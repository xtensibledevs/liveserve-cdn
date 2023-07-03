

import os
import argparse
import random
import sys
import requests
import threading

from socketserver import ThreadingMixIn
from http.server import BaseHTTPRequestHandler, HTTPServer

# the hostname
hostname = 'en.wikipedia.org'

def merget_dicts(x, y):
	return x | y

def set_header():
	headers = {
		'Host': hostname
	}

	return headers

# Proxy HTTP Request Handler Class
class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
	protocol_version = 'HTTP/1.0'

	def get_connection_id(self):
		return self.path.split('/')[-1]

	def do_HEAD(self):
		self.do_GET(body=False)
		return

	def do_GET(self, body=True):
		sent = False
		try:
			url = 'https://{}{}'.format(hostname, self.path)
			req_header = self.parse_headers()

			print(req_header)
			print(url)

			resp = requests.get(url, headers=merget_dicts(req_header, set_header()), verify=False)
			sent = True

			self.send_response(resp.status_code)
			self.send_resp_headers(resp)
			msg = resp.text
			if body:
				self.wfile.write(msg.encode(encoding='UTF-8', errors='strict'))
			return
		finally:
			if not sent:
				self.send_error(404, 'error trying to proxy')

	def do_POST(self, body=True):
		sent = False

		try:
			url = 'https://{}{}'.format(hostname, self.path)
			content_len = int(self.headers.getheader('content-length', 0))
			post_body = self.rfile.read(content_len)
			req_header = self.parse_headers()

			resp = requests.post(url, data=post_body, headers=merget_dicts(req_header, set_header()), verify=False)
			sent = True

			self.send_response(resp.status_code)
			self.send_resp_headers(resp)
			if body:
				self.wfile.write(resp.content)
			return
		finally:
			if not sent:
				self.send_error(404, 'error trying to proxy')

	def parse_headers(self):
		req_header = {}
		for line in self.headers:
			line_parts = [o.strip() for o in line.split(':', 1)]
			if len(line_parts) == 2:
				req_header[line_parts[0]] = line_parts[1]
		return req_header

	def send_resp_headers(self, resp):
		respheaders = resp.headers
		print('Response Header')
		for key in respheaders:
			if key not in ['Content-Encoding', 'Transfer-Encoding', 'content-encoding', 'transfer-encoding', 'content-length', 'Content-Length']:
				print(key, respheaders[key])
				self.send_header(key, respheaders[key])
		# default headers
		self.send_header('Content-Length', len(resp.content))
		self.send_header('User-Agent', 'GoLive DNet Server/0.1')
		self.end_headers()

def parse_args(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(description='Proxy HTTP requests')
    parser.add_argument('--port', dest='port', type=int, default=9999,
                        help='serve HTTP requests on specified port (default: random)')
    parser.add_argument('--hostname', dest='hostname', type=str, default='en.wikipedia.org',
                        help='hostname to be processd (default: en.wikipedia.org)')
    args = parser.parse_args(argv)
    return args




def main(argv=sys.argv[1:]):
	global hostname
	args = parse_args(argv)
	hostname = args.hostname
	print('Reverse proxy starting on {} port {}'.format(args.hostname, args.port))
	server_address = ('127.0.0.1', args.port)
	httpd = ThreadedHTTPServer(server_address, ProxyHTTPRequestHandler)
	httpd.serve_forever()

if __name__ == "__main__":
	main()