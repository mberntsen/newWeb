#!/usr/bin/python
"""Underdark uWeb PageMaker class and its various Mixins."""
from __future__ import with_statement

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.6'

# Standard modules
import datetime
import mimetypes
import os
import sys
import threading
import warnings

# Custom modules
from underdark.libs import logging
from underdark.libs import pysession
from underdark.libs.uweb import templateparser

RFC_1123_DATE = '%a, %d %b %Y %T GMT'

__all__ = (
    'DatabaseError', 'ReloadModules', 'BasePageMaker', 'PageMakerDebuggerMixin',
    'PageMakerMongodbMixin', 'PageMakerMysqlMixin', 'PageMakerSqliteMixin',
    'PageMakerSessionMixin', 'Response')


class DatabaseError(Exception):
  """The database server has gone away"""


class ReloadModules(Exception):
  """Communicates the handler that it should reload the pageclass"""


class CacheStorage(object):
  """A semi-persistent storage with dict-like interface."""
  def __init__(self):
    super(CacheStorage, self).__init__()
    self._dict = {}
    self._lock = threading.RLock()

  def __contains__(self, key):
    return key in self._dict

  def Get(self, key, *default):
    """Returns the current value for `key`, or the `default` if it doesn't."""
    with self._lock:
      if len(default) > 1:
        raise ValueError('Only one default value accepted')
      try:
        return self._dict[key]
      except KeyError:
        if default:
          return default[0]
        raise

  def Set(self, key, value):
    """Sets the `key` in the dictionary storage to `value`."""
    self._dict[key] = value

  def SetDefault(self, key, default=None):
    """Returns the value for `key` or sets it to `default` if it doesn't exist.

    Arguments:
      @ key: obj
        The key to retrieve from the dictionary storage.
      @ default: obj ~~ None
        The default new value for the given key if it doesn't exist yet.
    """
    with self._lock:
      return self._dict.setdefault(key, default)


class MimeTypeDict(dict):
  """Dictionary that defines special behavior for mimetypes.

  Mimetypes (of typical form "type/subtype") are stored as (type, subtype) keys.
  This allows grouping of types to happen, and fallbacks to occur.

  The following is a typical complete MIMEType example:
    >>> mime_type_dict['text/html'] = 'HTML content'

  One could also define a default for the whole type, as follows:
    >>> mime_type_dict['text/*'] = 'Default'

  Looking up a type/subtype that doesn't exist, but for which a bare type does,
  will result in the value for the bare type to be returned:
    >>> mime_type_dict['text/nonexistant']
    'Default'
  """
  def __init__(self, data=(), **kwds):
    super(MimeTypeDict, self).__init__()
    if data:
      self.update(data)
    if kwds:
      self.update(**kwds)

  @staticmethod
  def MimeSplit(mime):
    """Split up a MIMEtype in a type and subtype, return as tuple.

    When the subtype if undefined or '*', only the type is returned, as 1-tuple.
    """
    mime_type, _sep, mime_subtype = mime.lower().partition('/')
    if not mime_subtype or mime_subtype == '*':
      return mime_type,  # 1-tuple
    return mime_type, mime_subtype

  def __setitem__(self, mime, value):
    super(MimeTypeDict, self).__setitem__(self.MimeSplit(mime), value)

  def __getitem__(self, mime):
    parsed_mime = self.MimeSplit(mime)
    try:
      return super(MimeTypeDict, self).__getitem__(parsed_mime)
    except KeyError:
      try:
        return super(MimeTypeDict, self).__getitem__(parsed_mime[:1])
      except KeyError:
        raise KeyError('KeyError: %r' % mime)

  def get(self, mime, default=None):
    try:
      return self[mime]
    except KeyError:
      return default

  def update(self, data=None, **kwargs):
    """Update the dictionary with new values from another dictionary.

    Also takes values from an iterable object of pairwise data.
    """
    if data:
      try:
        for key, value in data.iteritems():
          self[key] = value
      except AttributeError:
        # Argument data is not a proper dict, treat it as an iterable of tuples.
        for key, value in data:
          self[key] = value
    if kwargs:
      self.update(kwargs)


class BasePageMaker(object):
  """Provides the base pagemaker methods for all the html generators."""
  # Constant for persistent storage accross requests. This will be accessible
  # by all threads of the same application (in the same Python process).
  PERSISTENT = CacheStorage()
  # Base paths for templates and public data. These are used in the PageMaker
  # classmethods that set up paths specific for that pagemaker.
  PUBLIC_DIR = 'www'
  TEMPLATE_DIR = 'templates'

  # Default Static() handler cache durations, per MIMEtype, in days
  CACHE_DURATION = MimeTypeDict({'text': 7, 'image': 30, 'application': 7})

  def __init__(self, req, config=None):
    """sets up the template parser and database connections

    Arguments:
      @ req: request.Request
        The originating request, including environment, GET, POST and cookies.
      % config: dict ~~ None
        Configuration for the pagemaker, with database connection information
        and other settings. This will be available through `self.options`.
    """
    self.__SetupPaths()
    self.req = req
    self.cookies = req.vars['cookie']
    self.get = req.vars['get']
    self.post = req.vars['post']
    self.options = config or {}
    self.persistent = self.PERSISTENT

  def _PostInit(self):
    """Method that gets called for derived classes of BasePageMaker."""

  @classmethod
  def __SetupPaths(cls):
    """This sets up the correct paths for the PageMaker subclasses.

    From the passed in `cls`, it retrieves the filename. Of that path, the
    directory is used as the working directory. Then, the module constants
    PUBLIC_DIR and TEMPLATE_DIR are used to define class constants from.
    """
    cls_dir = os.path.dirname(sys.modules[cls.__module__].__file__)
    cls.LOCAL_DIR = cls_dir
    cls.PUBLIC_DIR = os.path.join(cls_dir, cls.PUBLIC_DIR)
    cls.TEMPLATE_DIR = os.path.join(cls_dir, cls.TEMPLATE_DIR)

  @property
  def parser(self):
    """Provides a templateparser.Parser instance.

    If the config file specificied a [templates] section and a `path` is
    assigned in there, this path will be used.
    Otherwise, the `TEMPLATE_DIR` will be used to load templates from.
    """
    if '__parser' not in self.persistent:
      self.persistent.Set('__parser', templateparser.Parser(
          self.options.get('templates', {}).get('path', self.TEMPLATE_DIR)))
    return self.persistent.Get('__parser')

  def InternalServerError(self):
    """Returns a plain text notification about an internal server error."""
    return Response(
        content='INTERNAL SERVER ERROR (HTTP 500) DURING PROCESSING OF %r' % (
            self.req.env['PATH_INFO']),
        content_type='text/plain', httpcode=500)

  @staticmethod
  def Reload():
    """Raises `ReloadModules`, telling the Handler() to reload its pageclass."""
    raise ReloadModules('Reloading ... ')

  def Static(self, rel_path):
    """Provides a handler for static content.

    The requested `path` is truncated against a root (removing any uplevels),
    and then added to the working dir + PUBLIC_DIR. If the request file exists,
    then the requested file is retrieved, its mimetype guessed, and returned
    to the client performing the request.

    Should the requested file not exist, a 404 page is returned instead.

    Arguments:
      @ rel_path: str
        The filename relative to the working directory of the webserver.

    Returns:
      Page: contains the content and mimetype of the requested file, or a 404
            page if the file was not available on the local path.
    """
    rel_path = os.path.abspath(os.path.join(os.path.sep, rel_path))[1:]
    abs_path = os.path.join(self.PUBLIC_DIR, rel_path)
    try:
      with file(abs_path) as staticfile:
        content_type, _encoding = mimetypes.guess_type(abs_path)
        if not content_type:
          content_type = 'text/plain'
        cache_days = self.CACHE_DURATION.get(content_type, 0)
        expires = datetime.datetime.utcnow() + datetime.timedelta(cache_days)
        return Response(content=staticfile.read(),
                        content_type=content_type,
                        headers={'Expires': expires.strftime(RFC_1123_DATE)})
    except IOError:
      message = 'This is not the path you\'re looking for. No such file %r' % (
          self.req.env['PATH_INFO'])
      return Response(content=message,
                      content_type='text/plain',
                      httpcode=404)


class PageMakerDebuggerMixin(object):
  """Replaces the default handler for Internal Server Errors.

  This one prints a host of debugging and request information, though it still
  lacks interactive functions.
  """
  CACHE_DURATION = MimeTypeDict({})

  def _ParseStackFrames(self, stack):
    """Generates list items for traceback information.

    Each traceback item contains the file- and function name, the line numer
    and the source that belongs with it. For each stack frame, the local
    variables are also added to it, allowing proper analysis to happen.

    This most likely doesn't need overriding / redefining in a subclass.

    Arguments:
      @ stack: traceback.stack
        The stack frames to return analysis on.

    Yields:
      str: Template-parsed HTML with frame information.
    """
    while stack:
      frame = stack.tb_frame
      yield self.debug_parser.Parse('stack_frame.xhtml', frame={
          'file': frame.f_code.co_filename,
          'scope': frame.f_code.co_name,
          'locals': ''.join(
              self.debug_parser.Parse('var_row.xhtml', var=(name, repr(value)))
              for name, value in sorted(frame.f_locals.items())),
          'source': ''.join(
              self._SourceLines(frame.f_code.co_filename, frame.f_lineno))})
      stack = stack.tb_next

  def _SourceLines(self, filename, line_num, context=3):
    """Yields the offending source line, and `context` lines of context.

    Arguments:
      @ filename: str
        The filename of the
      @ line_num: int
        The line number for the offending line.
      % context: int ~~ 3
        Number of lines context, before and after the offending line.

    Yields:
      str: Templated list-item for a source code line.
    """
    import linecache
    for line_num in xrange(line_num - context, line_num + context + 1):
      yield self.debug_parser.Parse('var_row.xhtml', var=(
          line_num, linecache.getline(filename, line_num)))

  def InternalServerError(self):
    """Returns a HTTP 500 response with detailed failure analysis."""
    cookies = [
        self.debug_parser.Parse(
            'var_row.xhtml', var=(name, self.cookies[name].value))
        for name in sorted(self.cookies)]
    environ = [
        self.debug_parser.Parse('var_row.xhtml', var=var)
        for var in sorted(self.req.ExtendedEnvironment().items())]
    post_data = [
        self.debug_parser.Parse('var_row.xhtml', var=(var, self.post[var]))
        for var in sorted(self.post)]
    query_args = [
        self.debug_parser.Parse('var_row.xhtml', var=(var, self.get[var]))
        for var in sorted(self.get)]
    nulldata = '<tr><td colspan="2"><em>NULL</em></td></tr>'
    stack_trace = reversed(list(self._ParseStackFrames(sys.exc_traceback)))
    return Response(
        httpcode=200,
        content=self.debug_parser.Parse(
            'http_500.xhtml',
            cookies=''.join(cookies) or nulldata,
            environ=''.join(environ) or nulldata,
            query_args=''.join(query_args) or nulldata,
            post_data=''.join(post_data) or nulldata,
            exc={'type': sys.exc_type.__name__,
                 'value': sys.exc_value,
                 'traceback': ''.join(stack_trace)}))

  @property
  def debug_parser(self):
    if not '__debug_parser' in self.persistent:
      template_dir = os.path.join(os.path.dirname(__file__), 'error_templates')
      self.persistent.Set('__debug_parser',
                          templateparser.Parser(os.path.abspath(template_dir)))
    return self.persistent.Get('__debug_parser')


class PageMakerMongodbMixin(object):
  """Adds MongoDB support to PageMaker."""
  @property
  def connection(self):
    """Returns a MongoDB database connection."""
    if '__mongo' not in self.persistent:
      import pymongo
      try:
        self.persistent.Set('__mongo', pymongo.connection.Connection(
            host=self.options['mongodb'].get('host', 'localhost'),
            port=self.options['mongodb'].get('port', None)))
      except pymongo.errors.AutoReconnect:
        raise DatabaseError('MongoDb is unavailable')
      except pymongo.errors.ConnectionFailure:
        raise DatabaseError('MongoDb is unavailable')
    return self.persistent.Get('__mongo')


class PageMakerMysqlMixin(object):
  """Adds MySQL support to PageMaker."""
  @property
  def connection(self):
    """Returns a MySQL database connection."""
    if '__mysql' not in self.persistent:
      from underdark.libs.sqltalk import mysql
      mysqlopts = self.options['mysql']
      self.persistent.Set('__mysql', mysql.Connect(
          host=mysqlopts.get('host', 'localhost'),
          user=mysqlopts.get('user'),
          passwd=mysqlopts.get('password'),
          db=mysqlopts.get('database'),
          charset=mysqlopts.get('charset', 'utf8'),
          debug=PageMakerDebuggerMixin in self.__class__.__mro__))
    return self.persistent.Get('__mysql')


class PageMakerSqliteMixin(object):
  """Adds SQLite support to PageMaker."""
  @property
  def connection(self):
    """Returns an SQLite database connection."""
    if '__sqlite' not in self.persistent:
      from underdark.libs.sqltalk import sqlite
      self.persistent.Set('__sqlite', sqlite.Connect(
          self.options['sqlite']['database']))
    return self._connection


class PageMakerSessionMixin(object):
  """Adds pysession support to PageMaker."""
  def __init__(self, *args, **kwds):
    super(PageMakerSessionMixin, self).__init__(*args, **kwds)
    self._userid = None

  @property
  def userid(self):
    """Provides the ID of the logged in user, if a valid session is available"""
    if '__session_userid' not in self.persistent:
      self.persistent.Set('__session_userid', self._GetSessionUserId())
    return self.persistent('__session_userid')

  def _GetSessionHandler(self):
    """Creates a session handler used to check sessions"""
    return pysession.Session(
        connection=self.connection,
        usertable='users',
        sessiontable='sessions',
        domain='true',
        remoteip=self.req['remote_addr'],
        columns={'user': 'emailaddress',
                 'password': 'password',
                 'useractive': 'status'},
        activestates='valid')

  def _GetSessionUserId(self):
    """Tries to validate a session by its cookiestring and IP address

    sets:
      self.options['login']: to True if logged in
      self.session['id']:    session id
      self.session['key']:   session password

    returns:
      True if logged in
      False if session is invalid
    """
    if 'session' not in self.cookies:
      return False
    raw_session = self.cookies.get['session'].value
    session_id, _sep, session_key = raw_session.partition(':')
    if not (session_id and session_key):
      return False
    try:
      session_handler = self._GetSessionHandler()
      session_handler.ResumeSession(session_id, session_key)
      return session_handler.userid
    except (pysession.SessionError, ValueError):
      return False


class Response(object):
  """Defines a full HTTP response.

  The full response consists of a required content part, and then optional
  http response code, cookies, additional headers, and a content-type.
  """
  # Default content-type for Page objects
  CONTENT_TYPE = 'text/html'

  def __init__(self, content='', content_type=CONTENT_TYPE,
               cookies=(), headers=None,  httpcode=200):
    """Initializes a Page object.

    Arguments:
      @ content: str
        The content to return to the client. This can be either plain text, html
        or the contents of a file (images for example).
      % content_type: str ~~ CONTENT_TYPE ('text/html' by default)
        The content type of the response. This should NOT be set in headers.
      % cookies: dict ~~ None
        Cookies are expected to be dictionaries, made up of the following keys:
        * Keys they MUST contain: `key`, `value`
        * Keys they MAY contain:  `expires`, `path`, `comment`, `domain`,
                                  `max-age`, `secure`, `version`, `httponly`
      % headers: dictionary ~~ None
        A dictionary mappging the header name to its value.
      % httpcode: int ~~ 200
        The HTTP response code to attach to the response.
    """
    if isinstance(content, unicode):
      self.content = content.encode('utf8')
    else:
      self.content = str(content)
    self.cookies = cookies
    self.httpcode = httpcode
    self.headers = headers or {}
    self.content_type = content_type

  def __repr__(self):
    return '<%s instance at %#x>' % (self.__class__.__name__, id(self))

  def __str__(self):
    return self.content
