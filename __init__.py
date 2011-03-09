#!/usr/bin/python
"""Underdark web interface, or uWeb interface"""
from __future__ import with_statement

__author__ = 'Jan Klopper <jan@underdark.nl>'
__version__ = '0.4'

# Standard modules
import htmlentitydefs
import os
import re
import sys
import warnings

# Import apache, or a mock for standalone purposes
try:
  from mod_python import apache
  STANDALONE = False
except ImportError:
  import apache_mock as apache
  import standalone
  STANDALONE = True

# Custom modules
from underdark.libs import app
from underdark.libs.uweb.pagemaker import *
from underdark.libs.uweb import request

# Regex to match HTML entities and character references with.
HTML_ENTITY_SEARCH = re.compile('&#?\w+;')


class NoRouteError(Exception):
  """The server does not know how to route this request"""


class PageMaker(PageMakerMysqlMixin, PageMakerSessionMixin, BasePageMaker):
  """The basic PageMaker class, providing MySQL and Pysession support."""


class DebuggingPageMaker(PageMakerDebuggerMixin, PageMaker):
  """The same basic PageMaker, with added debugging on HTTP 500."""


def Handler(req, pageclass, routes, config_file=None):
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
       This triggers the PageMaker method InternalServerError, which generates
       an appropriate response for the requesting client.
    2) Exception `ReloadModules`
       This halts any running execution of web-requests and reloads the
       `pageclass`. The response will be a text/plain page with the result of
       the reload statement

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
    apache.DONE: signal for Apache to send the page to the client. Ignored by
                 the standalone version of uWeb.
  """
  req = request.Request(req)
  pages = pageclass(req, config_file=config_file)
  try:
    req_method, req_arguments = Router(routes, req.env['PATH_INFO'])
    content = getattr(pages, req_method)(*req_arguments)
  except ReloadModules, message:
    reload_message = reload(sys.modules[pageclass.__module__])
    content = Response(content='%s\n%s' % (message, reload_message))
  except (Exception, NoRouteError):
    content = pages.InternalServerError()

  if not isinstance(content, Response):
    content = Response(content=content)
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
