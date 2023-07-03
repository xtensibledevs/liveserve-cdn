import sys
import multiprocessing
import time
import signal
import select
import socket
from logging import getLogger

logger = getLogger(__name__)

DEFAULT_BUFFER_SIZE = 4096
GRACEFUL_SHUTDOWN_TIME = 6

class Worker(multiprocessing.Process):
	''' Worker handles the worker-side of processing a request (communicating with a backend and the client ) '''

	def __init__(self, clientSocket, clientAddr, workerAddr, workerPort, bufferSize=DEFAULT_BUFFER_SIZE):
		multiprocessing.Process.__init__(self)

		self.clientSocket = clientSocket
		self.clientAddr = clientAddr

		self.workerAddr = workerAddr
		self.workerPort = workerPort
		self.workerSocket = None
		# the default size is 4096 bytes
		self.bufferSize = bufferSize

		self.failedToConnect = multiprocessing.Value('i', 0)

	def closeConnections(self):
		try:
			self.workerSocket.shutdown(socket.SHUT_RDWR)
		except:
			pass

		try:
			self.workerSocket.close()
		except:
			pass

		try:
			self.clientSocket.shutdown(socket.SHUT_RDWR)
		except:
			pass

		try:
			self.clientSocket.close()
		except:
			pass

		signal.signal(signal.SIGTERM, signal.SIG_DFL)

	def closeConnectionsAndExit(self):
		self.closeConnections()
		sys.exit(0)

	def run(self):
		workerSocket = self.workerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		clientSocket = self.clientSocket
		bufferSize = self.bufferSize

		try:
			workerSocket.connect((self.workerAddr, self.workerPort))
		except:
			logger.error('Could not connect to worker %s:%d\n' % (self.workerAddr, self.workerPort))
			self.failedToConnect.value = 1
			time.sleep(GRACEFUL_SHUTDOWN_TIME)
			return

		signal.signal(signal.SIGTERM, self.closeConnectionsAndExit())

		try:
			dataToClient = b''
			dataFromClient = b''
			while True:
				waitingToWrite = []
				if dataToClient:
					waitingToWrite.append(clientSocket)
				if dataFromClient:
					waitingToWrite.append(workerSocket)

				try:
					(hasDataForRead, readyForWrite, hasErr) = select.select([clientSocket, workerSocket], waitingToWrite, [clientSocket, workerSocket], .3)
				except KeyboardInterrupt:
					break

				if hasErr:
					break

				if clientSocket in hasDataForRead:
					nextData = clientSocket.recv(bufferSize)
					if not nextData:
						break
					dataFromClient += nextData

				if workerSocket in hasDataForRead:
					nextData = workerSocket.recv(bufferSize)
					if not nextData:
						break
					dataToClient += nextData

				if workerSocket in readyForWrite:
					while dataFromClient:
						workerSocket.send(dataFromClient[:bufferSize])
						dataFromClient = dataFromClient[bufferSize:]

				if clientSocket in readyForWrite:
					while dataToClient:
						clientSocket.send(dataToClient[:bufferSize])
						dataToClient = dataToClient[bufferSize:]

		except Exception as e:
			logger.error("Error on %s:%d: %s\n" % (self.workerAddr, self.workerPort, str(e)))

		self.closeConnectionsAndExit()

