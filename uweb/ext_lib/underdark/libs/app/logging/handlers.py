# Copyright 2001-2007 by Vinay Sajip. All Rights Reserved.
#
# Permission to use, copy, modify, and distribute this software and its
# documentation for any purpose and without fee is hereby granted,
# provided that the above copyright notice appear in all copies and that
# both that copyright notice and this permission notice appear in
# supporting documentation, and that the name of Vinay Sajip
# not be used in advertising or publicity pertaining to distribution
# of the software without specific, written prior permission.
# VINAY SAJIP DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING
# ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL
# VINAY SAJIP BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR
# ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER
# IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
# OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
"""Handlers for the logging package for Python.

The core package is based on PEP 282 and comments thereto in comp.lang.python,
and influenced by Apache's log4j system.

Copyright (C) 2001-2009 Vinay Sajip. All Rights Reserved.

To use, simply 'import logging.handlers' and log away!
"""
from __future__ import with_statement

__author__  = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.2.5'

# Standard modules
from stat import ST_DEV, ST_INO
import cPickle
import datetime
import email.utils
import httplib
import os
import re
import smtplib
import socket
import struct
import time
import traceback
import urllib
import warnings

# Package modules
from underdark.libs.app import logging

DEFAULT_TCP_LOGGING_PORT = 9020
DEFAULT_UDP_LOGGING_PORT = 9021
DEFAULT_HTTP_LOGGING_PORT = 9022
DEFAULT_SOAP_LOGGING_PORT = 9023
SYSLOG_UDP_PORT = 514

_MIDNIGHT = 24 * 60 * 60  # number of seconds in a day


class BaseRotatingHandler(logging.FileHandler):
  """Base class for handlers that rotate log files at a certain point.
  Not meant to be instantiated directly.  Instead, use RotatingFileHandler
  or TimedRotatingFileHandler.
  """
  def __init__(self, filename, mode, encoding=None):
    """Use the specified filename for streamed logging"""
    super(BaseRotatingHandler, self).__init__(filename, mode, encoding)
    self.mode = mode
    self.encoding = encoding

  def DoRollover(self):
    raise NotImplementedError

  def Emit(self, record):
    """Emit a record.

    Output the record to the file, catering for rollover as described
    in DoRollover().
    """
    try:
      if self.ShouldRollover(record):
        self.DoRollover()
      super(BaseRotatingHandler, self).Emit(record)
    except Exception:
      self.HandleError(record)

  def ShouldRollover(self, _record):
    raise NotImplementedError


class RotatingFileHandler(BaseRotatingHandler):
  """Handler for logging to a set of files, which switches from one file
  to the next when the current file reaches a certain size.
  """
  def __init__(self, filename, mode='a', max_bytes=0,
               backup_count=0, encoding=None):
    """Open the specified file and use it as the stream for logging.

    By default, the file grows indefinitely. You can specify particular
    values of maxBytes and backupCount to allow the file to rollover at
    a predetermined size.

    Rollover occurs whenever the current log file is nearly maxBytes in
    length. If backupCount is >= 1, the system will successively create
    new files with the same pathname as the base file, but with extensions
    '.1', '.2' etc. appended to it. For example, with a backupCount of 5
    and a base file name of 'app.log', you would get 'app.log',
    'app.log.1', 'app.log.2', ... through to 'app.log.5'. The file being
    written to is always 'app.log' - when it gets filled up, it is closed
    and renamed to 'app.log.1', and if files 'app.log.1', 'app.log.2' etc.
    exist, then they are renamed to 'app.log.2', 'app.log.3' etc.
    respectively.

    If maxBytes is zero, rollover never occurs.
    """
    if max_bytes > 0:
      mode = 'a' # doesn't make sense otherwise!
    super(RotatingFileHandler, self).__init__(filename, mode, encoding)
    self.max_bytes = max_bytes
    self.backup_count = backup_count

  def DoRollover(self):
    """Do a rollover, as described in __init__()."""
    self.stream.close()
    if self.backup_count > 0:
      for i in reversed(range(1, self.backup_count)):
        sfn = '%s.%d' % (self.filename, i)
        dfn = '%s.%d' % (self.filename, i + 1)
        if os.path.exists(sfn):
          #print '%s -> %s' % (sfn, dfn)
          if os.path.exists(dfn):
            os.remove(dfn)
          os.rename(sfn, dfn)
      dfn = self.filename + '.1'
      if os.path.exists(dfn):
        os.remove(dfn)
      os.rename(self.filename, dfn)
      #print '%s -> %s' % (self.baseFilename, dfn)
    self.mode = 'w'
    self.stream = self._Open()

  def ShouldRollover(self, record):
    """Determine if rollover should occur.

    Basically, see if the supplied record would cause the file to exceed
    the size limit we have.
    """
    if self.max_bytes > 0:           # are we rolling over?
      msg = '%s\n' % self.Format(record)
      self.stream.seek(0, 2)  #due to non-posix-compliant Windows feature
      if self.stream.tell() + len(msg) >= self.max_bytes:
        return True
    return False


class TimedRotatingFileHandler(BaseRotatingHandler):
  """Handler for logging to a file, rotating the log file at certain timed
  intervals.

  If backupCount is > 0, when rollover is done, no more than backupCount
  files are kept - the oldest ones are deleted.
  """
  def __init__(self, filename, when='h', interval=1, backup_count=0,
        encoding=None, utc=0):
    super(TimedRotatingFileHandler, self).__init__(filename, 'a', encoding)
    self.when = when.upper()
    self.backup_count = backup_count
    self.utc = utc
    # Calculate the real rollover interval, which is just the number of
    # seconds between rollovers.  Also set the filename suffix used when
    # a rollover occurs.  Current 'when' events supported:
    # S - Seconds
    # M - Minutes
    # H - Hours
    # D - Days
    # midnight - roll over at midnight
    # W{0-6} - roll over on a certain day; 0 - Monday
    #
    # Case of the 'when' specifier is not important; lower or upper case
    # will work.
    if self.when == 'S':
      self.interval = 1 # one second
      self.suffix = '%Y-%m-%d_%H-%M-%S'
      self.ext_match = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$')
    elif self.when == 'M':
      self.interval = 60 # one minute
      self.suffix = '%Y-%m-%d_%H-%M'
      self.ext_match = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}$')
    elif self.when == 'H':
      self.interval = 60 * 60 # one hour
      self.suffix = '%Y-%m-%d_%H'
      self.ext_match = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{2}$')
    elif self.when == 'D' or self.when == 'MIDNIGHT':
      self.interval = 60 * 60 * 24 # one day
      self.suffix = '%Y-%m-%d'
      self.ext_match = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    elif self.when.startswith('W'):
      self.interval = 60 * 60 * 24 * 7 # one week
      if len(self.when) != 2:
        raise ValueError('You must specify a day for weekly rollover from '
                         '0 to 6 (0 is Monday): %r' % self.when)
      if self.when[1] < '0' or self.when[1] > '6':
        raise ValueError('Invalid day specified for weekly rollover: %r' %
                         self.when)
      self.weekday = int(self.when[1])
      self.suffix = '%Y-%m-%d'
      self.ext_match = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    else:
      raise ValueError('Invalid rollover interval specified: %s' % self.when)

    self.interval = self.interval * interval # multiply by units requested
    self.rollover_time = self.ComputeRollover(int(time.time()))

  def ComputeRollover(self, current_time):
    """Work out the rollover time based on the specified time."""
    result = current_time + self.interval
    # If we are rolling over at midnight or weekly, then the interval is already
    # known. What we need to figure out is WHEN the next interval is.  In other
    # words, if you are rolling over at midnight, then your base interval is 1
    # day but you want to start that one day clock at midnight, not now. So, we
    # have to fudge the rolloverAt value in order to trigger the first rollover
    # at the right time.  After that, the regular interval will take care of
    # the rest.  Note that this code doesn't care about leap seconds. :)
    if self.when == 'MIDNIGHT' or self.when.startswith('W'):
      # This could be done with less code, but I wanted it to be clear
      if self.utc:
        time_tuple = time.gmtime(current_time)
      else:
        time_tuple = time.localtime(current_time)
      hour, minute, second = time_tuple[3:6]
      remaining = _MIDNIGHT - ((hour * 60 + minute) * 60 + second)
      result = current_time + remaining
      # If we are rolling over on a certain day, add in the number of days until
      # the next rollover, but offset by 1 since we just calculated the time
      # until the next day starts.  There are three cases:
      # Case 1) The day to rollover is today; in this case, do nothing
      # Case 2) The day to rollover is further in the interval (i.e., today is
      #     day 2 (Wednesday) and rollover is on day 6 (Sunday).  Days to
      #     next rollover is simply 6 - 2 - 1, or 3.
      # Case 3) The day to rollover is behind us in the interval (i.e., today
      #     is day 5 (Saturday) and rollover is on day 3 (Thursday).
      #     Days to rollover is 6 - 5 + 3, or 4.  In this case, it's the
      #     number of days left in the current week (1) plus the number
      #     of days in the next week until the rollover day (3).
      # The calculations described in 2) and 3) above need to have a day added.
      # This is because the above time calculation takes us to midnight on this
      # day, i.e. the start of the next day.
      if self.when.startswith('W'):
        day = time_tuple[6] # 0 is Monday
        if day != self.weekday:
          if day < self.weekday:
            days_to_wait = self.weekday - day
          else:
            days_to_wait = 6 - day + self.weekday + 1
          new_rollover_at = result + (days_to_wait * (60 * 60 * 24))
          if not self.utc:
            dst_now = time_tuple[-1]
            dst_at_rollover = time.localtime(new_rollover_at)[-1]
            if dst_now != dst_at_rollover:
              if not dst_now:
                # DST kicks in before next rollover, so we deduct an hour
                new_rollover_at -= 3600
              else:
                # DST bows out before next rollover, so we add an hour
                new_rollover_at += 3600
          result = new_rollover_at
    return result

  def DoRollover(self):
    """do a rollover; in this case, a date/time stamp is appended to the
    filename when the rollover happens. However, you want the file to be named
    for the start of the interval, not the current time. If there is a backup
    count, then we have to get a list of matching filenames, sort them and
    remove the one with the oldest suffix.
    """
    if self.stream:
      self.stream.close()
    # get the time that this sequence started at and make it a timetuple
    begin_time = self.rollover_time - self.interval
    if self.utc:
      time_tuple = time.gmtime(begin_time)
    else:
      time_tuple = time.localtime(begin_time)
    dfn = self.filename + '.' + time.strftime(self.suffix, time_tuple)
    if os.path.exists(dfn):
      os.remove(dfn)
    os.rename(self.filename, dfn)
    if self.backup_count > 0:
      # find the oldest log file and delete it
      #s = glob.glob(self.baseFilename + '.20*')
      #if len(s) > self.backupCount:
      #  s.sort()
      #  os.remove(s[0])
      for filename in self.GetFilesToDelete():
        os.remove(filename)
    #print '%s -> %s' % (self.baseFilename, dfn)
    self.mode = 'w'
    self.stream = self._Open()
    current_time = int(time.time())
    new_rollover_at = self.ComputeRollover(current_time)
    while new_rollover_at <= current_time:
      new_rollover_at += self.interval
    # If DST changes and midnight or weekly rollover, adjust for this.
    if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
      dst_now = time.localtime(current_time)[-1]
      dst_at_rollover = time.localtime(new_rollover_at)[-1]
      if dst_now != dst_at_rollover:
        if not dst_now:
          # DST kicks in before next rollover, so we deduct an hour
          new_rollover_at -= 3600
        else:
          # DST bows out before next rollover, so we add an hour
          new_rollover_at += 3600
    self.rollover_time = new_rollover_at

  def GetFilesToDelete(self):
    """Determine the files to delete when rolling over.

    More specific than the earlier method, which just used glob.glob().
    """
    dir_name, base_name = os.path.split(self.filename)
    file_names = os.listdir(dir_name)
    result = []
    prefix = base_name + '.'
    plen = len(prefix)
    for file_name in file_names:
      if file_name[:plen] == prefix:
        suffix = file_name[plen:]
        if self.ext_match.match(suffix):
          result.append(os.path.join(dir_name, file_name))
    result.sort()
    if len(result) < self.backup_count:
      del result[:]
    else:
      result = result[:len(result) - self.backup_count]
    return result

  def ShouldRollover(self, _record):
    """Determine if rollover should occur.

    record is not used, as we are just comparing times, but it is needed so
    the method signatures are the same
    """
    now = int(time.time())
    if now >= self.rollover_time:
      return True
    return False


class WatchedFileHandler(logging.FileHandler):
  """A handler for logging to a file, which watches the file
  to see if it has changed while in use. This can happen because of
  usage of programs such as newsyslog and logrotate which perform
  log file rotation. This handler, intended for use under Unix,
  watches the file to see if it has changed since the last emit.
  (A file has changed if its device or inode have changed.)
  If it has changed, the old file stream is closed, and the file
  opened to get a new stream.

  This handler is not appropriate for use under Windows, because
  under Windows open files cannot be moved or renamed - logging
  opens the files with exclusive locks - and so there is no need
  for such a handler. Furthermore, ST_INO is not supported under
  Windows; stat always returns zero for this value.

  This handler is based on a suggestion and patch by Chad J.
  Schroeder.
  """
  def __init__(self, filename, mode='a', encoding=None):
    super(WatchedFileHandler, self).__init__(filename, mode, encoding)
    if not os.path.exists(self.filename):
      self.dev, self.ino = -1, -1
    else:
      stat = os.stat(self.filename)
      self.dev, self.ino = stat[ST_DEV], stat[ST_INO]

  def Emit(self, record):
    """Emit a record.

    First check if the underlying file has changed, and if it
    has, close the old stream and reopen the file to get the
    current stream.
    """
    if not os.path.exists(self.filename):
      stat = None
      changed = 1
    else:
      stat = os.stat(self.filename)
      changed = (stat[ST_DEV] != self.dev) or (stat[ST_INO] != self.ino)
    if changed and self.stream is not None:
      self.stream.flush()
      self.stream.close()
      self.stream = self._Open()
      if stat is None:
        stat = os.stat(self.filename)
      self.dev, self.ino = stat[ST_DEV], stat[ST_INO]
    super(WatchedFileHandler).Emit(record)


class SocketHandler(logging.Handler):
  """A handler class which writes logging records, in pickle format, to
  a streaming socket. The socket is kept open across logging calls.
  If the peer resets it, an attempt is made to reconnect on the next call.
  The pickle which is sent is that of the LogRecord's attribute dictionary,
  so that the receiver does not need to have the logging module
  installed in order to process the logging event.

  To unpickle the record at the receiving end into a LogRecord, use the
  makeLogRecord function.
  """
  def __init__(self, host, port):
    """Initializes the handler with a specific host address and port.

    The attribute 'close_on_error' is set to 1 - which means that if
    a socket error occurs, the socket is silently closed and then
    reopened on the next logging call.
    """
    super(SocketHandler, self).__init__()
    self.host = host
    self.port = port
    self.sock = None
    self.close_on_error = 0
    self.retry_time = time.time()

    # Exponential backoff parameters.
    self.retry_period = 0.5
    self.retry_max = 30.0
    self.retry_factor = 2.0

  def Close(self):
    """Closes the socket."""
    if self.sock:
      self.sock.close()
      self.sock = None
    super(SocketHandler, self).Close()

  def CreateSocket(self):
    """Try to create a socket, using an exponential backoff with
    a max retry time. Thanks to Robert Olson for the original patch
    (SF #815911) which has been slightly refactored.
    """
    now = time.time()
    if not self.retry_time or now >= self.retry_time:
      try:
        self.sock = self.MakeSocket()
        self.retry_time = now # next time, no delay before trying
        self.retry_period = 1.0
      except socket.error:
        #Creation failed, so set the retry time and return.
        self.retry_period = max(self.retry_period * self.retry_factor,
                                self.retry_max)
        self.retry_time = now + self.retry_period

  def Emit(self, record):
    """Emit a record.

    Pickles the record and writes it to the socket in binary format.
    If there is an error with the socket, silently drop the packet.
    If there was a problem with the socket, re-establishes the
    socket.
    """
    try:
      self.Send(self.MakePickle(record))
    except Exception:
      self.HandleError(record)

  def HandleError(self, record):
    # [Arguments number differs from overridden method]
    # The baseclass uses a @staticmethod for this method, which we do not here.
    # pylint: disable-msg=W0221
    """Handle an error during logging.

    An error has occurred during logging. Most likely cause -
    connection lost. Close the socket so that we can retry on the
    next event.
    """
    if self.close_on_error and self.sock:
      self.sock.close()
      self.sock = None  # try to reconnect next time
    else:
      super(SocketHandler, self).HandleError(record)

  def MakePickle(self, record):
    """Pickles the record in binary format with a length prefix, and
    returns it ready for transmission across the socket.
    """
    exc_info = record.exc_info
    if exc_info:
      self.Format(record) # To get traceback text into record.exc_text
      record.exc_info = None  # to avoid Unpickleable error
    record_string = cPickle.dumps(vars(record), 1)
    if exc_info:
      # The next handler should have this information back.
      record.exc_info = exc_info
    slen = struct.pack('>L', len(record_string))
    return slen + record_string

  def MakeSocket(self, timeout=1):
    """A factory method which allows subclasses to define the precise
    type of socket they want.
    """
    requested_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(requested_socket, 'settimeout'):
      requested_socket.settimeout(timeout)
    requested_socket.connect((self.host, self.port))
    return requested_socket

  def Send(self, record_string):
    """Send a pickled string to the socket.

    This function allows for partial sends which can happen when the
    network is busy.
    """
    if self.sock is None:
      self.CreateSocket()
    # self.sock can be None either because we haven't reached the retry
    # time yet, or because we have reached the retry time and retried,
    # but are still unable to connect.
    if self.sock:
      try:
        if hasattr(self.sock, 'sendall'):
          self.sock.sendall(record_string)
        else:
          sentsofar = 0
          left = len(record_string)
          while left:
            sent = self.sock.send(record_string[sentsofar:])
            sentsofar += sent
            left -= sent
      except socket.error:
        self.sock.close()
        self.sock = None  # so we can call CreateSocket next time


class DatagramHandler(SocketHandler):
  """A handler class which writes logging records, in pickle format, to
  a datagram socket.  The pickle which is sent is that of the LogRecord's
  attribute dictionary, so that the receiver does not need to
  have the logging module installed in order to process the logging event.

  To unpickle the record at the receiving end into a LogRecord, use the
  makeLogRecord function.
  """
  def __init__(self, host, port):
    """Initializes the handler with a specific host address and port."""
    super(DatagramHandler, self).__init__(host, port)
    self.close_on_error = 0

  def MakeSocket(self, _timeout=None):
    """The factory method of SocketHandler is here overridden to create
    a UDP socket (SOCK_DGRAM).
    """
    return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

  def Send(self, record_string):
    """Send a pickled string to a socket.

    This function no longer allows for partial sends which can happen
    when the network is busy - UDP does not guarantee delivery and
    can deliver packets out of sequence.
    """
    if self.sock is None:
      self.CreateSocket()
    self.sock.sendto(record_string, (self.host, self.port))


class SysLogHandler(logging.Handler):
  """A handler class which sends formatted logging records to a syslog
  server. Based on Sam Rushing's syslog module:
  http://www.nightmare.com/squirl/python-ext/misc/syslog.py
  Contributed by Nicolas Untz (after which minor refactoring changes
  have been made).
  """
  # from <linux/sys/syslog.h>:
  # ======================================================================
  # priorities/facilities are encoded into a single 32-bit quantity, where
  # the bottom 3 bits are the priority (0-7) and the top 28 bits are the
  # facility (0-big number). Both the priorities and the facilities map
  # roughly one-to-one to strings in the syslogd(8) source code.  This
  # mapping is included in this file.
  #
  # priorities (these are ordered)

  LOG_EMERG   = 0     #  system is unusable
  LOG_ALERT   = 1     #  action must be taken immediately
  LOG_CRIT    = 2     #  critical conditions
  LOG_ERR     = 3     #  error conditions
  LOG_WARNING = 4     #  warning conditions
  LOG_NOTICE  = 5     #  normal but significant condition
  LOG_INFO    = 6     #  informational
  LOG_DEBUG   = 7     #  debug-level messages

  #  facility codes
  LOG_KERN   = 0     #  kernel messages
  LOG_USER   = 1     #  random user-level messages
  LOG_MAIL   = 2     #  mail system
  LOG_DAEMON = 3     #  system daemons
  LOG_AUTH   = 4     #  security/authorization messages
  LOG_SYSLOG = 5     #  messages generated internally by syslogd
  LOG_LPR    = 6     #  line printer subsystem
  LOG_NEWS   = 7     #  network news subsystem
  LOG_UUCP   = 8     #  UUCP subsystem
  LOG_CRON   = 9     #  clock daemon
  LOG_AUTHPRIV = 10  #  security/authorization messages (private)

  #  other codes through 15 reserved for system use
  LOG_LOCAL0 = 16    #  reserved for local use
  LOG_LOCAL1 = 17    #  reserved for local use
  LOG_LOCAL2 = 18    #  reserved for local use
  LOG_LOCAL3 = 19    #  reserved for local use
  LOG_LOCAL4 = 20    #  reserved for local use
  LOG_LOCAL5 = 21    #  reserved for local use
  LOG_LOCAL6 = 22    #  reserved for local use
  LOG_LOCAL7 = 23    #  reserved for local use

  PRIORITY_NAMES = {
    'alert': LOG_ALERT,
    'crit': LOG_CRIT,
    'critical': LOG_CRIT,
    'debug': LOG_DEBUG,
    'emerg': LOG_EMERG,
    'err': LOG_ERR,
    'error': LOG_ERR,    #  DEPRECATED
    'info': LOG_INFO,
    'notice': LOG_NOTICE,
    'panic': LOG_EMERG,    #  DEPRECATED
    'warn': LOG_WARNING,  #  DEPRECATED
    'warning': LOG_WARNING}

  FACILITY_NAMES = {
    'auth': LOG_AUTH,
    'authpriv': LOG_AUTHPRIV,
    'cron': LOG_CRON,
    'daemon': LOG_DAEMON,
    'kern': LOG_KERN,
    'lpr': LOG_LPR,
    'mail': LOG_MAIL,
    'news': LOG_NEWS,
    'security': LOG_AUTH,     #  DEPRECATED
    'syslog': LOG_SYSLOG,
    'user': LOG_USER,
    'uucp': LOG_UUCP,
    'local0': LOG_LOCAL0,
    'local1': LOG_LOCAL1,
    'local2': LOG_LOCAL2,
    'local3': LOG_LOCAL3,
    'local4': LOG_LOCAL4,
    'local5': LOG_LOCAL5,
    'local6': LOG_LOCAL6,
    'local7': LOG_LOCAL7}

  #The map below appears to be trivially lowercasing the key. However,
  #there's more to it than meets the eye - in some locales, lowercasing
  #gives unexpected results. See SF #1524081: in the Turkish locale,
  #'INFO'.lower() != 'info'
  PRIORITY_MAP = {
    'DEBUG' : 'debug',
    'INFO' : 'info',
    'WARNING' : 'warning',
    'ERROR' : 'error',
    'CRITICAL' : 'critical'}

  # curious: when talking to the unix-domain '/dev/log' socket, a
  # zero-terminator seems to be required.  this string is placed
  # into a class variable so that it can be overridden if
  # necessary.
  LOG_FORMAT_STRING = '<%d>%s\000'

  def __init__(self, address=('localhost', SYSLOG_UDP_PORT), facility=LOG_USER):
    """Initialize a handler.

    If address is specified as a string, a UNIX socket is used. To log to a
    local syslogd, 'SysLogHandler(address='/dev/log')' can be used.
    If facility is not specified, LOG_USER is used.
    """
    super(SysLogHandler, self).__init__()
    self.address = address
    self.facility = facility
    if isinstance(address, str):
      self.unixsocket = 1
      self._ConnectUnixsocket(address)
    else:
      self.unixsocket = 0
      self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.formatter = None

  def _ConnectUnixsocket(self, address):
    self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    # syslog may require either DGRAM or STREAM sockets
    try:
      self.socket.connect(address)
    except socket.error:
      self.socket.close()
      self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
      self.socket.connect(address)

  def Close (self):
    """Closes the socket."""
    if self.unixsocket:
      self.socket.close()
    super(SysLogHandler, self).Close()

  def Emit(self, record):
    """Emit a record.

    The record is formatted, and then sent to the syslog server. If
    exception information is present, it is NOT sent to the server.
    """
    msg = self.LOG_FORMAT_STRING % (
        self.EncodePriority(self.facility, self.MapPriority(record.levelname)),
        self.Format(record))
    try:
      if self.unixsocket:
        try:
          self.socket.send(msg)
        except socket.error:
          self._ConnectUnixsocket(self.address)
          self.socket.send(msg)
      else:
        self.socket.sendto(msg, self.address)
    except Exception:
      self.HandleError(record)

  def EncodePriority(self, facility, priority):
    """Encode the facility and priority. You can pass in strings or
    integers - if strings are passed, the FACILITY_NAMES and
    PRIORITY_NAMES mapping dictionaries are used to convert them to
    integers.
    """
    if isinstance(facility, str):
      facility = self.FACILITY_NAMES[facility]
    if isinstance(priority, str):
      priority = self.PRIORITY_NAMES[priority]
    return (facility << 3) | priority

  def MapPriority(self, level_name):
    """Map a logging level name to a key in the PRIORITY_NAMES map.
    This is useful in two scenarios: when custom levels are being
    used, and in the case where you can't do a straightforward
    mapping by lowercasing the logging level name because of locale-
    specific issues (see SF #1524081).
    """
    return self.PRIORITY_MAP.get(level_name, 'warning')


class SMTPHandler(logging.Handler):
  """A handler class which sends an SMTP email for each logging event."""

  WEEKDAYNAME = 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'
  MONTHNAME = (None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')

  def __init__(self, mailhost, fromaddr, toaddrs, subject, credentials=None):
    """Initialize the handler.

    Initialize the instance with the from and to addresses and subject
    line of the email. To specify a non-standard SMTP port, use the
    (host, port) tuple format for the mailhost argument. To specify
    authentication credentials, supply a (username, password) tuple
    for the credentials argument.
    """
    super(SMTPHandler, self).__init__()
    if isinstance(mailhost, tuple):
      self.mailhost, self.mailport = mailhost
    else:
      self.mailhost, self.mailport = mailhost, None
    if isinstance(credentials, tuple):
      self.username, self.password = credentials
    else:
      self.username = None
    self.fromaddr = fromaddr
    if isinstance(toaddrs, str):
      toaddrs = [toaddrs]
    self.toaddrs = toaddrs
    self.subject = subject

  def DateTime(self):
    """Return the current date and time formatted for a MIME header.
    Needed for Python 1.5.2 (no email package available)
    """
    (year, month, day, hour, minute,
     second, weekday, _daynum, _dst) = time.gmtime()
    return ('%s, %02d %3s %4d %02d:%02d:%02d GMT' % (
            self.WEEKDAYNAME[weekday],
            day, self.MONTHNAME[month], year,
            hour, minute, second))

  def Emit(self, record):
    """Emit a record.

    Format the record and send it to the specified addressees.
    """
    try:
      port = self.mailport
      if not port:
        port = smtplib.SMTP_PORT
      smtp = smtplib.SMTP(self.mailhost, port)
      msg = self.Format(record)
      msg = 'From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\n\r\n%s' % (
              self.fromaddr,
              ','.join(self.toaddrs),
              self.GetSubject(record),
              email.utils.formatdate(), msg)
      if self.username:
        smtp.login(self.username, self.password)
      smtp.sendmail(self.fromaddr, self.toaddrs, msg)
      smtp.quit()
    except Exception:
      self.HandleError(record)

  def GetSubject(self, _record):
    """Determine the subject for the email.

    If you want to specify a subject line which is record-dependent,
    override this method.
    """
    return self.subject


class HTTPHandler(logging.Handler):
  """A class which sends records to a Web server, using either GET or POST."""
  def __init__(self, host, url, method='GET'):
    """Initialize the instance with the host, the request URL, and method."""
    super(HTTPHandler, self).__init__()
    method = method.upper()
    if method not in ('GET', 'POST'):
      raise ValueError('method must be GET or POST')
    self.host = host
    self.url = url
    self.method = method

  def Emit(self, record):
    """Emit a record.

    Send the record to the Web server as an URL-encoded dictionary
    """
    try:
      host = self.host
      http_handler = httplib.HTTP(host)
      url = self.url
      data = urllib.urlencode(self.MapLogRecord(record))
      if self.method == 'GET':
        if url.find('?') >= 0:
          sep = '&'
        else:
          sep = '?'
        url += sep + data
      http_handler.putrequest(self.method, url)
      # support multiple hosts on one IP address...
      # need to strip optional :port from host, if present
      i = host.find(':')
      if i >= 0:
        host = host[:i]
      http_handler.putheader('Host', host)
      if self.method == 'POST':
        http_handler.putheader('Content-type',
                               'application/x-www-form-urlencoded')
        http_handler.putheader('Content-length', str(len(data)))
      http_handler.endheaders()
      if self.method == 'POST':
        http_handler.send(data)
      http_handler.getreply()  #can't do anything with the result
    except Exception:
      self.HandleError(record)

  @staticmethod
  def MapLogRecord(record):
    """Default implementation of mapping the log record into a dict
    that is sent as the CGI data. Overwrite in your class.
    Contributed by Franz Glasner.
    """
    return vars(record)


class BufferingHandler(logging.Handler):
  """A handler class which buffers logging records in memory. Whenever each
  record is added to the buffer, a check is made to see if the buffer should
  be flushed. If it should, then Flush() is expected to do what's needed.
  """
  def __init__(self, capacity):
    """Initialize the handler with the buffer size."""
    super(BufferingHandler, self).__init__()
    self.capacity = capacity
    self.buffer = []

  def Close(self):
    """Flushes the buffer and closes the handler."""
    self.Flush()
    super(BufferingHandler, self).Close()

  def Emit(self, record):
    """Emit a record.

    Append the record. If ShouldFlush() tells us to, call Flush() to process
    the buffer.
    """
    self.buffer.append(record)
    if self.ShouldFlush(record):
      self.Flush()

  def Flush(self):
    """Override to implement custom flushing behaviour.

    This version detroys the contents of the existing buffer.
    """
    del self.buffer[:]

  def ShouldFlush(self, _record):
    """Should the handler flush its buffer?

    Returns true if the buffer is up to capacity. This method can be
    overridden to implement custom flushing strategies.
    """
    return len(self.buffer) >= self.capacity


class PriorityBufferingHandler(BufferingHandler):
  """A handler class which buffers logging records in memory, periodically
  flushing them to a target handler. Flushing occurs whenever the buffer
  is full, or when an event of a certain severity or greater is seen.
  """
  def __init__(self, capacity=10, flush_level=logging.ERROR, target=None):
    """Initialize the handler with the buffer size, the level at which
    flushing should occur and an optional target.

    Note that without a target being set either here or via setTarget(),
    a MemoryHandler is no use to anyone!
    """
    super(PriorityBufferingHandler, self).__init__(capacity)
    self.flush_level = flush_level
    self.target = target

  def Close(self):
    """Flush, set the target to None and lose the buffer."""
    self.Flush()
    self.target = None
    super(PriorityBufferingHandler, self).Close()

  def Flush(self):
    """For a MemoryHandler, flushing means just sending the buffered
    records to the target, if there is one. Override if you want
    different behaviour.
    """
    if self.target:
      for record in self.buffer:
        self.target.Handle(record)
      del self.buffer[:]

  def ShouldFlush(self, record):
    """Check for buffer full or a record at the flush_level or higher."""
    return (len(self.buffer) >= self.capacity or
            record.levelno >= self.flush_level)


class DatabaseHandler(logging.Handler):
  """A logging handler that writes events to a database.

  The expected connection is an SQLTalk instance, with the appropriate cursor.
  API wise, only Insert() calls are required on the cursor.
  """
  def __init__(self, connection):
    super(DatabaseHandler, self).__init__()
    self.connection = connection

  def Close(self):
    self.connection = None
    super(DatabaseHandler, self).Close()

  def Emit(self, record):
    try:
      with self.connection as cursor:
        cursor.Insert(table='logging', values=self.Format(record))
    except Exception, error:
      warnings.warn(
        'Logging record could not be written to the database: %r' % error,
        RuntimeWarning)
      self.HandleError(record)

  def Format(self, record):
    if record.exc_info:
      record.exc_text = ''.join(traceback.format_exception(*record.exc_info))
    return {'logLevel': record.levelname,
            'logLevelNumber': record.levelno,
            'logMessage': record.Message(),
            'logName': record.name,
            'logTime': self.FormatTime(record.created),
            'logTimeRelative': int(record.relative_created),
            'processName': record.processname,
            'processNumber': record.process,
            'threadName': record.threadname,
            'threadNumber': record.thread,
            'fileName': record.filename,
            'filePath': record.pathname,
            'moduleName': record.module,
            'lineNumber': record.lineno,
            'functionName': record.funcname,
            'traceback': record.exc_text}

  @staticmethod
  def FormatTime(epoch_seconds):
    return datetime.datetime.utcfromtimestamp(epoch_seconds)


class BufferingDatabaseHandler(DatabaseHandler):
  def __init__(self, connection, capacity=25, flush_level=logging.ERROR):
    self.buffer = []
    self.capacity = capacity
    self.flush_level = flush_level
    super(BufferingDatabaseHandler, self).__init__(connection)

  def Close(self):
    self.Flush()
    super(BufferingDatabaseHandler, self).Close()

  def Emit(self, record):
    """Emit a record.

    Append the record. If ShouldFlush() tells us to, call Flush() to process
    the buffer.
    """
    self.buffer.append(self.Format(record))
    if self.ShouldFlush(record):
      self.Flush()

  def Flush(self):
    """For a MemoryHandler, flushing means just sending the buffered
    records to the target, if there is one. Override if you want
    different behaviour.
    """
    if not self.buffer:
      return
    try:
      with self.connection as cursor:
        cursor.Insert(table='logging', values=self.buffer)
    except Exception, error:
      warnings.warn(
        'Logging record could not be written to the database: %r' % error,
        RuntimeWarning)
      self.HandleError(None)
    finally:
      del self.buffer[:]

  def ShouldFlush(self, record):
    """Check for buffer full or a record at the flush_level or higher."""
    return (len(self.buffer) >= self.capacity or
            record.levelno >= self.flush_level)
