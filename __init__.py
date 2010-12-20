#!/usr/bin/python
"""Underdark web interface, or uWeb interface"""
from __future__ import with_statement

__author__ = 'Jan Klopper <jan@underdark.nl>'
__version__ = '0.2'

#Standard modules
try:
  from mod_python import apache
  STANDALONE = False
except ImportError:
  import apache_mock as apache
  import standalone
  STANDALONE = True

import htmlentitydefs
import mimetypes
import os
import re
import sys
import warnings

# Custom modules
from underdark.libs import app
from underdark.libs import logging
from underdark.libs import pysession
from underdark.libs import udders
import request
import templateparser

# Regex to match HTML entities and character references with.
HTML_ENTITY_SEARCH = re.compile('&#?\w+;')


class DatabaseError(Exception):
  """The database server has gone away"""


class NoRouteError(Exception):
  """The server does not know how to route this request"""


class HttpMovedPermanently(Exception):
  """Communicate a http redirect to the upper layers"""


class ReloadModules(Exception):
  """Communicates the handler that it should reload the pageclass"""


class BasePageMaker(object):
  """Provides the base pagemaker methods for all the html generators
  """
  # Default content-type for the pagemaker
  DEFAULT_CONTENT_TYPE = 'text/html'

  # Base paths for templates and public data. These are used in the PageMaker
  # classmethods that set up paths specific for that pagemaker.
  PUBLIC_DIR = 'www'
  TEMPLATE_DIR = 'templates'

  def __init__(self, req, config_file=None):
    """sets up the template parser and database connections

    Takes:
      sessiondata: dict:
        remote_addr: str, ip addres of client
        cookies:     str, cookies from header
    """
    self.__SetupPaths()
    self._connection = None
    self._cursor = None
    self._parser = None
    self._userid = None
    self.session_handler = None
    self.options = udders.ParseConfig(os.path.join(self.LOCAL_DIR, config_file))
    self.req = req

    # GET/POST/Cookie vars
    self.cookies = req.vars['cookie']
    self.get = req.vars['get']
    self.post = req.vars['post']

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

  #TODO(Elmer): Put the connection property in separate Mixin classes
  # This allows the developer to simple inherit from the desired mixin,
  # and receive the appropriate connection, without making this needlessly
  # complex, and error prone. (A bad config block can now break the application,
  # which is not desirable).
  @property
  def connection(self):
    if not self._connection:
      if 'mysql' in self.options:
        from underdark.libs.sqltalk import mysql
        mysqlopts = self.options['mysql']
        self._connection = mysql.Connect(
            host=mysqlopts.get('host', 'localhost'),
            user=mysqlopts.get('user'),
            passwd=mysqlopts.get('password'),
            db=mysqlopts.get('database'),
            charset=mysqlopts.get('charset', 'utf8'))
      elif 'sqlite' in self.options:
        from underdark.libs.sqltalk import sqlite
        self._connection = sqlite.Connect(self.options['sqlite']['database'])
      elif 'mongodb' in self.options:
        import pymongo
        try:
          self._connection = pymongo.connection.Connection(
              host=self.options['mongodb'].get('host', 'localhost'),
              port=self.options['mongodb'].get('port', None))
        except pymongo.errors.AutoReconnect:
          raise DatabaseError('MongoDb is unavailable')
        except pymongo.errors.ConnectionFailure:
          raise DatabaseError('MongoDb is unavailable')
      else:
        raise TypeError('E_NODATABASE')
    return self._connection

  @property
  def cursor(self):
    """Provides a cursor to the database as specified in the options dict"""
    warnings.warn('Cursor property is disappearing, please use the connection '
                  'property and its context manager instead',
                  DeprecationWarning, stacklevel=2)
    logging.LogWarning('Cursor property is disappearing, please use the '
                       'connection property and its context manager instead')
    if not self._cursor:
      if 'mysql' in self.options:
        self._cursor = self.connection.Cursor()
      elif 'sqlite' in self.options:
        self._cursor = self.connection.Cursor()
      elif 'mongodb' in self.options:
        self._cursor = getattr(
            self.connection, self.options['mongodb']['database'])
    return self._cursor

  @property
  def parser(self):
    """Provides a templateparser.Parser instance.

    If the config file specificied a [templates] section and a `path` is
    assigned in there, this path will be used.
    Otherwise, the `TEMPLATE_DIR` will be used to load templates from.
    """
    if not self._parser:
      self._parser = templateparser.Parser(
          self.options.get('templates', {}).get('path', self.TEMPLATE_DIR))
    return self._parser

  @property
  def userid(self):
    """Provides the ID of the logged in user, if a valid session is available"""
    if not self._userid:
      self._userid = self._GetSessionUserId()
    return self._userid

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
          #TODO(Jan): add mime-type guessing based on the path extension,
          # and a custom dict, if that fails, add Magic Mime detection
          #XXX(Elmer): mimetypes.guess_type is already strictly extension based.
          content_type = 'text/plain'
        return Page(content=staticfile.read(),
                    content_type=content_type)
    except IOError:
      message = 'This is not the path you\'re looking for. No such file %r' % (
          self.req.env['PATH_INFO'])
      return Page(content=message, httpcode=404, content_type='text/plain')


class Page(object):
  def __init__(self, content, httpcode=200, cookies=(),
               headers=None, content_type='text/html'):
    self.content = content
    self.cookies = cookies
    self.httpcode = httpcode
    self.headers = headers or {}
    self.content_type = content_type


class Record(dict):
  def __init__(self, record, fields=None):
    super(Record, self).__init__(record)
    #XXX(Elmer): Can use these fields to validate data @ Save() time.
    # A record with inappropriate NULLs can be rejected.
    self._fields = fields


class RecordFactory(object):
  ID_FIELD = 'ID'  #XXX(Elmer): Could dump this in favor of the prikey field?
  RECORD_CLASS = Record
  TABLE = 'subclass_defined'

  def __init__(self, connection):
    self.connection = connection
    self._fields = []
    with self.connection as cursor:
      for row in cursor.Execute('EXPLAIN %s' % self.TABLE):
        self._fields.append(dict(row.items))

  def _SelectNaiveRecords(self, **sqltalk_options):
    with self.connection as cursor:
      records = cursor.Select(table=self.TABLE, **sqltalk_options)
    for record in records:
      yield self.RECORD_CLASS(record.items)

  def GetById(self, record_id):
    conditions = '%s = %s' % (self.ID_FIELD,
                              self.connection.EscapeValues(record_id))
    return self._SelectNaiveRecords(conditions=conditions).next()


def Handler(req, pageclass, routes, config_file='config.cfg'):
  """Handles a web request through processing the routes list.

  The url in the received `req` object is taken and matches against the
  available `routes` (refer to Router() for more documentation on this).

  Once a method is known, the request and the arguments that came from the
  Router return are passed to the relevant `pageclass` method.

  The return value from the `pageclass` method will be written to the `req`
  object. When this is completed, the Handler will issue an apache.OK value,
  indicating that it has successfully processed the request.

  The processing in this function knows three main interruptions:
    1) Exception `NoRouteError`:
       This raises apache.SERVER_RETURN with an apache.INTERNAL_SERVER_ERROR
       attached. No route exists to tell the Handler what to do, this situation
       should usually be prevented by a catchall route.
    2) Exception `HttpMovedPermanently`
       This raises apache.SERVER_RETURN with an apache.HTTP_MOVED_PERMANENTLY
       attached, telling Apache there has been a redirect.
    3) Exception `ReloadModules`
       This halts any running execution of web-requests and reloads the
       `pageclass`. The returned page will be the return of the relad() action.

  Takes:
    @ req: obj
      the apache request object
    @ pageclass: PageMaker
      Class that holds request handling methods as defined in the `routes`
    @ routes: iterable of 2-tuple
      Each tuple is a pair of pattern and handler. More info in Router().
    % config_file: str ~~ 'config.cfg'
      Filename to read handler configuration from. This typically contains
      sections for databases and the like.

  Returns:
    apache.OK: signal for Apache to send the page to the client. Ignored by
               the standalone version of uWeb.

  Raises:
    apache.SERVER_RETURN: Details on these exceptions included above.
  """
  req = request.Request(req)

  try:
    req_method, req_arguments = Router(routes, req.env['PATH_INFO'])
  except NoRouteError:
    # This needs to be done, for BaseHTTP (as it always writes immediately):
    req.SetHttpStatus(500)
    req.SetContentType(pageclass.DEFAULT_CONTENT_TYPE)
    req.Write('Sorry, badly configured server')
    raise apache.SERVER_RETURN(apache.DONE, apache.HTTP_INTERNAL_SERVER_ERROR)

  try:
    pages = pageclass(req, config_file=config_file)
    content = getattr(pages, req_method)(*req_arguments)
  except HttpMovedPermanently, location:
    #TODO(Elmer): This will be removed next version, in favour of returning
    # a Page with a Location header and a relevant httpcode.
    req.SetHttpStatus(301)
    req.AddHeader('Location', str(location))
    raise apache.SERVER_RETURN(apache.DONE, apache.HTTP_MOVED_PERMANENTLY)
  except ReloadModules, content:
    content = str(content)
    if pageclass.__name__ in sys.modules:
      content += HtmlEscape(reload(pageclass))

  if isinstance(content, Page):
    req.SetHttpStatus(content.httpcode)
    req.SetContentType(content.content_type)
    for header_pair in content.headers.iteritems():
      #XXX(Elmer): `req.headers` is expected to be a dictionary.
      req.AddHeader(*header_pair)
    for cookie in content.cookies:
      #XXX(Elmer): All cookies are expected to be dicts.
      # Keys they MUST contain: `key`, `value`
      # Keys they MAY contain:  `expires`, `path`, `comment`, `domain`,
      #                         `max-age`, `secure`, `version`, `httponly`

      req.AddCookie(**cookie)
    req.Write(content.content)
  else:
    req.SetHttpStatus(200)
    req.SetContentType(pages.DEFAULT_CONTENT_TYPE)
    req.Write(content)
  return apache.DONE


def Router(routes, url):
  """Returns the first request handler that matches the request URL.

  Each `url` is matched against the `routes` mapping. The `routes` mapping
  consists of 2-tuples that define a `pattern` and a `handler`:
  - The `pattern` part of each route is a regular expression that the `url`
    is matched against. If it matches, the paired `handler` will be returned.
  - The `handler` portion of each route is a string that indicated the method
    on the PageMaker that is to be called to handle the requested `url`.

  Once a handler has been found to match, a 2-tuple of that handler, and the
  matches from the pattern regex is returned.

  More specific is, in this context, synonymous with being mentioned later.

  Takes:
    @ routes: iterable of 2-tuples.
      Each tuple is a pair of `pattern` and `handler`.
    @ requested_url: str
      Requested URL that is to be matched against the mapping.

  Returns:
    2-tuple: handler name, and matches resulting from `pattern` regex.

  Raises:
    NoRouteError: None of the patterns match the requested `url`.
  """
  for pattern, handler in routes:
    matches = re.match(pattern + '$', url)
    if matches:
      return handler, matches.groups()
  raise NoRouteError(url +' cannot be handled')


def HtmlEscape(text):
  """Escapes the 5 characters deemed by XML to be unsafe if left unescaped.

  The relevant defined set consists of the following characters: &'"<>

  Takes:
    @ html: str
      The html string with html character entities.

  Returns:
    str: the input, after turning entites back into raw characters.
  """
  if not isinstance(text, basestring):
    text = unicode(text)
  html = text.replace('&', '&amp;')
  html = html.replace('"', '&quot;')
  html = html.replace('\'', '&#39;')  # &apos; is valid, but poorly supported.
  html = html.replace('>', '&gt;')
  return html.replace('<', '&lt;')


def HtmlUnescape(html):
  """Replaces html named entities and character references with raw characters.

  Unlike its HtmlEscape counterpart, this function supports all named entities
  and every character reference possible, through use of a regular expression.

  Takes:
    @ html: str
      The html string with html named entities and character references.

  Returns:
    str: The input, with all entities and references replaces by unicode chars.
  """
  def FixEntities(match):
    text = match.group(0)
    if text[:2] == "&#":
      # character reference
      try:
        if text[2] == 'x':
          return unichr(int(text[3:-1], 16))
        return unichr(int(text[2:-1]))
      except ValueError:
        pass
    else:
      # named entity
      try:
        return unichr(htmlentitydefs.name2codepoint[text[1:-1]])
      except KeyError:
        pass
    return text # leave as is
  return HTML_ENTITY_SEARCH.sub(FixEntities, html)


def ServerSetup(router):
  """Sets up a the runtime environment of the webserver.

  If the router (the caller of this function) runs in STANDALONE mode, the
  runtime environment will be a service as defined by the app framework.
  This reads a config file to use for configuring the webserver itself, sets up
  output redirection and logging to sqlite database.

  In the STANDALONE mode, the assumption is made that the passed in `router` is
  a file that lives in a directory one path below what is considered the
  `package`. This package name will be used to create a directory for log files.

  Also, if present, the file 'config.cfg' will be read from the package path
  and used to configure the webserver. The config portion used is [server],
  and the supported settings are 'host' and 'port'.

  When not runnin in STANDALONE mode, this function sets up logging to sqlite,
  in a directory that's defined by the router's module constant PACKAGE.
  If this constant is not present, it will default to 'mod_python_project'.

  Arguments:
    @ router: function
      The main router of the webserver.
    % package: str ~~ 'mod_python_project'
      The application's common name. This is used in the creation of the
      directory that will hold the application's log files.
      For Apache, this name is required, for BaseHTTP, it's optional, and the
      default is the directory name two levels up from the router.
  """
  if STANDALONE:
    # The following is based on the assumption that the package path contains a
    # directory (typically `www`) which contains the router module.
    # Third from the right is the package directory's name, which we need.
    router_file = sys.modules['__main__'].__file__
    package_dir = os.path.abspath(os.path.join(router_file, '../..'))
    package_name = os.path.basename(package_dir)
    config_location = os.path.join(package_dir, 'config.cfg')
    if not os.path.exists(config_location):
      config_location = None
    def main(router=router, **options):
      """Sets up a closure that is compatible with the UD app framework."""
      standalone.RunStandAlone(router, **options)

    app.Service(stack_depth=3, app=main, config=config_location,
                working_dir=package_dir, package=package_name)
  else:
    #os.chdir(working_dir)
    # For mod_python, the current working directory is set to the package dir.
    package = router.func_globals.get('PACKAGE', 'mod_python_project')
    log_dir = app.FirstWritablePath(app.MakePaths(app.LOGGING_PATHS, package))
    app.SetUpLogging(os.path.join(log_dir, 'apache.sqlite'))
