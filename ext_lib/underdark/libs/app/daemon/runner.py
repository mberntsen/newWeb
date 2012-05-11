# -*- coding: utf-8 -*-

# daemon/runner.py
# Part of python-daemon, an implementation of PEP 3143.
#
# Copyright © 2009–2010 Ben Finney <ben+python@benfinney.id.au>
# Copyright © 2007–2008 Robert Niederreiter, Jens Klein
# Copyright © 2003 Clark Evans
# Copyright © 2002 Noah Spurrier
# Copyright © 2001 Jürgen Hermann
#
# This is free software: you may copy, modify, and/or distribute this work
# under the terms of the Python Software Foundation License, version 2 or
# later as published by the Python Software Foundation.
# No warranty expressed or implied. See the file LICENSE.PSF-2 for details.

"""Daemon runner library."""

# Standard modules
import errno
import os
import signal
import sys
import time

# Custom modules
from . import daemon
from . import pidlockfile

MIN_SYS_ARGS = 2


class DaemonRunnerError(Exception):
  """Abstract base class for errors from DaemonRunner. """


class DaemonRunnerInvalidActionError(ValueError, DaemonRunnerError):
  """Raised when specified action for DaemonRunner is invalid. """


class DaemonRunnerStartFailureError(RuntimeError, DaemonRunnerError):
  """Raised when failure starting DaemonRunner. """


class DaemonRunnerStopFailureError(RuntimeError, DaemonRunnerError):
  """Raised when failure stopping DaemonRunner. """


class DaemonRunner(object):
  """Controller for a callable running in a separate background process.

  The first command-line argument is the action to take:

  * 'start': Become a daemon and call `app.Run()`.
  * 'stop': Exit the daemon process specified in the PID file.
  * 'restart': Stop, then start.
  """
  def __init__(self, app):
    """Set up the parameters of a new runner.

    The `app` argument must have the following attributes:

    * `argv`: None, or a list of commandline arguments.

    * `stdin_path`, `stdout_path`, `stderr_path`: Filesystem
      paths to open and replace the existing `sys.stdin`,
      `sys.stdout`, `sys.stderr`.

    * `pidfile_path`: Absolute filesystem path to a file that
      will be used as the PID file for the daemon.

    * `pidfile_timeout`: Used as the default acquisition
      timeout value supplied to the runner's PID lock file.

    * `Run`: Callable that will be invoked when the daemon is
      started.
    """
    self.action = None
    self.app = app
    self.pidfile = MakePidlockfile(app.pidfile_path, app.pidfile_timeout)

    self.daemon_context = daemon.DaemonContext(
        chroot_directory=app.chroot_dir,
        working_directory=app.working_dir,
        umask=app.umask,
        pidfile=self.pidfile,
        stdin=open(app.stdin_path, 'r'),
        stdout=open(app.stdout_path, 'a+'),
        stderr=open(app.stderr_path, 'a+', buffering=0))

  def _DoAction(self):
    """Perform the requested action.

    Raises ``DaemonRunnerInvalidActionError`` if the action is
    unknown.
    """
    if self.action not in self.ACTIONS:
      raise DaemonRunnerInvalidActionError('Unknown action: %r' % self.action)
    self.ACTIONS[self.action](self)

  def _ParseArgs(self, argv=None):
    """Parse command-line arguments."""
    argv = argv or sys.argv
    if len(argv) < MIN_SYS_ARGS or argv[1] not in self.ACTIONS:
      self.Usage(argv)
      sys.exit(2)  # Syntax error in call
    self.action = argv[1]

  def _TerminateDaemonProcess(self):
    """Terminate the daemon process specified in the current PID file."""
    pid = self.pidfile.read_pid()
    sys.stdout.write('Stopping ..')
    try:
      os.kill(pid, signal.SIGTERM)
    except OSError, exc:
      raise DaemonRunnerStopFailureError(
        'Failed to terminate %d: %s' % (pid, exc))
    for _index in xrange(16):
      if not self.pidfile.is_locked():
        break
      sys.stdout.write('.')
      sys.stdout.flush()
      time.sleep(.5)
    else:
      # Application does not respond after 8 seconds.
      # Sending SIGKILL and removing lock/pid files.
      os.kill(pid, signal.SIGKILL)
      self.pidfile.break_lock()
    sys.stdout.write('\n')

  def Execute(self):
    self._ParseArgs()
    self._DoAction()

  def Restart(self):
    """Stop, then start."""
    self.Stop()
    self.Start()

  def Start(self):
    """Open the daemon context and run the application."""
    if IsPidfileStale(self.pidfile):
      self.pidfile.break_lock()

    EmitMessage('Starting ...')
    try:
      self.daemon_context.open()
    except (pidlockfile.AlreadyLocked, pidlockfile.LockTimeout):
      raise DaemonRunnerStartFailureError(
        'PID file %r already locked' % self.pidfile.path)
    EmitMessage('started with pid %d' % os.getpid())
    self.app.Run()

  def Stop(self):
    """Exit the daemon process specified in the current PID file."""
    if not self.pidfile.is_locked():
      raise DaemonRunnerStopFailureError(
          'PID file %r is not locked.' % self.pidfile.path)

    if IsPidfileStale(self.pidfile):
      self.pidfile.break_lock()
    else:
      self._TerminateDaemonProcess()

  ACTIONS = {'start': Start, 'stop': Stop, 'restart': Restart}

  def Usage(self, argv):
    """Emit a usage message, then exit."""
    EmitMessage('Usage: %s %s' % (
        os.path.basename(argv[0]), ' | '.join(self.ACTIONS)))


def EmitMessage(message, stream=sys.stderr):
  """Emit a message to the specified stream (default `sys.stderr`). """
  stream.write('%s\n' % message)
  stream.flush()


def MakePidlockfile(path, acquire_timeout):
  """Make a PIDLockFile instance with the given filesystem path. """
  if not isinstance(path, basestring):
    raise ValueError('Not a filesystem path: %r' % path)
  if not os.path.isabs(path):
    raise ValueError('Not an absolute path: %r' % path)
  return pidlockfile.TimeoutPIDLockFile(path, acquire_timeout)


def IsPidfileStale(pidfile):
  """Determine whether a PID file is stale.

  Return ``True`` (“stale”) if the contents of the PID file are
  valid but do not match the PID of a currently-running process;
  otherwise return ``False``.
  """
  pidfile_pid = pidfile.read_pid()
  if pidfile_pid is not None:
    try:
      os.kill(pidfile_pid, signal.SIG_DFL)
    except OSError, exc:
      if exc.errno == errno.ESRCH:
        # The specified PID does not exist
        return True
  return False
