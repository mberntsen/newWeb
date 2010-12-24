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


class ReloadModules(Exception):
  """Communicates the handler that it should reload the pageclass"""


class PageMaker(object):
  """Provides the base pagemaker methods for all the html generators."""
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

  def _InternalServerErrorDebug(self):
    """Returns a HTTP 500 response with detailed failure analysis."""
    def ParseStackFrames(stack=sys.exc_traceback):
      """Generates list items for traceback information.

      Each traceback item contains the file- and function name, the line numer
      and the source that belongs with it. For each stack frame, the local
      variables are also added to it, allowing proper analysis to happen.

      This most likely doesn't need overriding / redefining in a subclass.

      Arguments:
        % stack: traceback.stack ~~ sys.exc_traceback
          The stack frames to return analysis on.

      Yields:
        str: Template-parsed HTML with frame information.
      """
      def SourceLines(filename, line_num, context=3):
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
        for line_num in xrange(line_num - context, line_num + context + 1):
          yield self.parser.ParseString(
              '<li style="counter-reset: n [line]">[code]</li>',
              line=line_num - 1, code=linecache.getline(filename, line_num))
      while stack:
        frame = stack.tb_frame
        yield self.parser.Parse('stack_frame.xhtml', frame={
            'file': frame.f_code.co_filename,
            'scope': frame.f_code.co_name,
            'locals': ''.join(
                self.parser.Parse('var_list.xhtml', var=(name, repr(value)))
                for name, value in sorted(frame.f_locals.items())),
            'source': ''.join(SourceLines(frame.f_code.co_filename,
                                          frame.f_lineno))})
        stack = stack.tb_next
    import linecache
    self.parser.template_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), 'error_templates'))
    environ = [self.parser.Parse('var_list.xhtml', var=var)
               for var in sorted(self.req.ExtendedEnvironment().items())]
    post_data = [self.parser.Parse('var_list.xhtml', var=(var, self.post[var]))
                 for var in sorted(self.post)]
    query_args = [self.parser.Parse('var_list.html', var=(var, self.get[var]))
                  for var in sorted(self.get)]
    nulldata = '<li><em>NULL</em></li>'
    return Page(
        self.parser.Parse(
            'http_500.xhtml',
            environ=''.join(environ),
            query_args=''.join(query_args) or nulldata,
            post_data=''.join(post_data) or nulldata,
            exc={'type': sys.exc_type, 'value': sys.exc_value,
                 'traceback': ''.join(ParseStackFrames())}),
        httpcode=200)

  @staticmethod
  def _InternalServerErrorProduction():
    """Returns a text/plain notification about an internal server error.

    Clients should override this in their own pagemaker subclasses.
    """
    return Page('INTERNAL SERVER ERROR (HTTP 500)',
                content_type='text/plain', httpcode=500)

  def InternalServerError(self):
    """Processes an Internal Server Error.

    If the environment variable DEBUG is True, the _InternalServerErrorDebug
    method is returned, otherwise, _InternalServerErrorProduction is returned.
    """
    if self.req.env['DEBUG']:
      return self._InternalServerErrorDebug()
    return self._InternalServerErrorProduction()

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


#TODO(Elmer): Deprecate BasePageMaker in favor of PageMaker.
class BasePageMaker(PageMaker):
  """A trivial subclass of PageMaker, maintaining backwards compatibility."""


#TODO(Elmer): Rename this 'Response', to better cover the purpose.
class Page(object):
  """Defines a full HTTP response.

  The full response consists of a required content part, and then optional
  http response code, cookies, additional headers, and a content-type.
  """
  # Default content-type for Page objects
  CONTENT_TYPE = 'text/html'

  def __init__(self, content, content_type=CONTENT_TYPE,
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
    self.content = content
    self.cookies = cookies
    self.httpcode = httpcode
    self.headers = headers or {}
    self.content_type = content_type

  def __repr__(self):
    return '<%s instance at %#x>' % (self.__class__.__name__, id(self))

  def __str__(self):
    return self.content


def Handler(req, pageclass, routes, config_file='config.cfg', debug=False):
  """Handles a web request through processing the routes list.

  The url in the received `req` object is taken and matches against the
  available `routes` (refer to Router() for more documentation on this).

  Once a method is known, the request and the arguments that came from the
  Router return are passed to the relevant `pageclass` method.

  The return value from the `pageclass` method will be written to the `req`
  object. When this is completed, the Handler will issue an apache.OK value,
  indicating that it has successfully processed the request.

  The processing in this function knows two main interruptions:
    1) Exception `NoRouteError`:
       This raises apache.SERVER_RETURN with an apache.INTERNAL_SERVER_ERROR
       attached. No route exists to tell the Handler what to do, this situation
       should usually be prevented by a catchall route.
    2) Exception `ReloadModules`
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
    % debug: boolean ~~ False
      The DEBUG request-environment variable is set to this boolean value.

  Returns:
    apache.OK: signal for Apache to send the page to the client. Ignored by
               the standalone version of uWeb.

  Raises:
    apache.SERVER_RETURN: Details on these exceptions included above.
  """
  req = request.Request(req)
  req.env['DEBUG'] = bool(debug)
  pages = pageclass(req, config_file=config_file)
  try:
    req_method, req_arguments = Router(routes, req.env['PATH_INFO'])
    content = getattr(pages, req_method)(*req_arguments)
  except ReloadModules, content:
    content = str(content)
    if pageclass.__name__ in sys.modules:
      content += templateparser.HtmlEscape(reload(pageclass))
  except (Exception, NoRouteError):
    content = pages.InternalServerError()

  if not isinstance(content, Page):
    content = Page(content)
  req.SetHttpStatus(content.httpcode)
  req.SetContentType(content.content_type)
  for header_pair in content.headers.iteritems():
    req.AddHeader(*header_pair)
  for cookie in content.cookies:
    req.AddCookie(**cookie)
  req.Write(content.content)
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
  def _FixEntities(match):
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
  return HTML_ENTITY_SEARCH.sub(_FixEntities, html)


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
