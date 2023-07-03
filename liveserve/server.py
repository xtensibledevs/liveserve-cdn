class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
	def __init__(self, config):
		self.config = config
		self.blocked_users = {}
		self.blocked_last_mod = None
		self.tcp_tunnels = {}
		self.http_tunnels = {}