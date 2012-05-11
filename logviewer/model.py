#!/usr/bin/python2.5
"""This module scans for logging files and delivers them as objects"""

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.3'

# standard modules
import os
import fnmatch

# custom modules
from underdark.libs.sqltalk import sqlite
import uweb


class Logging(object):
  """Provides a method to scan a folder recursively for db log files"""
  def __init__(self, paths, mask):
    """Sets up the loggin file emitter"""
    if isinstance(paths, basestring):
      self.paths = [paths]
    else:
      self.paths = paths
    self.mask = mask

  def ListFiles(self):
    """Lists all the files that match the mask in path, includes the path from
    the base path given"""
    file_listing = []
    for root_dir in self.paths:
      listing = {'name': root_dir, 'files': []}
      file_listing.append(listing)
      for base, _dirs, files in os.walk(root_dir):
        for path in fnmatch.filter(files, self.mask):
          listing['files'].append(
              os.path.relpath(os.path.join(base, path), root_dir))
      listing['files'].sort()
    return file_listing


class LogDb(object):
  """Opens a log database provides methods to lists its errors"""
  def __init__(self, db_path):
    """Opens a log database

    Arguments:
      @ db_path: str
        The fully qualified path for the SQLite logging database.
    """
    if not os.path.exists(db_path):
      raise uweb.DatabaseError(db_path)
    try:
      self.connection = sqlite.Connect(db_path)
    except sqlite.OperationalError, error:
      raise uweb.DatabaseError(error)

  def Events(self, offset=0, count=None, query=None, level=0):
    """Lists all the errors in a database's logging table

    Arguments:
      % offset: int ~~ 0:
        The amount of log-events to skip before output.
      % count: int ~~ None
        The number of log-events to return. None equals no limit.
      % query: str ~~ None
        Text that has to occur in either the message or the traceback of a
        log-event for it to be returned.
      % level: int ~~ 0
        Minimal log level to show events for:
          10 - DEBUG
          20 - INFO
          30 - WARNING
          40 - ERROR (and EXCEPTION)
          50 - CRITICAL

    Returns
      sqltalk resultset"""
    conditions = ['`logLevelNumber` >= %d' % int(level)]
    if query:
      conditions.append('(`logMessage` LIKE "%%%s%%" OR'
                        ' `traceback` LIKE "%%%s%%")' % (query, query))
    with self.connection as cursor:
      return cursor.Select(
        table='logging', conditions=conditions, limit=count,
        offset=offset, order=[('ID', True)])
