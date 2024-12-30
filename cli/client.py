import sys
from urllib.parse import urljoin
import aiohttp
import bson
import threading
import socket
import websockets
import certifi
import asyncio
import ssl
from rich import print as pretty_print
from getpass import getuser
import click

class HTTPClient:
	def __init__(self, base_uri, token):
		self.base_uri = base_uri
		self.token = token

	async def process(self, message, websocket):
		async with aiohttp.ClientSession() as session:
			try:
				response = await session.request(
					method=message['method'],
					url=urljoin(self.base_uri, message['uri']),
					headers=message['header'],
					data=message['body'],
				)
			except:
				pretty_print(f"[bold red]FAIL: [white]Error Processing Request At: {message['url']}", file=sys.stderr)
				return {
                    'request_id': message['id'],
                    'token': self.token,
                    'status': 500,
                    'header': {},
                    'body': b'Error Performing Request',
                }

            pretty_print(f'[bold green]{"INFO:":<10} [white] {self.base_uri} - "[bold bright_red]{message["method"]} [white]{message["url"]}"[bold cyan] {response.status}')

            body = await response.read()
            response_message = {
            	'request_id': message['id'],
            	'token': self.token,
            	'status': response.status,
            	'header': dict(response.headers),
            	'body': body,
            }

            await websocket.send(bson.dumps(response_message))

class TCPClient:
	def __init__(self, remote_server_host, remote_server_port, local_server_host, local_server_port):
		self.remote_server_host = remote_server_host
		self.remote_server_port = remote_server_port
		self.local_server_host = local_server_host
		self.local_server_port = local_server_port

	@staticmethod
	def pump_read_to_write(read_conn, write_conn):
		size = 1024 * 256
		buffer = read_conn.recv(size)

		while buffer:
			try:
				write_conn.send(buffer)
				buffer = read_conn.recv(size)
			except (ConnectionResetError, BrokenPipeError):
				break

		read_conn.close()
		pretty_print("[bold red]Connection Closed!")

	def process(self, message, websocket):
		remote_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		remote_client.connect((self.remote_server_host, self.remote_server_port))

		local_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		local_client.connect((self.local_server_host, self.local_server_port))

		port = message["public_client_port"]
		remote_client.send(bytearray([port >> 8 & 0xFF, port & 0xFF]))

		# 2-way shit
		therading.Therad(target=pump_read_to_write, args=(remote_client, local_client)).start()
		therading.Therad(target=pump_read_to_write, args=(local_client, remote_client)).start()


http_ssl_ctx = ssl.create_default_context()
http_ssl_ctx.load_verify_locations(certifi.where())

async def open_http_tunnel(ws_uri: str, http_uri):
	async with websockets.connect(ws_uri, ssl=http_ssl_ctx) as websocket:
		message = bson.loads(await websocket.recv())

		if message.get("warning"):
			pretty_print(f"[bold yellow]WARNING: {message['warning']}", file=sys.stderr)

		if message.get("error"):
			pretty_print(f"[bold yellow]ERROR: {message['error']}", file=sys.stderr)
			return

		host, token = message["host"], message["toke"]

		pretty_print(f"{'Tunnel Status:':<25}[bold green]Online")
        pretty_print(
            f"{'Forwarded:':<25}{f'[bold cyan]{host} → {http_uri}'}")
        pretty_print(f"\n[bold bright_magenta]:tada: Visit: https://{host}\n")

        client = HTTPClient(http_uri, token)
        while True:
        	message = bson.loads(await websocket.recv())
        	asyncio.ensure_future(client.process(message, websocket))


tcp_ssl_context = ssl.create_default_context()
tcp_ssl_context.load_verify_locations(certifi.where())

async def open_tcp_tunnel(ws_uri, remote_server_host, local_server_port):
    async with websockets.connect(ws_uri, ssl=tcp_ssl_context) as websocket:
        message = json.loads(await websocket.recv())

        if message.get("warning"):
            pretty_print(
                f"[bold yellow]WARNING: {message['warning']}", file=sys.stderr)

        if message.get("error"):
            pretty_print(
                f"[bold yellow]ERROR: {message['error']}", file=sys.stderr)
            return

        local_server_host = '127.0.0.1'
        public_server_port = message["public_server_port"]
        private_server_port = message["private_server_port"]

        pretty_print(f"{'Tunnel Status:':<25}[bold green]Online")
        pretty_print(
            f"{'Forwarded:':<25}{f'[bold cyan]{remote_server_host}:{public_server_port} → 127.0.0.1:{local_server_port}'}")

        client = TCPClient(
            remote_server_host=remote_server_host,
            remote_server_port=private_server_port,
            local_server_host=local_server_host,
            local_server_port=local_server_port,
        )

        while True:
            message = json.loads(await websocket.recv())
            pretty_print("[bold green]INFO: [bold white] New Connection +1")

            threading.Thread(
                target=client.process,
                args=(message, websocket)
            ).start()

@click.group()
def main():
	pass

__version__ = "0.1.0"

banner = f"""[bold green]
██╗     ██╗██╗   ██╗███████╗███████╗███████╗██████╗ ██╗   ██╗███████╗
██║     ██║██║   ██║██╔════╝██╔════╝██╔════╝██╔══██╗██║   ██║██╔════╝
██║     ██║██║   ██║█████╗  ███████╗█████╗  ██████╔╝██║   ██║█████╗  
██║     ██║╚██╗ ██╔╝██╔══╝  ╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██╔══╝  
███████╗██║ ╚████╔╝ ███████╗███████║███████╗██║  ██║ ╚████╔╝ ███████╗
╚══════╝╚═╝  ╚═══╝  ╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝
{f'v{__version__}':>14}
                                                                     
[bold yellow]Press Ctrl+C to quit
"""

@main.command()
@click.argument('port')
@click.option('-s', '--subdomain', default='')
@click.option('--host', default='liveserve.xcloud.io')
def http(**kwargs):
    host, port = kwargs['host'], kwargs['port']
    username = kwargs['subdomain'] or getuser()

    pretty_print(banner)
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(
            open_http_tunnel(
                ws_uri=f'wss://{host}/_ws/?username={username}&port={port}&version={__version__}',
                http_uri=f'http://127.0.0.1:{port}',
            )
        )
    except KeyboardInterrupt:
        pretty_print(f"[bold red]\njprq tunnel closed!")
        sys.exit(1)


@main.command()
@click.argument('port', type=click.INT)
@click.option('--host', default='liveservetcp.xcloud.io')
def tcp(**kwargs):
    host, port = kwargs['host'], kwargs['port']

    pretty_print(banner)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            open_tcp_tunnel(
                remote_server_host=host,
                ws_uri=f'wss://{host}/_ws/',
                local_server_port=port
            )
        )
    except KeyboardInterrupt:
        pretty_print(f"[bold red]\njprq tunnel closed!")
        sys.exit(1)


if __name__ == '__main__':
    main()