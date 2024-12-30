
import sys
import os
import random
import socket
import signal
import time
import threading
import multiprocessing
from logging import getLogger

from .worker import Worker

DEFAULT_BUFFER_SIZE = 4096

logger = getLogger(__name__)

class RequestListener(multiprocessing.Process):
	''' Listens for client connections and assigns them to workers '''

	def __init__(self, localAddr, localPort, workers, bufferSize=DEFAULT_BUFFER_SIZE):
		multiprocessing.Process.__init__()
		self.localAddr = localAddr
		self.localPort = localPort
		self.workers = workers
		self.bufferSize = bufferSize

		self.activeWorkers = []
		self.listenSocket = None
		self.cleanupTh =  None
		self.keepGoing = True

	def cleanup(self):
		time.sleep(2)
		while self.keepGoing:
			currentWorkers = self.activeWorkers[:]
			for worker in currentWorkers:
				worker.join(.02)
				# if the worker is done
				if worker.is_alive() == False:
					self.activeWorkers.remove(worker)

			time.sleep(1.5)


	def closeWorkers(self, *args):
		self.keepGoing = False
		time.sleep(1)

		try:
			self.listenSocket.shutdown(socket.SHUT_RDWR)
		except:
			pass
		try:
			self.listenSocket.close()
		except:
			pass

		if not self.activeWorkers:
			self.cleanupTh and self.cleanupTh.join(3)
			signal.signal(signal.SIGTERM, signal.SIG_DFL)
			sys.exit(0)

		for worker in self.activeWorkers:
			try:
				worker.terminate()
				os.kill(worker.pid, signal.SIGTERM)
			except:
				pass
		time.sleep(1)

		remainingWorkers = []
		for worker in self.activeWorkers:
			worker.join(.03)
			if worker.is_alive() is True:
				remainingWorkers.append(worker)

		if len(remainingWorkers) > 0:
			time.sleep(1)
			for worker in remainingWorkers:
				worker.join(.2)

		self.cleanupTh and self.cleanupTh.join(2)

		signal.signal(signal.SIGTERM, signal.SIG_DFL)
		sys.exit(0)

	def retryFailedWorkers(self, *args):
		''' Loops over the activeWorkers and checks for shared `failedToConnect` value and then we pick a diffrent worker and assign the client to new worker '''

		time.sleep(2)
		successfulRuns = 0

		while self.keepGoing is True:
			currentWorkers = self.activeWorkers[:]
			for worker in currentWorkers:
				if worker.failedToConnect.value == 1:
					successfulRuns = -1
					logger.warn('Found a `failuretoConnect` worker\n')

					numWorkers = len(self.workers)

					if numWorkers > 1:
						nextWorkerInfo = None
						while (nextWorkerInfo is None) or (worker.workerAddr == nextWorkerInfo['addr'] and worker.workerPort == nextWorkerInfo['port']):
							nextWorkerInfo = self.workers[random.randint(0, numWorkers-1)]
					else:
						nextWorkerInfo = self.workers[0]

					logger.debug('Retrying request from %s from %s:%d on %s:%d\n' % (worker.clientAddr, worker.workerAddr, worker.workerPort))

					nextWorker = Worker(worker.clientSocket, worker.clientAddr, nextWorkerInfo['addr'], nextWorkerInfo['port'], self.bufferSize)
					nextWorker.start()
					self.activeWorkers.append(nextWorker)
					worker.failedToConnect.value = 0

			successfulRuns += 1
			if successfulRuns > self.maxActiveWorkers:
				successfulRuns = 6
			if successfulRuns > 5:
				time.sleep(2)
			else:
				time.sleep(.05)

	def run(self):
		signal.signal(signal.SIGTERM, self.closeWorkers)

		while True:
			try:
				listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				try:
					listenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
				except:
					pass
				listenSocket.bind((self.localAddr, self.localPort))
				self.listenSocket = listenSocket
				break

			except Exception as e:
				logger.error('Failed to bind to %s:%d. "%s" Retrying in 5 sec...\n' % (self.localAddr, self.localPort, str(e)))
				time.sleep(5)

		# Take 5 connections at a time
		listenSocket.listen(5)

		# Create thread that will cleanup completed tasks
		self.cleanupTh = cleanupTh = threading.Thread(target=self.cleanup)
		cleanupTh.start()

		# create thread that will retry failed tasks
		retryThread = threading.Thread(target=self.retryFailedWorkers)
		retryThread.start()

		try:
			while self.keepGoing is True:
				for workerInfo in self.workers:
					if self.keepGoing is False:
						break
					try:
						(clientConn, clientAddr) = listenSocket.accept()
					except:
						logger.error('Cannot bind to %s:%s\n' % (self.localAddr, self.localPort))
						if self.keepGoing is True:
							time.sleep(3)
							continue
						raise
					worker = Worker(clientConn, clientAddr, workerInfo['addr'], workerInfo['port'], self.bufferSize)
					self.activeWorkers.append(worker)
					worker.start()
		except Exception as e:
			logger.error('Got exception : %s, shutting down workers on %s:%d\n' % (str(e), self.localAddr, self.localPort))
			self.closeWorkers()
			return

		self.closeWorkers()



