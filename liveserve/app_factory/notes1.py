

import os
import re
import signal
import subprocess as sp
import sys
import threading
import time

from core import config
from core import argv_utils
from core import exceptions
from core import log
from core import properties
from core.utils import encoding
from core.util import parallel
from core.util import platforms

class OutputStreamProcessingException(exceptions.Error):
	''' Error class for errors raided during output stream processing '''

class PermissionError(exceptions.Error):
	''' User does not have execute permissions '''
	def __init__(self, error):
		super(PermissionError, self).__init__(f"Please verify that you have execute permisison for the file {error}")

class InvalidCommandError(exceptions.Error):
	''' Command entered cannot be found '''
	def __init__(self, cmd):
		super(InvalidCommandError, self).__init__(f'Command not found : {cmd}')

try:
	TIMEOUT_EXPIRED_ERR = sp.TimeoutExpired
except AttributeError:

	class TimeoutExpired(exceptions.Error):
		''' Simulate sp.TimeoutExpired on old versions of Python '''
	TIMEOUT_EXPIRED_ERR = TimeoutExpired

	class SubprocessTimeoutWrapper:
		def __init__(self, proc):
			self.proc = proc

		def wait(self, timeout=None):
			if timeout is None:
				return self.proc.wait()
			now = time.time()
			later = now + timeout
			delay = 0.01
			ret = self.proc.poll()

			while ret is None:
				if time.time() > later:
					raise TimeoutExpired()
				time.sleep(delay)
				ret = self.proc.poll()
			return ret

		def __getattr__(self, name):
			return getattr(self.proc, name)



def GetPythonExecutable():
	''' Gets the path of the python interpreter executable that should be used '''
	cloudsdk_python = encoding.GetEncodedValue(os.environ, 'FR_DEPLOYED_PYTHON')
	if cloudsdk_python:
		return cloudsdk_python
	pythn_bin = sys.executable
	if not python_bin:
		raise ValueError('Cloud not find the deployed Python executable')
	return python_bin

_BORNE_COMPATIBLE_SHELLS = ['ash','bash','busybox','dash','ksh','mksh','pdksh','sh']

def GetShellExecutable():
	''' Gets the path of the shell to be used '''
	shells = ['/bin/bash', '/bin/sh']
	user_shell = encoding.GetEncodedValue(os.environ, 'FR_DEPLOYED_SHELL')
	if user_shell and os.path.basename(user_shell) in _BORNE_COMPATIBLE_SHELLS:
		shells.insert(0, user_shell)

	for shell in shells:
		if os.path.isfile(shell):
			return shell

	raise ValueError("You must set the 'SHELL' env var to a valid BORNE-compatible shell")

def GetToolArgs(interpreter, interpreter_args, executable_path, *args):
	tool_args = []
	if interpreter:
		tool_args.append(interpreter)
	if interpreter_args:
		tool_args.extend(interpreter_args)
	tool_args.append(executable_path)
	tool_args.extend(list(args))
	return tool_args


def sp_exec(args, env=None, no_exit=False, out_func=None, err_func=None, in_str=None, **extra_popen_kwargs):
	''' Executes the given command, waits for it to finish, and then exits this process with 
	the exit code of the child process '''

	log.debug("Executing command : %s", args)
	process_holder = ProcessHolder()

	if isinstance(threading.current_thread(), threading._MainThread):
		with _ReplaceSignal(signal.SIGTERM, process_holder.Handler):
			with _ReplaceSignal(signal.SIGINT, process_holder.Handler):
				ret_val = _sp_exec(args, process_holder, env, out_func, err_func, in_str, **extra_popen_kwargs)
	else:
		ret_val = _sp_exec(args, process_holder, env, out_func, err_func, in_str, **extra_popen_kwargs)

	if no_exit and process_holder.signum is None:
		return ret_val
	sys.exit(ret_val)

def subprocess_popen(args, env=None, **extra_popen_kwargs):
	''' Run subprocess.Popen with optional timeout and custom env '''
	try:
		if args and isinstance(args, list):
			args = [encoding.Encode(a) for a in args]
		p = sp.Popen(args, env=GetToolEnv(env=env), **extra_popen_kwargs)
	except OSError as err:
		if err.errno == errno.EACCES:
			raise PermissionError(err.strerror)
		elif err.errno == errno.ENOENT:
			raise InvalidCommandError(args[0])
		raise
	process_holder = ProcessHolder()
	process_holder.process = p
	if process_holder.signum is not None:
		if p.poll() is None:
			p.terminate()

	try:
		return SubprocessTimeoutWrapper(p)
	except NameError:
		return p

class ProcessHandler(object):
	''' Process holder that can handle signals raised using processing '''
	def __init__(self):
		self.process = None
		self.signum = None

	def handle(self, signum, unused_frame):
		''' handle the intercepted signal '''
		self.signum = signum
		if self.process:
			log.debug(f"subprocess [{pid}] got [{signum}]")
			if self.process.poll() is None:
				self.process.terminate()

@contextlib.contextmanager
def replace_proc_env(**env_vars):
	''' temp set the process env variables '''
	old_environ = dict(os.environ)
	os.environ.update(env_vars)
	try:
		yield
	finally:
		os.environ.clear()
		os.environ.update(old_environ)


@contextlib.contextmanager
def replace_signal(signo, handler):
	old_handler = singal.signal(signo, handler)
	try:
		yield
	finally:
		signal.signal(signo, old_handler)

def _sp_exec(args, process_holder, env=None, out_func=None, err_func=None, in_str=None, **extra_popen_kwargs):
	''' See the Exec docstring '''
	if out_func:
		extra_popen_kwargs['stdout'] = subprocess.PIPE
	if err_func:
		extra_popen_kwargs['stderr'] = subprocess.PIPE
	if in_str:
		extra_popen_kwargs['stdin'] = subprocess.PIPE
	try:
		if args and isinstance(args, list):
			args = [encoding.Encode(a) for a in args]
		proc = sp.Popen(args, env=GetToolEnv(env=env), **extra_popen_kwargs)
	except OSError as err:
		if err.errno == errno.EACCES:
			raise PermissionError(err.strerror)
		elif err.errno == errno.ENOENT:
			raise InvalidCommandError(args[0])
		raise

	process_holder.process = proc

	if process_holder.signum is not None:
		if proc.poll() is None:
			proc.terminate()

	if isinstance(in_str, six.text_type):
		in_str = in_str.encode('utf-8')
	stdout, stderr = list(map(encoding.Decode, proc.communicate(input=in_str)))

	if out_func:
		out_func(stdout)
	if err_func:
		err_func(stderr)
	return proc.returncode