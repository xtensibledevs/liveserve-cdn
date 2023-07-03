
# A control connection, metadata, and proxy connections which
# route public traffic to a firewalled endpoint
class Tunnel:
	# request that opened the tunnel
	req = None
	# when the tunnel was opened
	start_time = None
	# public url of the tunnel
	url = None
	# tcp listener
	listener = None
	# control connection
	conn_ctrl = None
	# logger
	log = None

def registerVHostPortocols(tun, protocol, servingPort):
	vhost = os.environ.get('VHOST') or f"{opts.domainName}:{servingPort}"
	# canonicalize virtual host by removing default port
	defaultPort = defaultPortMap[protocol]
	defaultPortSuffix = f":{defaultPort}"

	# register for specific hostname
	if hostname != "":
		tun.url = f"{protocol}://{hostname.trim()}"
		return TunnelRegistery.register(tun.url, tun)

	# Register for specific subdomain
	if subdomain != "":
		tun.url = f"{protocol}://{subdomain}.{vhost}"
		return TunnelRegistery.register(tun.url, tun)

	# Register for random URL
	tun.url = f"{protocol}://{random()}.{vhost}"
	return TunnelRegistery.register(tun.url, tun)



# A GoLiveAppDelivery Service client side application that is attached to the 
# golive application deployed in a container.
class GoLiveAppDelivery:
	def run():
		pass

	def close():
		pass

	def play_req():
		pass


class Controller:
	# the model updates the application
	def update(state):
		pass

	# the controller can shutdown the application
	def close(msg):
		pass

	# play_req instructs the app deliverer to play requests
	def play_req(tun, payload):
		pass

	# the current state
	def state():
		pass

	# get the address where the web inspection interface is running
	def get_webinspect_address():
		pass


def run(config):
	

class State:
	def get_client_version()

	def get_server_version()

	def get_tunnels()

	def get_protocols()

	def update_status()

	def conn_status()

	def connection_metrics()

	def bytes_in_metrics()

	def bytes_out_metrics()

	def set_update_status(update_status)

class ConnectionContext:
	tunnel: Tunnel
	client_addr: str

class Tunnel:
	public_url = None
	protocol = protocols.Protocol
	local_addr = None

class ConnectionStatus:
	CONNECTING = 0
	RECONNECTING = 1
	ONLINE = 2

class UpdateStatus:
	NONE = 0
	INSTALLING = 1
	READY = 2
	AVAILABLE = 3

class Connection:
	# an underlying tcp/udp connection
	underhood_tcp_connection
	conn_type = None
	conn_id = None

	def __init__(self, conn_id, remote_addr, proxy_addr):
		# sender generates the conn_id
		self.conn_id = conn_id
		self.conn_dest = proxy_addr or remote_addr
		self.log = logging.getLogger(__name__)
		self.log.debug("Establishing connection with remote host at %s:%s" % (conn_dest[0], conn_dest[1]))
		# uses an http connection
		self.raw_conn = httplib.HTTPConnection(host=conn_dest[0], port=conn_dest[1])
		self.remote_addr = remote_addr

	def url(self, url):
		return "http://{host}:{port}{url}".format(host=self.remote_addr[0], port=self.remote_addr[1], url=url)

	def get_id(self):
		return self.conn_id

	def create_conn(self, target_addr):
		params = urllib.urlencode("host": target_addr[0], "port": target_addr[1])
		if proxy_auth:
			headers = {"Content-Type": "application/x-www-form-urlendoded", "Accept": "text/plain", "User-Agent": "GoLive DNet Client/0.1"}

		self.raw_conn.request("CONNECT", self.url("/" + self.id), params, headers)
		resp = self.raw_conn.getresponse()
		
		resp.read()

		if resp.status != 200:
			return Exception("Non-200 reponse from proxy server: %s", resp.status)

		# upgrade the connection to tls
		self.raw_conn.to_tls()

	def send_data(self, data):
		params = urllib.urlencode({"data": data})
		headers = {"Content-Type": "application/x-www-form-urlendoded", "Accept": "text/plain"}
		try:
			self.raw_conn.request("PUT", self.url("/" + self.id), params, headers)
			response = self.raw_conn.getresponse()
			response.read()
			print response.status
		except (httplib.HTTPResponse, socket.error) as e:
			print "Error sending data: %s" % e

	def recv_data(self):
		try:
			self.raw_conn.request("GET", "/" + self.id)
			response = self.raw_conn.getresponse()
			data = response.read()
			if response.status == 200:
				return data
			else:
				return None
		except (httplib.HTTPResponse, socket.error) as e:
			self.log.error("Error Receiving Data: %s" % e)
			return None

	def close(self):
		self.log.debug("Closing Connection to target remote host %s:%s" % (conn_dest[0], conn_dest[1]))
		self.raw_conn.request("DELETE", "/" + self.id)
		self.raw_conn.getresponse()

class LoggerConn(Connection):
	conn_logger = loging.getLogger()

	def __init__(connection, logger, conn_id, conn_type):
		self.conn_logger = logger
		super().__init__(connection, conn_id, conn_type)

class Listener:
	address
	# live array - changes continously
	connections = []

	def __init__(address, conns):
		self.address = address
		self.conns = conns


def wrap_conn(conn, conn_type):
	if isinstance(conn, HTTPConnection):
		wrapped = conn.underhood_tcp_connection
		return LoggerConn(wrapped.underhood_tcp_connection, wrapped.conn_logger, wrapped.conn_id, wrapped.conn_type)
	elif isinstance(conn, LoggerConn):
		return conn
	elif isinstance(conn, TCPConnection):
		wrapped = LoggerConn(conn, logger.getLogger(), random.rand(), conn_type)
		return wrapped
	return None

def listen(address, conn_type, tlsConfig):
	try:
		listener = TCPListener("tcp_listener", address)
	except Exception as e:
		return None

	l = Listener(address=listener.address(), conns=[])

	# Theaded listening and wrapping of the connection object
	# into LoggerConn, TCPConnection or Connection


# Copy streaming data to different sources simultaneously
class Tee:
	def __init__(self, conn, reader, readPIPE, writer, writePIPE):
		self.reader = reader
		self.writer = writer
		self.writePIPE = writePIPE
		self.readPIPE = readPIPE
		self.conn = conn

		self.readPIPE, self.writePIPE = os.pipe()


	def read(self):
		r = os.fdopen(self.readPIPE)
		return r.read()

	def close(self):
		os.close(self.readPIPE)
		os.close(self.writePIPE)

	def write(self, data):
		return os.write(self.writePIPE, data)

	def read_from(self, reader):
		r = os.fdopen(reader)
		os.write(self.writePIPE, r.read())


