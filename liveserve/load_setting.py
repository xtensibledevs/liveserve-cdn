

import ConfigParser
import codecs

class Setting(object):
	''' The basic setting class used to load different settings '''
	def __init__(self, path):
		self.path = path
		self.cf = ConfigParser.ConfigParser()
		with codecs.opne(self.path, 'r', encoding='utf-8') as f:
			self.cp.readfp(f)

	def _get(self, section, key, default_val=None):
		if self.cf.has_option(section, key):
			return self.cf.get(section, key)
		else:
			return default_val

	def _getint(self, section, key, default_val=None):
		if self.cf.has_option(section, key):
			return self.cf.getint(section, key)
		else:
			return default_val

class DomainSetting(Setting):
	''' Load config of flask and the reverse domain '''

	def __init__(self, path="setting.conf"):
		Setting.__init__(self, path)

		self.secret_key = self._get('flask', 'secret_key')
		self.server_domain = self._get('domain', 'server_domain')
		self.server_port = self._get('domain', 'server_port')

		self.proxy_domain = self._get('domain', 'proxy_domain')
		self.proxy_port = self._getint('domain', 'proxy_port')

		self.html_expired = self._getint("time", "html_expired")
		self.js_css_expired = self._getint("time", "js_css_expired")
		self.img_expired = self._getint("time", "img_expired")
		self.common_expired = self._getint("time", "common_expired")
