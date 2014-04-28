#!/usr/bin/python2.5
"""Extra stuff for logging package."""
from __future__ import with_statement
__author__  = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.1.0'

# Custom modules
from underdark.libs.sqltalk import sqlite


class LoggerAdapter(object):
  """An adapter for loggers which makes it easier to specify contextual
  information in logging output.
  """
  def __init__(self, logger, extra):
    """Initialize the adapter with a logger and a dict-like object which
    provides contextual information. This constructor signature allows
    easy stacking of LoggerAdapters, if so desired.

    You can effectively pass keyword arguments as shown in the
    following example:

    adapter = LoggerAdapter(someLogger, dict(p1=v1, p2="v2"))
    """
    self.logger = logger
    self.extra = extra

  def Log(self, level, msg, *args, **kwargs):
    """Delegate a log call to the underlying logger, after adding
    contextual information from this adapter instance.
    """
    msg, kwargs = self.Process(msg, kwargs)
    self.logger.Log(level, msg, *args, **kwargs)

  def LogDebug(self, msg, *args, **kwargs):
    """Delegate a debug call to the underlying logger, after adding
    contextual information from this adapter instance.
    """
    msg, kwargs = self.Process(msg, kwargs)
    self.logger.LogDebug(msg, *args, **kwargs)

  def LogInfo(self, msg, *args, **kwargs):
    """Delegate an info call to the underlying logger, after adding
    contextual information from this adapter instance.
    """
    msg, kwargs = self.Process(msg, kwargs)
    self.logger.LogInfo(msg, *args, **kwargs)

  def LogWarning(self, msg, *args, **kwargs):
    """Delegate a warning call to the underlying logger, after adding
    contextual information from this adapter instance.
    """
    msg, kwargs = self.Process(msg, kwargs)
    self.logger.LogWarning(msg, *args, **kwargs)

  def LogError(self, msg, *args, **kwargs):
    """Delegate an error call to the underlying logger, after adding
    contextual information from this adapter instance.
    """
    msg, kwargs = self.Process(msg, kwargs)
    self.logger.LogError(msg, *args, **kwargs)

  def LogException(self, msg, *args, **kwargs):
    """Delegate an exception call to the underlying logger, after adding
    contextual information from this adapter instance.
    """
    msg, kwargs = self.Process(msg, kwargs)
    self.logger.LogException(msg, *args, **kwargs)

  def LogCritical(self, msg, *args, **kwargs):
    """Delegate a critical call to the underlying logger, after adding
    contextual information from this adapter instance.
    """
    msg, kwargs = self.Process(msg, kwargs)
    self.logger.LogCritical(msg, *args, **kwargs)

  def Process(self, msg, kwargs):
    """Process the logging message and keyword arguments passed in to
    a logging call to insert contextual information. You can either
    manipulate the message itself, the keyword args or both. Return
    the message and kwargs modified (or not) to suit your needs.

    Normally, you'll only need to override this one method in a
    LoggerAdapter subclass for your specific needs.
    """
    kwargs['extra'] = self.extra
    return msg, kwargs


def MakeLoggingTable(connection):
  """Creates a table on an SQLite database for logging purposes."""
  with connection as cursor:
    cursor.Execute("""CREATE TABLE logging (
                       `ID` INTEGER PRIMARY KEY AUTOINCREMENT,
                       `logLevel` VARCHAR(12),
                       `logLevelNumber` INTEGER,
                       `logMessage` TEXT,
                       `logName` VARCHAR(24),
                       `logTime` TIMESTAMP,
                       `logTimeRelative` INTEGER,
                       `processName` VARCHAR(24),
                       `processNumber` INTEGER,
                       `threadName` VARCHAR(24),
                       `threadNumber` INTEGER,
                       `fileName` VARCHAR(32),
                       `filePath` TEXT,
                       `moduleName` VARHCAR(32),
                       `lineNumber` INTEGER,
                       `functionName` VARCHAR(32),
                       `traceback` TEXT)""")


def OpenSqliteLoggingDatabase(filename):
  """Opens a sqlite database by the given filename.

  If it doesn't yet exist, a table by the name `logging` is created.

  Arguments:
    @ filename: str
      Path + filename for the sqlite database file to use or create.
  """
  connection = sqlite.ThreadConnect(filename, disable_log=True)
  if 'logging' not in connection.ShowTables():
    MakeLoggingTable(connection)
  return connection
