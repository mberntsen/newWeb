#!/usr/bin/python2.5
"""times module

This module provides some Date and Time classes for dealing with MySQL data.

Use Python datetime module to handle date and time columns.
"""
# Standard modules
import _mysql
import datetime
import math
import pytz
import time


INTERPRET_AS_UTC = pytz.utc.localize

def DateFromTicks(ticks):
  """Convert UNIX ticks into a date instance."""
  return datetime.date.fromtimestamp(ticks)


def DateOrNone(string):
  """Converts an input string to a datetime.date object.

  Returns:
    datetime.date object, or None if input is bad.
  """
  try:
    return datetime.date(*map(int, string.split('-')))
  except ValueError:
    return None


def DateTimeOrNone(string):
  """Converts an input string to a datetime.datetime object.

  Returns:
    datetime.datetime object, or None if input is bad.
  """
  if ' ' in string:
    separator = ' '
  elif 'T' in string:
    separator = 'T'
  else:
    return DateOrNone(string)
  try:
    strdate, strtime = string.split(separator)
    return INTERPRET_AS_UTC(
        datetime.datetime(*map(int, strdate.split('-') + strtime.split(':'))))
  except ValueError:
    return DateOrNone(string)


def DateTimeToLiteral(date, converter):
  """Format a DateTime object as an ISO timestamp."""
  try:
    date = date.astimezone(pytz.utc)
  except ValueError:
    pass  # naive datetime object
  return _mysql.string_literal(date.isoformat(), converter)


def TimeDeltaToLiteral(timedelta, converter):
  """Formats a DateTimeDelta object as a string-literal time delta."""
  hours, seconds = divmod(timedelta.seconds, 3600)
  minutes, seconds = divmod(seconds, 60)
  literal = '%d %d:%d:%d' % (timedelta.days, hours, minutes, seconds)
  return _mysql.string_literal(literal, converter)


def TimeStructToLiteral(date, converter):
  """Formats a time_struct as an ISO timestamp."""
  return _mysql.string_literal(time.strftime('%FT%T', date), converter)


def MysqlTimestampConverter(stamp):
  """Convert a MySQL TIMESTAMP to a datetime.datetime object."""
  # MySQL > 4.1 returns TIMESTAMP in the same format as DATETIME
  if len(stamp) == 19:
    return DateTimeOrNone(stamp)
  try:
    stamp = stamp.ljust(14, '0')
    return INTERPRET_AS_UTC(datetime.datetime(
        *map(int, (stamp[:4], stamp[4:6], stamp[6:8],
                   stamp[8:10], stamp[10:12], stamp[12:14]))))
  except ValueError:
    return None


def TimeDeltaOrNone(string):
  """Converts an input string to a datetime.timedelta object.

  Returns:
    datetime.timedelta object, or None if input is bad.
  """
  try:
    hour, minute, second = map(float, string.split(':'))
    return (-1, 1)[hour > 0] * datetime.timedelta(
        hours=hour, minutes=minute, seconds=second)
  except ValueError:
    return None


def TimeFromTicks(ticks):
  """Convert UNIX ticks into a time instance."""
  return INTERPRET_AS_UTC(datetime.time(*time.gmtime(ticks)[3:6]))


def TimeOrNone(string):
  """Converts an input string to a datetime.time object.

  Returns:
    datetime.time object, or None if input is bad.
  """
  try:
    hour, minute, second = string.split(':')
    micro, second = math.modf(float(second))
    return INTERPRET_AS_UTC(datetime.time(
        hour=int(hour), minute=int(minute),
        second=int(second), microsecond=int(micro * 1000000)))
  except ValueError:
    return None


def TimestampFromTicks(ticks):
  """Convert UNIX ticks into a datetime instance."""
  return INTERPRET_AS_UTC(datetime.datetime.utcfromtimestamp(ticks))
