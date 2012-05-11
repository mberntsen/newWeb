#!/usr/bin/python2.5
"""SQLTalk SQLite interface package."""

# Standard modules
import _sqlite3

# Application specific modules
import connection

VERSION_INFO = tuple(map(int, _sqlite3.version.split('.')))
SQLITE_VERSION_INFO = tuple(map(int, _sqlite3.sqlite_version.split('.')))


def Connect(*args, **kwds):
  """Factory function for connection.Connection."""
  kwds['detect_types'] = _sqlite3.PARSE_DECLTYPES
  return connection.Connection(*args, **kwds)


def ThreadConnect(*args, **kwds):
  """Factory function for connection.ThreadedConnection."""
  kwds['detect_types'] = _sqlite3.PARSE_DECLTYPES
  return connection.ThreadedConnection(*args, **kwds)


DataError = _sqlite3.DataError
DatabaseError = _sqlite3.DatabaseError
Error = _sqlite3.Error
IntegrityError = _sqlite3.IntegrityError
InterfaceError = _sqlite3.InterfaceError
InternalError = _sqlite3.InternalError
NotSupportedError = _sqlite3.NotSupportedError
OperationalError = _sqlite3.OperationalError
