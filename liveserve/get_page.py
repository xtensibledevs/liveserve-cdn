

import urlparse
import requests

def replace_domain(original_url, target_dom, port=80):
	''' Replace the domain of the original url 

	http://original.com/pages --> http://panjaksweets.store/catalog
	'''
	result = urlparse.urlparse(original_url)
	return result._replace(netloc="%s:%d" % (target_dom, port)).geturl()

def replace_sub_domain(original, target_dom, port=80):
	''' Replace top domain of the url 

	http://kolkata.pankajsweets.com/catalog --> http://kolkata.frcldapp1556343.frcloudnet/catalog

	http://kolkata.pankajsweets.com:8000/catalog --> http://kolkata.frcldapp1556343.frcloudnet:8000/catalog
	'''
	result = urlparse.urlparse(original_url)
	domain_list = result.netloc.split(".")
	if len(domain_list) <= 2:
		print("Error !!! %s" % (original_url))
		return
	else:
		new_netloc = "%s.%s" % ("".join(domain_list[:-2]), target_dom)
	return result._replace(netloc="%s:%d" % (new_netloc, port)).geturl()

def remove_anchor(original_url):
	''' Remove the anchor in url
	http://original.com/pages?time=1#23 --> http://internalapp.com/pages?time=1
	'''
	result = urlparse.urlparse(original_url)
	return result._replace(fragment=None).geturl()

def get_url_suffix(path):
	''' Get the requested type of resource

	Use HEAD request is to check the content type of the URL
	We need to allow redirect in 'request.head' method, otherwise we may get wrong
	info
	'''
	res = requests.head(path, allow_redirects=True)
	content_type = res.headers.get('content-type', None) or res.headers.get('Content-Type', None)

	if content_type:
		if any(x in content_type for x in ["html", "htm"]):
			return "html"
		elif any(x in content_type for x in ["jpeg", "jpg"]):
			return "jpg"
		elif any(x in content_type for x in ["png"]):
			return "png"
		elif any(x in content_type for x in ["gif"]):
			return "gif"
		elif any(x in content_type for x in ["css"]):
			return "css"
		elif any(x in content_type for x in ["javascript", "js", "x-javascript"]):
			return "js"
		else:
			pass

	url_path = urlparse.urlparse(path).path
	url_path_l = url_path.split(".")
	if len(url_path_l) != 1:
		return url_path_l[-1]
	else:
		return None