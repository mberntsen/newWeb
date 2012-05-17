#!/usr/bin/python
"""Underdark Web Framework -- uWeb"""

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.14'


# Standard modules
import htmlentitydefs
import os
import re
import sys
import warnings

# Underdark package module
#
# If the underdark package is not directly available, add the 'ud_lib'
# directory to the module path.
try:
  import underdark
except ImportError:
  sys.path.append(
      os.path.abspath(os.path.join(os.path.dirname(__file__), 'ext_lib')))
# Underdark modules
from underdark.libs import app
from underdark.libs.app import logging

try:
  # Import this module to check uWeb runmode (success means MOD_PYTHON)
  from mod_python import apache
except ImportError:
  # uWeb will run in STANDALONE mode
  class _MockApache(object):
    def __nonzero__(self):
      return False
  # Make sure we have a global `apache` we can test for truthness later on.
  # pylint: disable=C0103
  apache = _MockApache()
  # pylint: enable=C0103

# Package modules
from . import pagemaker
from . import request
from . import standalone

# Package classes
from .response import Response
from .response import Redirect
from .pagemaker import PageMaker
from .pagemaker import DebuggingPageMaker

# Regex to match HTML entities and character references with.
HTML_ENTITY_SEARCH = re.compile('&#?\w+;')


class Error(Exception):
  """Superclass used for inheritance and external excepion handling."""


class ImmediateResponse(Exception):
  """Used to trigger an immediate repsonse, foregoing the regular returns."""

class NoRouteError(Error):
  """The server does not know how to route this request"""


def Handler(page_class, routes, config=None):
  """Returns a configured closure for handling page requests.

  This closure is configured with a precomputed set of routes and handlers using
  the Router function. After this, incoming requests are processed and delegated
  to the correct PageMaker handler.

  The url in the received `req` object is taken and matches against the
  available `routes` (refer to Router() for more documentation on this).


  Takes:
    @ page_class: PageMaker
      Class that holds request handling methods as defined in the `routes`
    @ routes: iterable of 2-tuple
      Each tuple is a pair of pattern and handler name. More info in Router().
    % config: dict ~~ None
      Configuration for the PageMaker. Typically contains entries for database
      connections, default search paths etc.

  Returns:
    RequestHandler: Configured closure that is ready to process requests.
  """
  router = Router(routes)
  del routes

  def RequestHandler(req):
    """Closure to handle incoming web requests.

    Incoming requests are transformed to a proper uWeb Request object, and then
    processed by the `router`, which is provided by the outer scope.

    The router may return in two ways:
      1) Returns a handler and arguments, in which case these are used to
         create a regular response for the client.
      2) Raise `NoRouteError`, in which case `InternalServerError` on the
         pagemaker is returned instead.

    During processing of a request, two additional error situations may come up:
      1) `ReloadModules`
         This halts any running execution of web-requests and reloads the
         `pageclass`. The response will be a text/plain page with the result of
         the reload statement
      2) Any other Exception
         Like NoRouteError this will return `InternalServerError` to the client.

    Returns:
      apache.DONE: signal for Apache to send the page to the client.
                   This is ignored by the standalone version of uWeb.
    """
    req = request.Request(req)
    pages = page_class(req, config=config)
    try:
      # We're specifically calling _PostInit here as promised in documentation.
      # pylint: disable=W0212
      pages._PostInit()
      # pylint: enable=W0212
      method, args = router(req.env['PATH_INFO'])
      response = getattr(pages, method)(*args)
    except pagemaker.ReloadModules, message:
      reload_message = reload(sys.modules[page_class.__module__])
      response = Response(
          content='%s\n%s' % (message, reload_message))
    except ImmediateResponse, response:
      response = response[0]
    except (NoRouteError, Exception):
      response = pages.InternalServerError(*sys.exc_info())

    if not isinstance(response, Response):
      response = Response(content=response)
    req.SetHttpCode(response.httpcode)
    req.SetContentType(response.content_type)
    for header_pair in response.headers.iteritems():
      req.AddHeader(*header_pair)
    req.Write(response.content)
    if apache:
      return apache.DONE
  return RequestHandler


def Router(routes):
  """Returns the first request handler that matches the request URL.

  The `routes` argument is an iterable of 2-tuples, each of which contain a
  pattern (regex) and the name of the handler to use for matching requests.

  Before returning the closure, all regexen are compiled, and handler methods
  are retrieved from the provided `page_class`.

  Arguments:
    @ routes: iterable of 2-tuples.
      Each tuple is a pair of `pattern` and `handler`, both are strings.

  Returns:
    RequestRouter: Configured closure that processes urls.
  """
  req_routes = []
  for pattern, method in routes:
    req_routes.append((re.compile(pattern + '$', re.UNICODE), method))

  def RequestRouter(url):
    """Returns the appropriate handler and arguments for the given `url`.

    The`url` is matched against the compiled patterns in the `req_routes`
    provided by the outer scope. Upon finding a pattern that matches, the
    match groups from the regex and the unbound handler method are returned.

    N.B. The rules are such that the first matching route will be used. There
    is no further concept of specificity. Routes should be written with this in
    mind.

    Arguments:
      @ url: str
        The URL requested by the client.

    Raises:
      NoRouteError: None of the patterns match the requested `url`.

    Returns:
      2-tuple: handler method (unbound), and tuple of pattern matches.
    """
    for pattern, handler in req_routes:
      match = pattern.match(url)
      if match:
        return handler, match.groups()
    raise NoRouteError(url +' cannot be handled')
  return RequestRouter


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
  # We need _getframe here, there's not really a neater way to do this.
  # pylint: disable=W0212
  router = sys._getframe(1)
  # pylint: enable=W0212
  router_file = router.f_code.co_filename
  router_name = os.path.splitext(os.path.basename(router_file))[0]

  # Configuration based on constants provided
  package_name = router.f_globals.get('PACKAGE')
  router_pages = router.f_globals['PAGE_CLASS']
  router_routes = router.f_globals['ROUTES']
  config_file = router.f_globals.get('CONFIG')
  if config_file:
    router_config = app.ParseConfig(os.path.join(
        os.path.dirname(router_file), config_file))
  else:
    router_config = {}
  handler = Handler(router_pages, router_routes, config=router_config)
  if not apache:
    package_dir = os.path.abspath(os.path.join(
        os.path.dirname(router_file), os.path.pardir))
    package_name = package_name or os.path.basename(package_dir)

    def main(router=handler):
      """Sets up a closure that is compatible with the UD app framework."""
      server = standalone.StandAloneServer(router, router_name, router_config)
      server.serve_forever()

    app.Service(stack_depth=3, app=main, working_dir=package_dir,
                package=package_name)
  else:
    router.f_globals['handler'] = handler
    if apache_logging:
      package = package_name or 'uweb_project'
      log_dir = app.FirstWritablePath(app.MakePaths(app.LOGGING_PATHS, package))
      app.SetUpLogging(os.path.join(log_dir, '%s.sqlite' % router_name))
