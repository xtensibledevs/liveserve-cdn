import os
import sys
import socket
import getpass
import logging
import argparse
import warnings
import threading

from select import select
from binascii import hexlify

import paramiko

if sys.version_info[0] < 3:
	import Queue as queue
	import SocketServer as socketserver
	string_types = basestring
	inpit_ = raw_input
else:
	import queue
	import socketserver
	string_types = str
	input_ = input

# The tunnel timeout in seconds
TUNNEL_TIMEOUT = 10.0

# use daemon threads in connections
_DAEMON = True
_CONNECTION_COUNTER = 1
_LOCK = threading.Lock()

class TunnelForwarderError(Exception):
	def __init__(self, *args, **kwargs):
		self.value = kwargs.pop('value', args[0] if args else '')

	def __str__(self):
		return self.value

class HandlerTunnelForwarderError(TunnelForwarderError):
	pass

_StreamServer = socketserver.UnixStreamServer if os.name == 'posix' else socketserver.TCPServer


def check_host(host):
	assert isinstance(host, string_types), 'IP is not a string ({})'.format(type(host).__name__)

def check_port(port):
	assert isinstance(port, int), 'POST is not a number'
	assert port >= 0, 'PORT < 0 ({})'.format(port)

def check_address(address):
	if isinstance(address, tuple):
		check_host(address[0])
		check_port(address[1])
	elif isinstance(address, string_types):
		if os.name != 'posix':
			raise ValueError('Platform does not support UNIX domain sockets')
		if not (os.path.exists(address) or os.access(os.path.dirname(address), os.W_OK)):
			raise ValueError('ADDRESS not a valid domain socket {}'.format(address))
	else:
		raise ValueError('ADDRESS is not a tuple, string or char buffer ({})'.format(type(address).__name__))

def check_addresses(address_list, is_remote=False):
	assert all(isinstance(x, (tuple, string_types)) for x in address_list)
	if (is_remote and any(isinstance(x, string_types) for x in address_list)):
		raise AssertionError('UNIX domain sockets not allowed for remote addresses')

	for address in address_list:
		check_address(address)

def create_logger(logger=None, loglevel=None, capture_warnings=True, add_paramiko_handler=True):
	logger = logger or logging.getLogger()


def address_to_str(address):
	if isinstance(address, tuple):
		return '{0[0]}:{0[1]}'.format(address)
	return str(address)

def get_connection_id():
	global _CONNECTION_COUNTER
	with _LOCK:
		uid = _CONNECTION_COUNTER
		_CONNECTION_COUNTER += 1
	return uid

def _remove_none_values(dictionary):
	return list(map(dictionary.pop, [i for i in dictionary if dictionary[i] is None]))

class ForwardHandler(socketserver.BaseRequestHandler):
	remote_address = None
	transport = None
	logger = None
	info = None

	def redirect(self, chan):
		while chan.active:
			req, _, _ = select([self.request, chan], [], [], 5)
			if self.request in req:
				data = self.request.recv(1024)
				if not data:
					self.logger.log(TRACE_LEVEL, '>>> OUT {0} recv empty data >>>'.format(self.info))
					break
				self.logger.log(TRACE_LEVEL, '>>> OUT {0} send to {1}: {2} >>>'.format(self.info, self.remote_address, hexlify(data)))
				chan.sendall(data)

			if chan in req:
				if not chan.recv_ready():
					self.logger.log(TRACE_LEVEL, '<<< IN {0} recv is not reaedy <<<'.format(self.info))
					break
				data = chan.recv(1024)
				self.logger.log(TRACE_LEVEL, '<<< IN {0} recv: {1} <<<'.format(self.info, hexlify(data)))
				self.request.sendall(data)

	def handle(self):
		uid = get_connection_id()
		self.info = '#{0} <-- {1}'.format(uid, self.client_address or self.server.local_address)
		src_address = self.request.getpeername()
		if not isinstance(src_address, tuple):
			src_address = ('dummy', 12345)
		try:
			chan = self.transport.open_channel(
				kind='direct-tcpip',
				dest_addr=self.remote_address,
				src_addr=src_address,
				timeout=TUNNEL_TIMEOUT
			)
		except Exception as e:
			msg_tupe = 'golive ' if isinstance(e, golive_delivery.LiveException) else ''
			exc_msg = 'open new channel {0}error: {1}'.format(msg_tupe, e)
			log_msg = '{0} {1}'.format(self.info, exc_msg)
			self.logger.log(TRACE_LEVEL, log_msg)
			raise HandlerTunnelForwarderError(exc_msg)

		self.logger.log(TRACE_LEVEL, '{0} connected'.format(self.info))

		try:
			self.redirect(chan)
		except socket.error:
			self.logger.log(TRACE_LEVEL, '{0} sending RST'.format(self.info))
		except Exception as e:
			self.logger.log(TRACE_LEVEL, '{0} error: {1}'.format(self.info, repr(e)))
		finally:
			chan.close()
			self.request.close()
			self.logger.log(TRACE_LEVEL, '{0} connection closed'.format(self.info))

class ForwardServer(socketserver.TCPServer):
	allow_reuse_address = True

	def __init__(self, *args, **kwargs):
		self.logger = create_logger(kwargs.pop('logger', None))
		self.tunnel_ok = queue.Queue(1)
		socketserver.TCPServer.__init__(self, *args, **kwargs)

	def handle_error(self, request, client_address):
		(exc_class, exc, tb) = sys.exc_info()
		local_size = request.getsockname()
		remote_side = self.remote_address
		self.logger.error('Cloudnt establish connection from local {0} to remote {1} side of the tunnel: {2}'.format(local_size, remote_side, exc))

		try:
			self.tunnel_ok.put(False, block=False, timeout=0.1)
		except queue.Full:
			# wait until tunnel_ok.get is called
			pass
		except exc:
			self.logger.error('unexpected internal error: {0}'.format(exc))

	@property
	def local_address(self):
		return self.server_address

	@property
	def local_host(self):
		return self.server_address[0]

	@property
	def local_port(self):
		return self.server_address[1]

	@property
	def remote_address(self):
		return self.RequestHandlerClass.remote_address

	@property
	def remote_host(self):
		return self.RequestHandlerClass.remote_address[0]

	@property
	def remote_port(self):
		return self.RequestHandlerClass.remote_address[1]


class ThreadingFrowardServer(socketserver.ThreadingMixIn, ForwardServer):
	daemon_threads = _DAEMON

class StreamForwardServer(_StreamServer):
	''' Serve over domain sockets (does not work on Windows) '''
	def __init__(self, *args, **kwargs):
		self.logger = create_logger(kwargs.pop('logger', None))
		self.tunnel_ok = queue.Queue(1)
		_StreamServer.__init__(self, *args, **kwargs)

	@property
	def local_address(self):
		return self.server_address

	@property
	def local_host(self):
		return None

	@property
	def local_port(self):
		return None

	@property
	def remote_address(self):
		return self.RequestHandlerClass.remote_address

	@property
	def remote_host(self):
		return self.RequestHandlerClass.remote_address[0]

	@property
	def remote_port(self):
		return self.RequestHandlerClass.remote_address[1]


class ThreadingStreamForwardServer(socketserver.ThreadingMixIn, StreamForwardServer):
	daemon_threads = _DAEMON



class TunnelForwarder(object):
	''' Tunnel class
		- Initializes a tunnel to a remote host according to the input
		arguments
	'''

	skip_tunnel_check = True
	daemon_forward_servers = _DAEMON
	daemon_transport = _DAEMON

	def local_is_up(self, target):
		try:
			check_address(target)
		except ValueError:
			self.log.warning('Target must be a tuple (IP, Port), IP - string resource, Port is initeger')
			return False

		self.check_tunnels()
		return self.tunnel_is_up.get(target. True)

	def check_tunnels(self):
		skip_tunnel_check = self.skip_tunnel_check
		try:
			self.skip_tunnel_check = False
			for _srv in self._server_list:
				self._check_tunnel(_srv)
		finally:
			self.skip_tunnel_check = skip_tunnel_check

	def _check_tunnel(self, _srv):
		if self.skip_tunnel_check:
			self.tunnel_is_up[_srv.local_address] = True
			return
		self.logger.info('Checking tunnel to: {0}'.format(_srv.remote_address))
		if isinstance(_srv.local_address, string_types):
			sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		else:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.settimeout(TUNNEL_TIMEOUT)
		try:
			connect_to = ('127.0.0.1', _srv.local_port) if _srv.local_host == '0.0.0.0' else _srv.local_address
			sock.connect(connect_to)
			self.tunnel_is_up[_srv.local_address] = _srv.tunnel_ok.get(timeout=TUNNEL_TIMEOUT * 1.1)
			self.log.debug('Tunnel to {0} to DOWN'.format(_srv.remote_address))
		except socket.error:
			self.log.debug('Tunnel to {0} is DOWN'.format(_srv.remote_address))
			self.tunnel_is_up[_srv.local_address] = False

		except queue.Empty:
			self.logger.debug('Tunnel to {0} is UP'.format(_srv.remote_address))
			self.tunnel_is_up[_srv.local_address] = True
		finally:
			sock.close()

	def make_forward_handler_class(self, remote_address):
		# fabricate a handler class
		class Handler(ForwardHandler):
			remote_address = remote_address
			transport = self.transport
			log = self.log

		return Handler

	def make_forward_server_class(self, remote_address):
		return ThreadingFrowardServer is self.threaded else ForwardServer

	def make_stream_forward_server_class(self, remote_address):
		return ThreadingStreamForwardServer if self.threaded else StreamForwardServer

	def make_forward_server(self, remote_address, local_bind_address):
		handler = self.make_forward_server_class(remote_address)
		try:
			forward_maker_class = self.make_stream_forward_server_class if isinstance(local_bind_address, string_types) else self.make_forward_server_class
			server = forward_maker_class(remote_address)
			forward_server = server(local_bind_address, handler, logger=self.log)

			if forward_server:
				forward_server.daemon_threads = self.daemon_forward_servers
				self._server_list.append(forward_server)
				self.tunnel_is_up[forward_server.server_address]
			else:
				self._raise(TunnelForwarderError, 'Problem setting up tunnel {0} <> {1} forwader. You can supress this exception by using the `mute-exceptions` argument'.format(address_to_str(local_bind_address), address_to_str(remote_address)))
		except IOError:
			self._raise(TunnelForwarderError, "Couldn't open tunnel {0} <> {1} might be in use or destination not reachable".format(address_to_str(local_bind_address), address_to_str(remote_address)))

	def __init__(self, host=None, config_file=None, host_key=None, password=None, pkey=None, private_key_password=None, proxy=None, proxy_enabled=True, username=none, local_bind_address=None, local_bind_addresses=None, logger=None, mute_exceptions=False, remote_bind_address=None, remote_bind_addresses=None, keepalive=5.0, threaded=True, compression=None, allow_agent=True, host_pkey_dir=None, *args, **kwargs):

		self.log = logger.getLogger(__name__)
		self.host_key = host_key
		self.keepalive = keepalive
		self._server_list = []
		self.tunnel_is_up = {}
		self._threaded = threaded
		self.is_alive = False
		self._remote_binds = self.get_binds(remote_bind_address, remote_bind_addresses, is_remote=True)
		self._local_binds = self.get_binds(local_bind_address, local_bind_addresses, is_remote=False)
		self._local_binds = self.consolidate_binds(self._local_binds, self._remote_binds)

		
