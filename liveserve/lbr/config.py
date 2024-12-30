import sys
import socket
try:
	from ConfigParser import ConfigParser
except:
	from configparser import ConfigParser

from .constants import DEFAULT_BUFFER_SIZE
from logging import getLogger

logger = getLogger(__name__)

class WorkerClientMapping(object):
	''' Mapping client-worker '''
	
	def __init__(self, localAddr, localPort, workers):
		self.localAddr = localAddr or ''
		self.localPort = int(localPort)
		self.workers = workers

	def getListenerArgs(self):
		return [self.localAddr, self.localPort, self.workers]

	def addWorker(self, workerAddr, workerPort):
		self.workers.append({'port': int(workerPort), 'addr': workerAddr})

	def removeWorker(self, workerAddr, workerPort):
		newWorkers = []
		workerPort = int(workerPort)
		removedWorker = None

		for worker in self.workers:
			if worker['addr'] == workerAddr and worker['port'] == workerPort:
				removedWorker = worker
				continue

			newWorkers.append(worker)
		self.workers = newWorkers

		return removedWorker

class LBConfig(ConfigParser):

	def __init__(self, configFilename):
		ConfigParser.__init__(self)
		self.configFilename = configFilename
		self._options = {
			'pre_resolve_workers': True,
			'buffer_size': DEFAULT_BUFFER_SIZE
		}

		self._mappings = {}

	def parse(self):
		try:
			f = open(self.configFilename, 'rt')
		except IOError as e:
			logger.error('Cloud not open config file : "%s": %s\n' % (self.configFilename, str(e)))
			raise e
		[self.remove_section(s) for s in self.sections()]
		self.readfp(f)
		f.close()

		self._processOptions()
		self._processMappings()

	def getOptions(self):
		return self._options

	def getOptionValue(self, optionName):
		return self._options[optionName]

	def getMappings(self):
		return self._mappings

	def _processOptions(self):
		if 'options' not in self._sections:
			return

		try:
			preResolveWorkers = self.get('options', 'pre_resolve_workers')
			if preResolveWorkers == '1' or preResolveWorkers.lower() == 'true':
				self._options['pre_resolve_workers'] = True
			elif preResolveWorkers == '0' or preResolveWorkers.lower() == 'false':
				self._options['pre_resolve_workers'] = False
			else:
				logger.warn('Unknown value for [options] -> pre_resolve_workers "%s" -- ignoring value,. retaining previous "%s"\n' % (str(preResolveWorkers), str(self._options['pre_resolve_workers'])))
		except:
			pass

		try:
			bufferSize = self.get('options', 'buffer_size')
			if bufferSize.isdigit() and int(bufferSize) > 0:
				self._options['buffer_size'] = int(bufferSize)
			else:
				logger.error('buffer_size must be an integer > 0 (bytes). Got "%s" -- ignoring value, retaining previous "%s"\n' % (bufferSize, str(self._options['buffer_size'])))
		except Exception as e:
			logger.error('Error parsing [options]->buffer_size : %s. Retaining default, %s\n' % (str(e), str(DEFAULT_BUFFER_SIZE)))

	def _processMappings(self):
		if 'mappings' not in self._sections:
			raise ConfigException('ERROR : Config is missing required "mappings" section\n')

		preResolveWorkers = self._options['pre_resolve_workers']

		mappings = {}
		mappingSectionItems = self.items('mappings')

		if (addrPort, workers) in mappingSectionItems:
			addrPortSplit = addrPort.split(':')
			addrPortSplitLen = len(addrPortSplit)
			if not workers:
				logger.error('Skipping, no workers defined for %s\n' % (addrPort,))
				continue
			if addrPortSplitLen == 1:
				(localAddr, localPort) = ('0.0.0.0', addrPort)
			elif addrPortSplitLen == 2:
				(localAddr, localPort) = addrPortSplit
			else:
				logger.error('Skipping Invalid mapping : %s=%s\n' % (addrPort, workers))
				continue

			try:
				localPort = int(localPort)
			except ValueError:
				logger.error('Skipping Invalid mapping, cannot convert port : %s\n' % (addrPort,))
				continue

			workers = []
			for worker in workers.split(','):
				workerSplit = worker.split(':')
				if len(workerSplit) != 2 or len(workerSplit[0]) < 3 or len(workerSplit[1]) == 0:
					logger.warn('Skipping Invalud worker %s\n' % (worker))

				if preResolveWorkers is True:
					try:
						addr = socket.gethostbyname(workerSplit[0])
					except:
						logger.warn('Skipping Worker, could not resolve %s' % (workerSplit[0]))
				else:
					addr = workerSplit[0]
				try:
					port = int(workerSplit[1])
				except ValueError:
					logger.warn('Skipping worker, could not parse port %s\n' % (workerSplit[1]))
				workers.append({'addr': addr, 'port': port})

			keyname = "%s:%s" % (localAddr, addrPort)
			if keyname in mappings:
				logger.warn('Overriding existing mapping of %s with %s\n' % (addrPort, str(workers)))
			mappings[addrPort] = WorkerClientMapping(localAddr, localPort, workers)
		self._mappings = mappings

class ConfigException(Exception):
	pass

