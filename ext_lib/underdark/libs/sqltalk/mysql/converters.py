#!/usr/bin/python2.5
"""MySQLdb type conversion module

This module handles all the type conversions for MySQL. If the default
type conversions aren't what you need, you can make your own. The
dictionary conversions maps some kind of type to a conversion function
which returns the corresponding value:

Key: FIELD_TYPE.* (from MySQLdb.constants)

Conversion function:

  Arguments: string

  Returns: Python object

Key: Python type object (from types) or class

Conversion function:

  Arguments: Python object of indicated type or class AND
         conversion dictionary

  Returns: SQL literal value

  Notes: Most conversion functions can ignore the dictionary, but
       it is a required parameter. It is necessary for converting
       things like sequences and instances.

Don't modify conversions if you can avoid it. Instead, make copies
(with the copy() method), modify the copies, and then pass them to
MySQL.connect().
"""

# Standard modules
import array
import datetime
import decimal
import time
import _mysql

# Application specific modules
import constants
import times


def Array2Str(obj, conv_dict):
  """Converts an array to a string."""
  return Thing2Literal(obj.tostring(), conv_dict)


def Bool2Str(obj, conv_dict=None):
  """Converts a bool to either 'True' or 'False' as string."""
  return str(obj)


def Float2Str(obj, conv_dict=None):
  """Converts a floating point number to a string."""
  return '%.15g' % obj


def Instance2Str(obj, conv_dict):
  """Convert an Instance to a string representation. If the __str__() method
  produces acceptable output, then you don't need to add the class to
  conversions; it will be handled by the default converter. If the exact class
  is not found in conv_dict, it will use the first class it can find for which
  obj is an instance.
  """
  if obj.__class__ in (object, type):
    return conv_dict[str](obj, conv_dict)
  try:
    return conv_dict[obj.__class__](obj, conv_dict)
  except KeyError:
    for converter in conv_dict:
      try:
        if (isinstance(obj, converter) and
            conv_dict[converter] is not Instance2Str):
          conv_dict[obj.__class__] = conv_dict[converter]
          return conv_dict[converter](obj, conv_dict)
      except TypeError:
        continue
    else:
      return conv_dict[str](obj, conv_dict)


def None2NULL(obj=None, conv_dict=None):
  """Convert None to NULL."""
  return 'NULL'


def Set2Str(obj, conv_dict):
  """Converts any itertable object into a comma separated string."""
  return _mysql.escape_sequence(list(obj), conv_dict)


def Str2Set(string):
  """Converts a comma separated string back to a list."""
  return string.split(',')


def Thing2Literal(obj, conv_dict):
  """Convert something into a SQL string literal.  If using
  MySQL-3.23 or newer, string_literal() is a method of the
  _mysql.MYSQL object, and this function will be overridden with
  that method when the connection is created."""
  return _mysql.string_literal(obj, conv_dict)


def Thing2Str(obj, conv_dict=None):
  """Convert something into a string via str()."""
  return str(obj)


CONVERSIONS = {
  dict: _mysql.escape_dict,
  list: _mysql.escape_sequence,
  tuple: _mysql.escape_sequence,
  set: Set2Str,
  bool: Bool2Str,
  int: Thing2Str,
  long: Thing2Str,
  float: Float2Str,
  type(None): None2NULL,
  str: Thing2Literal,
  object: Instance2Str,
  type: Instance2Str,
  array.array: Array2Str,
  datetime.datetime: times.DateTimeToLiteral,
  datetime.timedelta: times.TimeDeltaToLiteral,
  time.struct_time: times.TimeStructToLiteral,
  constants.FIELD_TYPE.TINY: int,
  constants.FIELD_TYPE.SHORT: int,
  constants.FIELD_TYPE.LONG: long,
  constants.FIELD_TYPE.FLOAT: float,
  constants.FIELD_TYPE.DOUBLE: float,
  constants.FIELD_TYPE.DECIMAL: decimal.Decimal,
  constants.FIELD_TYPE.NEWDECIMAL: decimal.Decimal,
  constants.FIELD_TYPE.LONGLONG: long,
  constants.FIELD_TYPE.INT24: int,
  constants.FIELD_TYPE.YEAR: int,
  constants.FIELD_TYPE.SET: Str2Set,
  constants.FIELD_TYPE.TIMESTAMP: times.MysqlTimestampConverter,
  constants.FIELD_TYPE.DATETIME: times.DateTimeOrNone,
  constants.FIELD_TYPE.TIME: times.TimeDeltaOrNone,
  constants.FIELD_TYPE.DATE: times.DateOrNone,
  constants.FIELD_TYPE.BLOB: [(constants.FLAG.BINARY, str)],
  constants.FIELD_TYPE.STRING: [(constants.FLAG.BINARY, str)],
  constants.FIELD_TYPE.VAR_STRING: [(constants.FLAG.BINARY, str)],
  constants.FIELD_TYPE.VARCHAR: [(constants.FLAG.BINARY, str)]}
