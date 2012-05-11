# Copyright 2001-2009 by Vinay Sajip. All Rights Reserved.
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
"""Logging package for Python.

Based on PEP 282 and comments thereto in comp.lang.python,
and influenced by Apache's log4j system.

Copyright (C) 2001-2009 Vinay Sajip. All Rights Reserved.

To use, simply 'import logging' and log away!
"""
from __future__ import with_statement

__author__  = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.2.4'

# Standard modules
import atexit
import codecs
import decorator
import os
import sys
import thread
import threading
import time
import traceback

#---------------------------------------------------------------------------
#   Miscellaneous module data
#---------------------------------------------------------------------------

# The filename of the logging package. On the second unedited run, __file__
# will contain a .pyc filename, whereas the inspection still returns .py.
# Not having this variable would cause the wrong stack frames to be grabbed.
if __file__[-4:-1].lower() == '.py':
  _FILENAME = __file__[:-1]
else:
  _FILENAME = __file__

#_startTime is used as the base when calculating the relative time of events
START_TIME = time.time()

# Should exceptions during handling be propagated
RAISE_EXCEPTIONS = True

# If you don't want threading information in the log, set this to zero
LOG_THREADS = True

# If you don't want multiprocessing information in the log, set this to zero
LOG_MULTIPROCESSING = True

# If you don't want process information in the log, set this to zero
LOG_PROCESSES = True

#---------------------------------------------------------------------------
#   Level related stuff
#---------------------------------------------------------------------------
# Default levels and level names, these can be replaced with any positive set
# of values having corresponding names. There is a pseudo-level, NOTSET, which
# is only really there as a lower limit for user-defined levels. Handlers and
# loggers are initialized with NOTSET so that they will log all messages, even
# at user-defined levels.

CRITICAL = 50
ERROR = 40
WARNING = 30
INFO = 20
DEBUG = 10
NOTSET = 0

LEVEL_NAMES = {
  CRITICAL : 'CRITICAL',
  ERROR : 'ERROR',
  WARNING : 'WARNING',
  INFO : 'INFO',
  DEBUG : 'DEBUG',
  NOTSET : 'NOTSET',
  'CRITICAL' : CRITICAL,
  'ERROR' : ERROR,
  'WARNING' : WARNING,
  'INFO' : INFO,
  'DEBUG' : DEBUG,
  'NOTSET' : NOTSET}

def SetLevelName(level, level_name):
  """Associate 'levelName' with 'level'.

  This is used when converting levels to text during message formatting.
  """
  with LOCK:
    LEVEL_NAMES[level] = level_name
    LEVEL_NAMES[level_name] = level

#---------------------------------------------------------------------------
#   Thread-related stuff
#---------------------------------------------------------------------------
# LOCK is used to serialize access to shared data structures in this module.
# This needs to be an RLock because fileConfig() creates Handlers and so
# might arbitrary user threads. Since Handler.__init__() updates the shared
# dictionary _handlers, it needs to acquire the lock. But if configuring,
# the lock would already have been acquired - so we need an RLock.
# The same argument applies to Loggers and Manager.logger_dict.
LOCK = threading.RLock()

#---------------------------------------------------------------------------
#   The logging record
#---------------------------------------------------------------------------

class LogRecord(object):
  """A LogRecord instance represents an event being logged.

  LogRecord instances are created every time something is logged. They
  contain all the information pertinent to the event being logged. The
  main information passed in is in msg and args, which are combined
  using str(msg) % args to create the message field of the record. The
  record also includes information such as when the record was created,
  the source line where the logging call was made, and any exception
  information to be logged.
  """
  def __init__(self, name, level, pathname, lineno,
               msg, args, exc_info, func=None):
    """Initialize a logging record with interesting information."""
    created_time = time.time()
    self.name = name
    self.msg = msg
    if len(args) == 1 and isinstance(args[0], dict):
      args = args[0]
    self.args = args
    self.levelname = LEVEL_NAMES.get(level, ("Level %s" % level))
    self.levelno = level
    self.pathname = pathname
    try:
      self.filename = os.path.basename(pathname)
      self.module = os.path.splitext(self.filename)[0]
    except (AttributeError, TypeError, ValueError):
      self.filename = pathname
      self.module = 'Unknown module'
    self.exc_info = exc_info
    self.exc_text = None  # used to cache the traceback text
    self.lineno = lineno
    self.funcname = func
    self.created = created_time
    self.msecs = (created_time - int(created_time)) * 1000
    self.relative_created = (self.created - START_TIME) * 1000
    if LOG_THREADS:
      self.thread = thread.get_ident()
      try:
        self.threadname = threading.currentThread().getName()
      except AttributeError:
        # Python 2.6 has a revised naming scheme for the `threading` module.
        self.threadname = threading.current_thread().name
    else:
      self.thread = None
      self.threadname = None
    if LOG_MULTIPROCESSING:
      try:
        import multiprocessing
        self.processname = multiprocessing.current_process().name
      except ImportError:
        self.processname = 'MainProcess'
    else:
      self.processname = None
    if LOG_PROCESSES:
      self.process = os.getpid()
    else:
      self.process = None

  def __str__(self):
    return ('<LogRecord: %(name)s, %(levelno)s, %(pathname)s, '
            '%(lineno)s, %(msg)r>' % vars(self))

  def Message(self):
    """Return the message for this LogRecord.

    Return the message for this LogRecord after merging any user-supplied
    arguments with the message.
    """
    if self.args:
      return self.msg % self.args
    return self.msg


#---------------------------------------------------------------------------
#   Formatter classes and functions
#---------------------------------------------------------------------------

class Formatter(object):
  """Formatter instances are used to convert a LogRecord to text.

  Formatters need to know how a LogRecord is constructed. They are
  responsible for converting a LogRecord to (usually) a string which can
  be interpreted by either a human or an external system. The base Formatter
  allows a formatting string to be specified. If none is supplied, the
  default value of "%s(message)\\n" is used.

  The Formatter can be initialized with a format string which makes use of
  knowledge of the LogRecord attributes - e.g. the default value mentioned
  above makes use of the fact that the user's message and arguments are pre-
  formatted into a LogRecord's message attribute. Currently, the useful
  attributes in a LogRecord are described by:

  %(name)s        Name of the logger (logging channel)
  %(levelno)s     Numeric logging level for the message (DEBUG, INFO,
                  WARNING, ERROR, CRITICAL)
  %(levelname)s   Text logging level for the message ("DEBUG", "INFO",
                  "WARNING", "ERROR", "CRITICAL")
  %(pathname)s    Full pathname of the source file where the logging
                  call was issued (if available)
  %(filename)s    Filename portion of pathname
  %(module)s      Module (name portion of filename)
  %(lineno)d      Source line number where the logging call was issued
                  (if available)
  %(funcname)s    Function name
  %(created)f     Time when the LogRecord was created (time.time() return value)
  %(asctime)s     Textual time when the LogRecord was created
  %(msecs)d       Millisecond portion of the creation time
  %(relative_created)d Time in milliseconds when the LogRecord was created,
            relative to the time the logging module was loaded
            (typically at application startup time)
  %(thread)d      Thread ID (if available)
  %(threadname)s  Thread name (if available)
  %(process)d     Process ID (if available)
  %(message)s     The result of record.getMessage(), computed just as
            the record is emitted
  """
  converter = time.gmtime

  def __init__(self, log_format=None, date_format=None):
    """Initialize the formatter with specified format strings.

    Initialize the formatter either with the specified format string, or a
    default as described above. Allow for specialized date formatting with
    the optional datefmt argument (if omitted, you get the ISO8601 format).
    """
    self._format = log_format or BASIC_FORMAT
    self.date_format = date_format

  def Format(self, record):
    """Format the specified record as text.

    The record's attribute dictionary is used as the operand to a
    string formatting operation which yields the returned string.
    Before formatting the dictionary, a couple of preparatory steps
    are carried out. The message attribute of the record is computed
    using LogRecord.Message(). If the formatting string contains
    "%(asctime)", FormatTime() is called to format the event time.
    If there is exception information, it is formatted using
    FormatException() and appended to the message.
    """
    record.message = record.Message()
    if '%(asctime)' in self._format:
      record.asctime = self.FormatTime(record, self.date_format)
    record_string = self._format % vars(record)
    if record.exc_info:
      # Cache the traceback text to avoid converting it multiple times
      # (it's constant anyway)
      if not record.exc_text:
        record.exc_text = self.FormatException(record.exc_info)
    if record.exc_text:
      return record_string.rstrip('\n') + '\n' + record.exc_text
    return record_string

  @staticmethod
  def FormatException(exc_info):
    """Format and return the specified exception information as a string.

    This default implementation just uses
    traceback.format_exception()
    """
    return ''.join(traceback.format_exception(*exc_info))

  def FormatTime(self, record, date_format=None):
    """Return the creation time of the specified LogRecord as formatted text.

    This method should be called from format() by a formatter which
    wants to make use of a formatted time. This method can be overridden
    in formatters to provide for any specific requirement, but the
    basic behaviour is as follows: if datefmt (a string) is specified,
    it is used with time.strftime() to format the creation time of the
    record. Otherwise, the ISO8601 format is used. The resulting
    string is returned. This function uses a user-configurable function
    to convert the creation time to a tuple. By default, time.localtime()
    is used; to change this for a particular formatter instance, set the
    'converter' attribute to a function with the same signature as
    time.localtime() or time.gmtime(). To change it for all formatters,
    for example if you want all logging times to be shown in GMT,
    set the 'converter' attribute in the Formatter class.
    """
    time_obj = self.converter(record.created)
    if date_format:
      string_time = time.strftime(date_format, time_obj)
    else:
      string_time = time.strftime("%Y-%m-%d %H:%M:%S", time_obj)
      string_time = "%s,%03d" % (string_time, record.msecs)
    return string_time


#---------------------------------------------------------------------------
#   Filter classes and functions
#---------------------------------------------------------------------------

class Filter(object):
  """Filter instances are used to perform arbitrary filtering of LogRecords.

  Loggers and Handlers can optionally use Filter instances to filter
  records as desired. The base filter class only allows events which are
  below a certain point in the logger hierarchy. For example, a filter
  initialized with "A.B" will allow events logged by loggers "A.B",
  "A.B.C", "A.B.C.D", "A.B.D" etc. but not "A.BB", "B.A.B" etc. If
  initialized with the empty string, all events are passed.
  """
  def __init__(self, name=''):
    """Initialize a filter.

    Initialize with the name of the logger which, together with its
    children, will have its events allowed through the filter. If no
    name is specified, allow every event.
    """
    self.name = name
    self.nlen = len(name)

  def ShouldLog(self, record):
    """Determine if the specified record is to be logged.

    Is the specified record to be logged? Returns 0 for no, nonzero for
    yes. If deemed appropriate, the record may be modified in-place.
    """
    if self.nlen == 0 or self.name == record.name[:self.nlen]:
      return True
    return record.name[self.nlen] == '.'


class Filterer(object):
  """Base class for loggers and handlers allowing them to share common code."""
  def __init__(self):
    """Initialize the list of filters to be an empty list."""
    self.filters = set()

  def AddFilter(self, fltr):
    """Add the specified filter to this handler."""
    if not fltr in self.filters:
      self.filters.add(fltr)

  def RemoveFilter(self, fltr):
    """Remove the specified filter from this handler."""
    self.filters.discard(fltr)

  def ShouldLog(self, record):
    """Determine if a record is loggable by consulting all the filters.

    The default is to allow the record to be logged; any filter can veto
    this and the record is then dropped. Returns a zero value if a record
    is to be dropped, else non-zero.
    """
    for fltr in self.filters:
      if not fltr.ShouldLog(record):
        return False
    return True

#---------------------------------------------------------------------------
#   Handler classes and functions
#---------------------------------------------------------------------------

class Handler(Filterer):
  """Handler instances dispatch logging events to specific destinations.

  The base handler class. Acts as a placeholder which defines the Handler
  interface. Handlers can optionally use Formatter instances to format
  records as desired. By default, no formatter is specified; in this case,
  the 'raw' message as determined by record.message is logged.
  """
  def __init__(self, level=NOTSET):
    """Initializes the instance - basically setting the formatter to None
    and the filter list to empty.
    """
    super(Handler, self).__init__()
    self.formatter = None
    self.level = level
    self.lock = threading.RLock()

    with LOCK:
      HANDLERS[self] = 1
      HANDLER_LIST.insert(0, self)

  def Close(self):
    """Tidy up any resources used by the handler.

    This version removes the handler from an internal list of handlers which is
    closed when shutdown() is called. Subclasses should ensure that this gets
    called from overridden close() methods.
    """
    # get the module data lock, as we're updating a shared structure.
    with LOCK:
      del HANDLERS[self]
      HANDLER_LIST.remove(self)

  def Emit(self, _record):
    """Do whatever it takes to actually log the specified logging record.

    This version is intended to be implemented by subclasses and so
    raises a NotImplementedError.
    """
    raise NotImplementedError('Emit must be implemented by Handler subclass.')

  def Flush(self):
    """Ensure all logging output has been flushed.

    This version does nothing and is intended to be implemented by
    subclasses.
    """
    pass

  def Format(self, record):
    """Format the specified record.

    If a formatter is set, use it. Otherwise, use the default formatter
    for the module.
    """
    if self.formatter:
      return self.formatter.Format(record)
    return DEFAULT_FORMATTER.Format(record)

  def Handle(self, record):
    """Conditionally emit the specified logging record.

    Emission depends on filters which may have been added to the handler.
    Wrap the actual emission of the record with acquisition/release of
    the I/O thread lock. Returns whether the filter passed the record for
    emission.
    """
    if self.ShouldLog(record):
      with self.lock:
        self.Emit(record)
      return True
    return False

  @staticmethod
  def HandleError(_record):
    """Handle errors which occur during an Emit() call.

    This method should be called from handlers when an exception is
    encountered during an Emit() call. If RAISE_EXCEPTIONS is false,
    exceptions get silently ignored. This is what is mostly wanted
    for a logging system - most users will not care about errors in
    the logging system, they are more interested in application errors.
    You could, however, replace this with a custom handler if you wish.
    The record which was being processed is passed in to this method.
    """
    if RAISE_EXCEPTIONS:
      try:
        traceback.print_exc()
      except IOError:
        pass

  def SetFormatter(self, formatter):
    """Set the formatter for this handler."""
    self.formatter = formatter

  def SetLevel(self, level):
    """Set the logging level of this handler."""
    self.level = level


class StreamHandler(Handler):
  """A handler class which writes logging records to a stream.

  Logging messages are appropriately formatted and sent to the stream.
  Note that this class does not close the stream, as stdout/stderr may be used.
  """
  def __init__(self, stream=None):
    """Initialize the handler.

    If strm is not specified, sys.stderr is used.
    """
    super(StreamHandler, self).__init__()
    if stream is None:
      stream = sys.stderr
    self.stream = stream

  def Emit(self, record):
    """Emit a record.

    If a formatter is specified, it is used to format the record.
    The record is then written to the stream with a trailing newline.  If
    exception information is present, it is formatted using
    traceback.print_exception and appended to the stream.  If the stream
    has an 'encoding' attribute, it is used to encode the message before
    output to the stream.
    """
    stream = self.stream
    try:
      message = self.Format(record) + '\n'
      try:
        if isinstance(message, unicode) and getattr(stream, 'encoding', None):
          message = message.decode(self.stream.encoding)
          try:
            stream.write(message)
          except UnicodeEncodeError:
            # Printing to terminals sometimes fails. For example,
            # with an encoding of 'cp1251', the above write will
            # work if written to a stream opened or wrapped by
            # the codecs module, but fail when writing to a
            # terminal even when the codepage is set to cp1251.
            # An extra encoding step seems to be needed.
            stream.write(message.encode(stream.encoding))
        else:
          stream.write(message)
      except UnicodeError:
        stream.write(message.encode('UTF-8'))
      self.Flush()
    except (KeyboardInterrupt, SystemExit):
      raise
    except:
      self.HandleError(record)

  def Flush(self):
    """Flushes the stream."""
    if self.stream and hasattr(self.stream, 'flush'):
      self.stream.flush()


class FileHandler(StreamHandler):
  """A handler class which writes formatted logging records to disk files."""
  def __init__(self, filename, mode='a', encoding=None):
    """Open the specified file and use it as the stream for logging."""
    # keep the absolute path, otherwise derived classes which use this
    # may come a cropper when the current directory changes
    if codecs is None:
      encoding = None
    self.filename = os.path.abspath(filename)
    self.mode = mode
    self.encoding = encoding
    super(FileHandler, self).__init__(self._Open())

  def _Open(self):
    """Open the current base file with the (original) mode and encoding.

    Return the resulting stream.
    """
    if self.encoding is None:
      stream = open(self.filename, self.mode)
    else:
      stream = codecs.open(self.filename, self.mode, self.encoding)
    return stream

  def Close(self):
    """Closes the stream."""
    if self.stream:
      self.Flush()
      if hasattr(self.stream, 'close'):
        self.stream.close()
      super(FileHandler, self).Close(self)
      self.stream = None


#---------------------------------------------------------------------------
#   Manager classes and functions
#---------------------------------------------------------------------------

class PlaceHolder(object):
  """PlaceHolder instances are used in the Manager logger hierarchy to take
  the place of nodes for which no loggers have been defined. This class is
  intended for internal use only and not as part of the public API.
  """
  def __init__(self, alogger):
    """Initialize with the specified logger being a child of the placeholder."""
    self.logger_branch = {alogger: None}

  def Append(self, alogger):
    """Add the specified logger as a child of this placeholder."""
    #if alogger not in self.loggers:
    if alogger not in self.logger_branch:
      #self.loggers.append(alogger)
      self.logger_branch[alogger] = None


class Manager(object):
  """There is [under normal circumstances] just one Manager instance, which
  holds the hierarchy of loggers.
  """
  def __init__(self, rootnode):
    """Initialize the manager with the root node of the logger hierarchy."""
    self.root = rootnode
    self.disabled_upto = NOTSET
    self.warned_nohandlers = False
    self.logger_dict = {}

  def GetLogger(self, logger_name):
    """Get a logger with the specified name (channel name), creating it
    if it doesn't yet exist. This name is a dot-separated hierarchical
    name, such as "a", "a.b", "a.b.c" or similar.

    If a PlaceHolder existed for the specified name [i.e. the logger
    didn't exist but a child of it did], replace it with the created
    logger and fix up the parent/child references which pointed to the
    placeholder to now point to the logger.
    """
    with LOCK:
      if logger_name in self.logger_dict:
        new_logger = self.logger_dict[logger_name]
        if isinstance(new_logger, PlaceHolder):
          placeholder = new_logger
          new_logger = LOGGER_CLASS(logger_name)
          new_logger.manager = self
          self.logger_dict[logger_name] = new_logger
          self._FixupChildren(placeholder, new_logger)
          self._FixupParents(new_logger)
      else:
        new_logger = LOGGER_CLASS(logger_name)
        new_logger.manager = self
        self.logger_dict[logger_name] = new_logger
        self._FixupParents(new_logger)
    return new_logger

  @staticmethod
  def _FixupChildren(placeholder, alogger):
    """Ensure children of the placeholder are connected to the given logger."""
    for child in placeholder.loggerMap:
      if not child.parent.name.startswith(alogger.name):
        alogger.parent = child.parent
        child.parent = alogger

  def _FixupParents(self, alogger):
    """Ensure that there are either loggers or placeholders all the way
    from the specified logger to the root of the logger hierarchy.
    """
    name = alogger.name
    index = name.rfind('.')
    parent = None
    while index > 0 and not parent:
      substr = name[:index]
      if substr not in self.logger_dict:
        self.logger_dict[substr] = PlaceHolder(alogger)
      else:
        potential_parent = self.logger_dict[substr]
        if isinstance(potential_parent, Logger):
          parent = potential_parent
        elif isinstance(potential_parent, PlaceHolder):
          potential_parent.Append(alogger)
      index = name[:index - 1].rfind('.')
    if not parent:
      parent = self.root
    alogger.parent = parent

#---------------------------------------------------------------------------
#   Logger classes and functions
#---------------------------------------------------------------------------

class Logger(Filterer):
  """Instances of the Logger class represent a single logging channel. A
  "logging channel" indicates an area of an application. Exactly how an
  "area" is defined is up to the application developer. Since an
  application can have any number of areas, logging channels are identified
  by a unique string. Application areas can be nested (e.g. an area
  of "input processing" might include sub-areas "read CSV files", "read
  XLS files" and "read Gnumeric files"). To cater for this natural nesting,
  channel names are organized into a namespace hierarchy where levels are
  separated by periods, much like the Java or Python package namespace. So
  in the instance given above, channel names might be "input" for the upper
  level, and "input.csv", "input.xls" and "input.gnu" for the sub-levels.
  There is no arbitrary limit to the depth of nesting.
  """
  def __init__(self, name, level=NOTSET):
    """Initialize the logger with a name and an optional level."""
    super(Logger, self).__init__()
    self.name = name
    self.level = level
    self.parent = None
    self.propagate = True
    self.handlers = set()
    self.disable_logger = False

  def _Log(self, level, msg, args, exc_info=None, extra=None):
    """Low-level logging routine which creates a LogRecord and then calls
    all the handlers of this logger to handle the record.
    """
    if self.IsEnabledFor(level):
      file_name, line_no, func_name = self.FindCaller()
      if exc_info:
        if not isinstance(exc_info, tuple):
          exc_info = sys.exc_info()
      record = self.MakeRecord(self.name, level, file_name, line_no,
                               msg, args, exc_info, func_name, extra)
      self.Handle(record)

  def AddHandler(self, handler):
    """Add the specified handler to this logger."""
    self.handlers.add(handler)

  def CallHandlers(self, record):
    """Pass a record to all relevant handlers.

    Loop through all handlers for this logger and its parents in the
    logger hierarchy. If no handler was found, output a one-off error
    message to sys.stderr. Stop searching up the hierarchy whenever a
    logger with the "propagate" attribute set to zero is found - that
    will be the last logger whose handlers are called.
    """
    logger = self
    found = False
    while logger:
      for handler in logger.handlers:
        found = True
        if record.levelno >= handler.level:
          handler.Handle(record)
      if not logger.propagate:
        break
      logger = logger.parent
    if (not found and RAISE_EXCEPTIONS and
        not self.manager.warned_nohandlers):
      sys.stderr.write('No handlers could be found for logger %r\n' % self.name)
      self.manager.warned_nohandlers = True

  @staticmethod
  def FindCaller():
    """Find the stack frame of the caller so that we can note the source
    file name, line number and function name.
    """
    # pylint: disable-msg=W0212
    # Accessing private member of module sys to grab a frame.
    # 0: local frame, 1: self._Log frame,
    # 2: Public Log method frame 3: First possible external caller.
    frame = sys._getframe(3)
    frame_info = '(unknown file)', 0, '(unknown function)'
    while hasattr(frame, 'f_code'):
      code = frame.f_code
      if code.co_filename == _FILENAME:
        frame = frame.f_back
        continue
      frame_info = (code.co_filename, frame.f_lineno, code.co_name)
      break
    return frame_info

  def GetEffectiveLevel(self):
    """Get the effective level for this logger.

    Loop through this logger and its parents in the logger hierarchy,
    looking for a non-zero logging level. Return the first one found.
    """
    logger = self
    while logger:
      if logger.level:
        return logger.level
      logger = logger.parent
    return NOTSET

  def Handle(self, record):
    """Call the handlers for the specified record.

    This method is used for unpickled records received from a socket, as
    well as those created locally. Logger-level filtering is applied.
    """
    if self.ShouldLog(record):
      self.CallHandlers(record)

  def IsEnabledFor(self, level):
    """Is this logger enabled for level 'level'?"""
    if self.disable_logger or self.manager.disabled_upto >= level:
      return False
    return level >= self.GetEffectiveLevel()

  @staticmethod
  def MakeRecord(name, level, filename, lno, msg, args,
                 exc_info, func=None, extra=None):
    """A factory method which can be overridden in subclasses to create
    specialized LogRecords.
    """
    record = LogRecord(name, level, filename, lno, msg, args, exc_info, func)
    if extra is not None:
      for key, value in extra.iteritems():
        if key in ('message', 'asctime') or key in vars(record):
          raise KeyError('Attempt to overwrite %r in LogRecord' % key)
        setattr(record, key, value)
    return record

  def RemoveHandler(self, handler):
    """Remove the specified handler from this logger."""
    self.handlers.discard(handler)

  def SetLevel(self, level):
    """Set the logging level of this logger."""
    self.level = level

  #-------------------------------------------------------------------------
  #   Public methods for logging events starts here
  #-------------------------------------------------------------------------
  def Log(self, level, msg, *args, **kwargs):
    """Log 'msg % args' with the integer severity 'level'.

    To pass exception information, set `exc_info` to True.
    """
    if not isinstance(level, int):
      if RAISE_EXCEPTIONS:
        raise TypeError('level must be an integer')
      return
    self._Log(level, msg, args, **kwargs)

  def LogDebug(self, msg, *args, **kwargs):
    """Log 'msg % args' with severity 'DEBUG'.

    To pass exception information, set `exc_info` to True.
    """
    self._Log(DEBUG, msg, args, **kwargs)

  def LogInfo(self, msg, *args, **kwargs):
    """Log 'msg % args' with severity 'INFO'.

    To pass exception information, set `exc_info` to True.
    """
    self._Log(INFO, msg, args, **kwargs)

  def LogWarning(self, msg, *args, **kwargs):
    """Log 'msg % args' with severity 'WARNING'.

    To pass exception information, set `exc_info` to True.
    """
    self._Log(WARNING, msg, args, **kwargs)

  def LogError(self, msg, *args, **kwargs):
    """Log 'msg % args' with severity 'ERROR'.

    To pass exception information, set `exc_info` to True.
    """
    self._Log(ERROR, msg, args, **kwargs)

  def LogException(self, msg, *args):
    """Convenience method for logging an ERROR with exception information."""
    self.LogError(msg, *args, **{'exc_info': True})

  def LogCritical(self, msg, *args, **kwargs):
    """Log 'msg % args' with severity 'CRITICAL'.

    To pass exception information, set `exc_info` to True.
    """
    self._Log(CRITICAL, msg, args, **kwargs)


class RootLogger(Logger):
  """A root logger is not that different to any other logger, except that
  it must have a logging level and there is only one instance of it in
  the hierarchy.
  """
  def __init__(self, level):
    """Initialize the logger with the name 'root'."""
    super(RootLogger, self).__init__('root', level)

#---------------------------------------------------------------------------
# Configuration classes and functions
#---------------------------------------------------------------------------

def BasicConfig(**kwargs):
  """Do basic configuration for the logging system.

  This creates a StreamHandler which writes to sys.stderr, set a formatter
  using the BASIC_FORMAT format string, and add the handler to the root logger.

  This function does nothing if the root logger already has handlers
  configured. It is a convenience method intended for use by simple scripts
  to do one-shot configuration of the logging package.
  """
  if not ROOT_LOGGER.handlers:
    handler = StreamHandler()
    handler.SetFormatter(DEFAULT_FORMATTER)
    ROOT_LOGGER.AddHandler(handler)
    level = kwargs.get('level')
    if level is not None:
      ROOT_LOGGER.SetLevel(level)

#---------------------------------------------------------------------------
# Utility functions at module level. Delegating everything to the root logger.
#---------------------------------------------------------------------------
def ExceptionLine(etype, value):
  # Accessing private member of traceback module to return an exception line.
  # pylint: disable=W0212
  return traceback._format_final_exc_line(etype.__name__, value)
  # pylint: enable=W0212

def ScopeName(depth):
  """Returns the name of the scope (usually a function) n levels on the stack.

  N.B. The function corrects for its own addition of a stack frame. The caller
  should only consider its own stack depth.
  """
  # Accessing private member of module sys to grab a frame.
  # pylint: disable=W0212
  frame = sys._getframe(depth + 1).f_code
  # pylint: enable=W0212
  return '%s (%s:%d)' % (frame.co_name, frame.co_filename, frame.co_firstlineno)

@decorator.decorator
def AccessLogger(function, *args, **kwds):
  """Writes a debug log-event (debug) that describes the call.

  Logged are the names of both calling and called function.
  In addition to that, the positional and keywords arguments are also recorded.
  """
  # 0: local frame, 1: decorated function's frame, 2: caller function's frame.
  LogDebug('Function %r was called by %r with arguments: *%s  **%s',
           function.__name__, ScopeName(2), args, kwds)
  return function(*args, **kwds)

#TODO(Elmer) Add a Deprecated decorator that logs a warning level event. This
# decorator should log caller and called function names, and include a message
# that mentions to function to call in the future. This needs to be configurable
# upon attaching the decorator.

def GetLogger(name=None):
  """Return a logger with the specified name, creating it if necessary.

  If no name is specified, return the root logger.
  """
  if name:
    return Logger.manager.GetLogger(name)
  return ROOT_LOGGER


def Log(level, msg, *args, **kwargs):
  """Log 'msg % args' with the integer severity 'level' on the root logger."""
  if not ROOT_LOGGER.handlers:
    BasicConfig()
  ROOT_LOGGER.Log(level, msg, *args, **kwargs)


def LogDebug(msg, *args, **kwargs):
  """Log a message with severity 'DEBUG' on the root logger."""
  if not ROOT_LOGGER.handlers:
    BasicConfig()
  ROOT_LOGGER.LogDebug(msg, *args, **kwargs)


def LogInfo(msg, *args, **kwargs):
  """Log a message with severity 'INFO' on the root logger."""
  if not ROOT_LOGGER.handlers:
    BasicConfig()
  ROOT_LOGGER.LogInfo(msg, *args, **kwargs)


def LogWarning(msg, *args, **kwargs):
  """Log a message with severity 'WARNING' on the root logger."""
  if not ROOT_LOGGER.handlers:
    BasicConfig()
  ROOT_LOGGER.LogWarning(msg, *args, **kwargs)


def LogError(msg, *args, **kwargs):
  """Log a message with severity 'ERROR' on the root logger."""
  if not ROOT_LOGGER.handlers:
    BasicConfig()
  ROOT_LOGGER.LogError(msg, *args, **kwargs)


def LogException(msg, *args):
  """Log a message + exception info with severity 'ERROR' on the root logger."""
  LogError(msg, *args, **{'exc_info': True})


def LogCritical(msg, *args, **kwargs):
  """Log a message with severity 'CRITICAL' on the root logger."""
  if not ROOT_LOGGER.handlers:
    BasicConfig()
  ROOT_LOGGER.LogCritical(msg, *args, **kwargs)


def SetMinimumSeverity(level):
  """Disable all logging calls less severe than 'level'."""
  ROOT_LOGGER.manager.disabled_upto = level


@atexit.register
def Shutdown():
  """Perform cleanup on application exit."""
  for handler in HANDLER_LIST:
    # Exceptions might occur upon locked files and the like.
    # Ignore unless we've chosen to raise them.
    try:
      handler.Flush()
      handler.Close()
    except StandardError:
      if RAISE_EXCEPTIONS:
        raise

def FlushAll():
  """Performs a flush on all open handlers, allowing manual cleanup."""
  for handler in HANDLER_LIST:
    try:
      handler.Flush()
    except StandardError:
      if RAISE_EXCEPTIONS:
        raise

BASIC_FORMAT = "%(levelname)s:%(name)s:%(message)s"
HANDLERS = {} # repository of handlers (for flushing when shutdown called)
HANDLER_LIST = [] # allow handlers to be removed in reverse of initialization.

DEFAULT_FORMATTER = Formatter()
ROOT_LOGGER = RootLogger(WARNING)
LOGGER_CLASS = Logger
LOGGER_CLASS.root = ROOT_LOGGER
LOGGER_CLASS.manager = Manager(ROOT_LOGGER)
