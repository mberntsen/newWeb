#!/usr/bin/python2.5
"""SQLTalk MySQL interface package.

This package provides a full SQLTalk interface against a MySQL database.
Required MySQL version is unknown but expected to be 4, however, migrating to
MySQL version 5 is in everyone's best interest :).

This package is built on a heavily modified version of MySQLdb 1.2.2 which was
originally written by Andy Dustman <adustman@users.sourceforge.net).

Classes:
  SqlTypeSet: Modification of a frozenset to check for type matches.

Functions:
  Connect: Connects to a MySQL server and returns a connection object.
           Refer to the documentation enclosed in the connections module for
           argument information.
"""
__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.9'

# Application specific modules
import constants
import connection


class SqlTypeSet(frozenset):
  """A special type of frozenset for which A == x is true if A is a
  DBAPISet and x is a member of that set."""
  def __ne__(self, other):
    return other not in self

  def __eq__(self, other):
    return other in self


def Connect(*args, **kwargs):
  """Factory function for connection.Connection."""
  return connection.Connection(*args, **kwargs)


STRING = SqlTypeSet((constants.FIELD_TYPE.ENUM, constants.FIELD_TYPE.STRING,
                     constants.FIELD_TYPE.VAR_STRING))
BINARY = SqlTypeSet((constants.FIELD_TYPE.BLOB,
                     constants.FIELD_TYPE.LONG_BLOB,
                     constants.FIELD_TYPE.MEDIUM_BLOB,
                     constants.FIELD_TYPE.TINY_BLOB))
NUMBER = SqlTypeSet((constants.FIELD_TYPE.DECIMAL, constants.FIELD_TYPE.DOUBLE,
                     constants.FIELD_TYPE.FLOAT, constants.FIELD_TYPE.INT24,
                     constants.FIELD_TYPE.LONG, constants.FIELD_TYPE.LONGLONG,
                     constants.FIELD_TYPE.TINY, constants.FIELD_TYPE.YEAR))
DATE = SqlTypeSet((constants.FIELD_TYPE.DATE, constants.FIELD_TYPE.NEWDATE))
TIME = SqlTypeSet((constants.FIELD_TYPE.TIME,))
TIMESTAMP = DATETIME = SqlTypeSet((constants.FIELD_TYPE.TIMESTAMP,
                                   constants.FIELD_TYPE.DATETIME))
ROWID = SqlTypeSet()
