

from .urlprocessing import get_url_suffix
from .pageparse import HTMLParser, JSCSSParse, ImageParse, CommonParse

class PageManagment(object):

	@classmethod
	def get_page_obj(cls, new_path, **kwargs):
		''' Get the suitable pages object form the suffix information

		headers : used in the methods: requests.get()
		kwargs[ip] : visiotr's ip address
		'''
		suffix = get_url_suffix(new_path)
		if suffix == "html":
			return HTMLParser(new_path, **kwargs)
		elif suffix in ["js", "css"]:
			return JSCSSParse(new_path, suffix, **kwargs)
		elif suffix in ["jpg", "png", "gif", "ico", "jpeg"]:
			return ImageParse(new_path, suffix, **kwargs)
		elif suffix:
			return CommonParse(new_path, suffix, **kwargs)
		else:
			pass