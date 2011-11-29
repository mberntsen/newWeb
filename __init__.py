#!/usr/bin/python
"""Underdark web interface, or uWeb interface"""
from __future__ import with_statement

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.8'

# Standard modules
import htmlentitydefs
import os
import re
import sys
import warnings

try:
  # Import the apache module from inside mod_python. This allows us to trigger
  # a DONE so that Apache knows when and how to respond to the client.
  from mod_python import apache
except ImportError:
  # We are *NOT* running from inside Apache. Import the standalone routines so
  # that we can set up a local webserver

  # The following global exists to signal the apache module is NOT loaded.
  # pylint: disable=C0103
  apache = False
  # pylint: enable=C0103
  import standalone

# Custom modules
from underdark.libs import app
from underdark.libs import udders
from underdark.libs.uweb.pagemaker import *
from underdark.libs.uweb import request

# Regex to match HTML entities and character references with.
HTML_ENTITY_SEARCH = re.compile('&#?\w+;')


class Error(Exception):
  """Superclass used for inheritance and external excepion handling."""


class ImmediateResponse(Exception):
  """Used to trigger an immediate repsonse, foregoing the regular returns."""

class NoRouteError(Error):
  """The server does not know how to route this request"""


class PageMaker(PageMakerMysqlMixin, PageMakerSessionMixin, BasePageMaker):
  """The basic PageMaker class, providing MySQL and Pysession support."""


class DebuggingPageMaker(PageMakerDebuggerMixin, PageMaker):
  """The same basic PageMaker, with added debugging on HTTP 500."""


def Handler(pageclass, routes, config=None):
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
  def RealHandler(req, pageclass=pageclass, routes=routes, config=config):
    req = request.Request(req)
    pages = pageclass(req, config=config)
    try:
      req_method, req_arguments = Router(routes, req.env['PATH_INFO'])
      response = getattr(pages, req_method)(*req_arguments)
    except ReloadModules, message:
      reload_message = reload(sys.modules[pageclass.__module__])
      response = Response(content='%s\n%s' % (message, reload_message))
    except ImmediateResponse, response:
      response = response[0]
    except (Exception, NoRouteError):
      response = pages.InternalServerError()

    if not isinstance(response, Response):
      response = Response(content=response)
    req.SetHttpStatus(response.httpcode)
    req.SetContentType(response.content_type)
    for header_pair in response.headers.iteritems():
      req.AddHeader(*header_pair)
    for cookie in response.cookies:
      req.AddCookie(**cookie)
    req.Write(response.content)
    if apache:
      return apache.DONE

  return RealHandler


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


def ServerSetup(apache_logging=True):
  """Sets up a the runtime environment of the webserver.

  If the router (the caller of this function) runs in `standalone` mode (defined
  by absence of the `apache` module), the runtime environment will be a service
  as defined by the app framework.

  If provided through the CONFIG constant, the configuration file will be read
  and parsed. This configuration will be used for the `StandAloneServer` for
  host and port configurations, and the PageMaker will use it for all sorts of
  configuration, for example database connection into and default search paths.

  Logging:
    For both `standalone` and `apache` mode, the PACKAGE constant will set the
    directory under which log files should be accumulated.
    * For `apache` this will create a log database 'apache.sqlite' only, and if
      the PACKAGE constant is not available, this will default to 'uweb_project'
    * For `standalone` mode, there will be '.sqlite' log files for each router,
      and the base-name will be the same as that of the router. Additionally
      there will be access and error logs, again sharing the base name with the
      router itself. The default directory name to bundle these files under will
      be the name of the directory one up from where the router runs.

  Arguments:
    % apache_logging: bool ~~ True
      Whether or not to log when running from inside Apache. Enabling logging
      will cause the log-database to be opened and closed with every request.
      This might significantly affect performance.
  """
  router = sys._getframe(1)
  router_file = router.f_code.co_filename

  # Configuration based on constants provided
  package_name = router.f_globals.get('PACKAGE')
  router_pages = router.f_globals['PAGE_CLASS']
  router_routes = router.f_globals['ROUTES']
  router_config = udders.ParseConfig(os.path.join(
      os.path.dirname(router_file), router.f_globals['CONFIG']))
  handler = Handler(router_pages, router_routes, config=router_config)
  if not apache:
    router_name = os.path.splitext(os.path.basename(router_file))[0]
    package_dir = os.path.abspath(os.path.join(
        os.path.dirname(router_file), os.path.pardir))
    package_name = package_name or os.path.basename(package_dir)

    def main(router=handler):
      """Sets up a closure that is compatible with the UD app framework."""
      standalone.StandAloneServer(router, router_name, router_config).Start()

    app.Service(stack_depth=3, app=main, working_dir=package_dir,
                package=package_name)
  else:
    router.f_globals['handler'] = handler
    if apache_logging:
      package = package_name or 'uweb_project'
      log_dir = app.FirstWritablePath(app.MakePaths(app.LOGGING_PATHS, package))
      app.SetUpLogging(os.path.join(log_dir, 'apache.sqlite'))
