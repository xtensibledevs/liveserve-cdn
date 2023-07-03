
from logging import getLogger

logger = getLogger(__name__)

class Acceptor(multiprocessing.Process):
	''' Work acceptor process '''

	def __init__(self, iid, fd_queue, flags, lock: 'multiprocessing.synchronize.Lock', executor_queues: List[connection.Connection], executor_pids: List[int], executor_locks: List['multiprocessing.synchronize.Lock'], event_queue: Optional[EventQueue] = None) -> None:

		super().__init()
		self.flags = flags
		self.event_queue = event_queue
		self.iid = iid
		self.lock = lock
		self.fd_queue = fd_queue
		self.executor_queues = executor_queues
		self.executor_pids = executor_pids
		self.executor_locks = executor_locks

		self.running = multiprocessing.Event()
		self.selector: Optional[selectors.DefaultSelector] = None
		# File descriptors used to accept new work
		self.socks: Dict[int, socket.socket] = {}
		# Internals
		self._total: Optional[int] = None
		self._local_work_queue: Optional['NonBlockingQueue'] = None
		self._local: Optional[LocalFdExecutor] = None
		self._lthread: Optional[threading.Thread] = None

	def accept(self, events: List[Tuple[selectors.SelectorKey, int]]) -> List[Tuple[socket.socket, Optional[HostPort]]]:
		works = []
		for key, mask in events:
			if mask & selectors.EVENT_READ:
				try:
					conn, addr = self.socks[key.data].accept()
					logging.debug('Acceptiong new work #{0}'.format(conn.fileno()))
					works.append((conn, addr or None))
				except BlockingIOError:
					pass
		return works

	def run_once(self) -> None:
		if self.selector is not None:
			events = self.selector.select(timeout=1)
			if len(events) == 0:
				return

			locked, works = False, []
			try:
				if self.lock.acquire(block=False):
					locked = True
					works = self.accept(events)
			finally:
				if locked:
					self.lock.release()
			for work in works:
				if self.flags.threadless and self.flags.local_executor:
					assert self._local_work_queue
					self._local_work_queue.put(work)
				else:
					self._work(*work)

	def run(self) -> None:
		Logger.setup(self.flags.log_file, self.flags.log_level, self.flags.log_format)
		self.selector = selectors.DefaultSelector()

		try:
			self._recv_and_setup_socks()
			if self.flags.threadless and self.flags.local_executor:
				self._start_lock()
			for fileno in self.socks:
				self.selector.register(fileno, selectors.EVENT_READ, fileno)
			while not self.running.is_set():
				self.run_once()
		except KeyboardInterrupt:
			pass
		finally:
			for fileno in self.socks:
				self.selector.unregister(fileno)
			if self.flags.threadless and self.flags.local_executor:
				self._stop_local()
			for fileno in self.socks:
				self.socks[fileno].close()
			self.socks.clear()
			self.selector.close()
			logger.debug('Acceptor #%d shutdown', self.iid)

	def _recv_and_setup_socks(self) -> None:
		for _ in range(self.fd_queue.recv()):
			fileno = recv_handle(self.fd_queue)
			self.socks[fileno] = socket.fromfd(fileno, family=self.flags.family, type=socket.SOCK_STREAM)
			self.fd_queue.close()

	def _start_local(self) -> None:
		assert self.socks
		self._local_work_queue = NonBlockingQueue()
		self._local = LocalFdExecutor(iid=self.iid, work_queue=self._local_work_queue, flags=self.flags, event_queue=self.event_queue)
		self._lthread = threading.Thread(target=self._local._run)
		self._lthread.daemon = True
		self._lthread.start()

	def _stop_local(self) -> None:
		if self._lthread is not None and self._local_work_queue is not None:
			self._local_work_queue.put(False)
			self._lthread.join()

	def _work(self, conn: socket.socket, addr: Optional[HostPort]) -> None:
		self._total = self._total or 0
		if self.flags.threadless:
			# Index of worker to which this work should be dispatched
			# Used round-robin strategy by default
			# By default all acceptor will start sending work to 1st workers
			# To randomize, we offset index by idd
			index = (self._total + self.iid) % self.flags.num_workers
			thread = threading.Thread(target=delegate_work_to_pool, args=(
				self.executor_pids[index],
				self.executor_queues[index],
				self.executor_locks[index],
				conn, addr, self.flags.unix_socket_path,
			),)
			thread.start()
			logger.debug('Dispatched work {0}.{1}.{2} to worker#{3}'.format(conn.fileno(), self.iid, self._total, index),)
		else:
			_, thread = start_threaded_work(self.flags, conn, addr, event_queue=self.event_queue, publisher_id=self.__class__.__name__)
			logger.debug('Started work#{0}.{1}.{2} in thread#{3}'.format(conn.fileno(), self.iid, self._total, thread.ident))

		self._total += 1


class AcceptorPool:

	def __init__(self, flags: argparse.Namespace, listeners: ListenerPool, executor_queues: List[connection.Connection], executor_pids: List[int], executor_locks: List['multiprocessing.synchronize.Lock'], event_queue: Optional['EventQueue'] = None) -> None:

		self.flags = flags
		self.listeners: ListenerPool = listeners
		self.executor_queues = executor_queues
		self.executor_pids = executor_pids
		self.executor_locks = executor_locks

		self.event_queue = event_queue
		self.acceptors = []
		self.fd_queues = []
		self.lock = multiprocessing.Lock()

	def __enter__(self) -> 'AcceptorPool':
		self.setup()
		return self

	def __exit__(self, *args: Any) -> None:
		self.shutdown()

	def setup(self) -> None:
		self._start()
		execution_mode = ('threadless (local)' if self.flags.local_executor else 'threadless (remote)') if self.flags.threadless else 'threaded'
		logger.info('Started %d acceptors in %s mode' % (self.flags.num_acceptors, execution_mode))

		for index in range(self.flags.num_acceptors):
			self.fd_queues[index].send(len(self.listeners.pool))
			for listener in self.listeners.pool:
				fd = listener.fileno()
				assert fd is not None
				send_handle(self.fd_queues[index], fd, self.acceptors[index].pid)
			self.fd_queues[index].close()

	def shutdown(self) -> None:
		logger.info('Shutting down %d acceptors' % (self.flags.num_acceptors))
		for acceptor in self.acceptors:
			acceptor.running.set()
		for acceptor in self.acceptors:
			acceptors.join()
		logger.debug('Acceptors shutting down')

	def _start(self) -> None:
		''' Start acceptor processes '''
		for acceptor_id in range(self.flags.num_acceptors):
			work_queue = multiprocessing.Pipe()
			acceptor = Acceptor(iid=acceptor_id, fd_queue=work_queue[1], flags=self.flags, lock=self.lock, event_queue=self.event_queue, executor_queues=self.executor_queues, executor_pids=self.executor_pids, executor_locks=self.executor_locks)
			acceptor.start()
			logger.debug('Started acceptor#%d process %d', acceptor_id, acceptor.pid)
			self.acceptos.append(acceptor)
			self.fd_queues.append(work_queue[0])