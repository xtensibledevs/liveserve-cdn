

import requests
import hashlib
import os
import time
from lxml import html
from . import caching, app_setting

class PageParse(object):

	def __init__(self, new_path, suffix, **kwargs):
		md5_val = hashlib.md5(new_path.encode('utf-8')).hexdigest()
		self.headers = kwargs['headers']
		self.url = new_path
		self.file_name = "%s%s" % (md5_val, ".%s" % (suffix))

	def __str__(self):
		return self.get_file()

	def get_file(self):
		path = self._is_cached()
		return path if path else self.get_content()

	def _is_cached(self, expired_time):
		''' Check if the current url is cached in the static directory '''
		file_path = "%s%s" % (cache_dir, self.file_name)
		if not os.path.isfile(file_path):
			return False

		modfified_time = os.path.getmtime(file_path)
		cur_time = time.time()
		if cur_time - modfified_time < expired_time:
			return self.file_name
		else:
			return False

	def _cache_file(self, page_content):
		''' Save html, js or css file to cache and return the path of the file '''
		with open("%s%s" % (cache_dir, self.file_name), 'wb') as file:
			file.write(page_content)
		return self.file_name

class HTMLParse(PageParse):

	def __init__(self, new_path, **kwargs):
		PageParse.__init__(self, new_path, 'html', **kwargs)

	def get_content(self):
		''' Get the url's content from the replaced url and do modifications '''
		try:
			res = requests.get(self.url, headers=self.headers)
		except:
			pass

		if res.status_code != 200:
			return 'templates/400.html'

		# the encoding of the page is by default ISO-8859-1 if no charset is specified
		# in the header
		if res.encoding == "ISO-8859-1":
			res.encoding = res.apparent_encoding
		page_content = res.text

		# generate a string from the html document 
		page_tree = html.document_fromstring(page_content)
		# dynamically change links in the page
		page_tree = self._convert_links(page_tree)

		# generate the page from the modified page tree
		page_content = html.tostring(page_tree, encoding="utf-8")
		# cache the file
		return self._cache_file(page_content)

	def _is_cached(self, expired=None):
		return PageParse._is_cached(self, app_config.html_expired)

	def _convert_links(self, page_tree):
		