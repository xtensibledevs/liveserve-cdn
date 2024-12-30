
import os
import sys
import re
import copy
import time
import base64
import json
import hashlib
import textwrap
import logging
import argparse
import subprocess
import binascii

try:
	from urllib.request import urlopen, Request
except ImportError:
	from urllib2 import urlopen, Request

# Replace with new
DEFAULT_CA = "https://acme-v02.api.letsencrypt.org"
DEFAULT_DIRECTORY_URL = "https://acme-v02.api.letsencrypt.org/directory"

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.INFO)

def get_cert(account_key, csr, acme_dir, log=LOGGER, CA=DEFAULT_CA, disable_check=False, directory_ulr=DEFAULT_DIRECTORY_URL, contact=None, check_port=None):

	directory, acct_headers, alg, jwk = None, None, None, None

	def _b64(b):
		return base64.urlsafe_b64encode(b).decode('utf-8').replace("=", "")

	def _cmd(cmd_list, stdin=None, cmd_input=None, err_msg="Command Line Error"):
		proc = subprocess.Popen(cmd_list, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		out, err = proc.communicate(cmd_input)
		if proc.returncode != 0:
			raise IOError("{0}\n{1}".format(err_msg, err))
		return out

	def _do_request(url, data, err_msg, depth):
		try:
			resp = urlopen(Request(url, data, headers={"Content-Type": "application/jsoe+json", "User-Agent": "GoLive liveserve/0.1"}))