#!/usr/bin/python
"""HTML generators for the logging web frontend"""

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.5'

# Standard modules
import datetime
import pytz
import time
import os

# Custom modules
import uweb
from . import model


class Viewer(uweb.DebuggingPageMaker):
  """Holds all the html generators for the logger web frontend

  Each page as a separate method.
  """
  PUBLIC_DIR = 'static'
  TEMPLATE_DIR = 'templates'

  def _PostInit(self):
    self.parser.RegisterFunction('datetime', DateFormat)
    self.parser.RegisterFunction('timeago', TimeAgo)
    self.parser.RegisterFunction('timedelta', TimeDeltaFormat)
    self.parser.RegisterFunction('80cols', CutAfter(80))
    self.paths = list(self._LogPaths())

  def _LogPaths(self):
    for path in self.options['paths']['logs'].split(os.path.pathsep):
      if path.strip():
        yield os.path.expanduser(path.strip())

  def _OpenLogDatabase(self, db_name):
    db_path = os.path.normpath(db_name)
    for path in self.paths:
      if db_path.startswith(path):
        break
    else:
      raise uweb.ImmediateResponse(self.InvalidDatabase(db_path))
    try:
      return model.LogDb(db_path)
    except uweb.DatabaseError, error:
      raise uweb.ImmediateResponse(self.InvalidDatabase(error))

  def Index(self):
    logs = model.Logging(self.paths, self.options['paths']['filemask'])
    return self.parser.Parse(
        'index.html', logfiles=logs.ListFiles(), **self.CommonBlocks('Home'))

  def Database(self, db_name):
    log_db = self._OpenLogDatabase(db_name)
    count = int(self.get.getfirst('count', 20))
    offset = int(self.get.getfirst('offset', 0))
    query = self.get.getfirst('query', '')
    level = self.get.getfirst('level', 0)

    events = log_db.Events(offset=offset, count=count, query=query, level=level)
    pagelinks = []
    if offset > 0:
      pagelinks.append(self.parser.Parse(
          'pagination_link.html', count=count, level=level,
          offset=max(offset - count, 0), query=query, title='Previous Page'))
    #XXX(Elmer): This may generate a false last next-link, because there is
    # no way to tell whether there are more files. It's a good bet though.
    if len(events) == count:
      pagelinks.append(self.parser.Parse(
          'pagination_link.html', count=count, level=level,
          offset=offset + count, query=query, title='Next Page'))
    if pagelinks:
      pagination = self.parser.Parse('pagination.html',
                                     pagelinks=''.join(pagelinks))
    else:
      pagination = ''

    return self.parser.Parse(
        'database.html',
        pagination=pagination,
        db_name=db_name,
        req_vars={'query': query, 'count': count, 'level': level},
        events=events,
        **self.CommonBlocks(db_name, scripts=(
            'http://ajax.googleapis.com/ajax/libs/jquery/1.3.2/jquery.min.js',
            '/static/database.js')))

  def Invalidcommand(self, command):
    """Returns an error message"""
    uweb.logging.LogWarning('Bad page %r requested', command)
    return uweb.Response(
        httpcode=404,
        content=self.parser.Parse(
            '404.html', error=command,
            **self.CommonBlocks('Page not found')))

  def InvalidDatabase(self, database):
    """Returns an error message"""
    uweb.logging.LogWarning('Bad database %r requested', database)
    return uweb.Response(
        httpcode=404,
        content=self.parser.Parse(
            'invaliddb.html', error=database,
            **self.CommonBlocks('Database not found')))

  def Header(self, title='Available databases', page_id=None):
    """Returns the header template, filled out from the given title and page_id.

    Arguments:
      @ title: str
        The page's title as it should be in the html
      % page_id: str
        The page_id as it should occur on the body tag. If left undefined, the
        page title is used, replacing spaces with underscores.
    """
    if not page_id:
      page_id = title.replace(' ', '_').lower()
    return self.parser.Parse('header.html', title=title, page_id=page_id)

  def Footer(self, scripts=()):
    """Returns the footer html"""
    scripts = ['<script type="text/javascript" src="%s"></script>' % path
               for path in scripts]
    return self.parser.Parse(
        'footer.html',
        scripts=''.join(scripts),
        year=time.strftime('%Y'),
        version={'uweb': uweb.__version__, 'logviewer': __version__})

  def Sidebar(self):
    logs = model.Logging(self.paths, self.options['paths']['filemask'])
    return self.parser.Parse('sidebar.html', logfiles=logs.ListFiles())

  def CommonBlocks(self, title, page_id=None, scripts=()):
    return {'sidebar': self.Sidebar(),
            'header': self.Header(title, page_id),
            'footer': self.Footer(scripts)}


def CutAfter(length):
  """Returns a function that cuts the string short after `length` characters."""
  def _CutAfter(text, length=length):
    if len(text) <= 80:
      return text
    return text[:78] + u' \u2026'
  return _CutAfter


def DateFormat(dtime):
  """Returns only the date portion (as string) of a datetime object."""
  return dtime.strftime('%F %T')


def TimeDeltaFormat(milliseconds):
  """Returns a timedelta input in milliseconds as a human readable string."""
  hours, seconds = divmod(milliseconds / 1e3, 3600)
  days, hours = divmod(hours, 24)
  minutes, seconds = divmod(seconds, 60)
  return ShortDiff(days, hours, minutes, seconds)


def TimeAgo(dtime):
  """Returns the amount of time something happened in the past as string."""
  diff = pytz.utc.localize(datetime.datetime.utcnow()) - dtime
  hours = diff.seconds // 3600
  minutes = diff.seconds // 60 % 60
  seconds = diff.seconds % 60
  return ShortDiff(diff.days, hours, minutes, seconds)


def ShortDiff(days, hours, minutes, seconds):
  if days:
    return '%dd%dh%dm%ds' % (days, hours, minutes, seconds)
  if hours:
    return '%dh%dm%ds' % (hours, minutes, seconds)
  if minutes:
    return '%dm%ds' % (minutes, seconds)
  return '%ds' % seconds
