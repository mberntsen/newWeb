#!/usr/bin/python
"""Underdark Web Framework -- uWeb"""

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.14'


# Standard modules
import ConfigParser
import os
import re
import sys

# Add the ext_lib directory to the path
# This ensures the logging module can be loaded
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), 'ext_lib')))
from underdark.libs import logging

# Package modules
from . import pagemaker
from . import request

# Package classes
from .response import Response
from .response import Redirect
from .pagemaker import PageMaker
from .pagemaker import DebuggingPageMaker


class Error(Exception):
  """Superclass used for inheritance and external excepion handling."""


class ImmediateResponse(Exception):
  """Used to trigger an immediate repsonse, foregoing the regular returns."""


class NoRouteError(Error):
  """The server does not know how to route this request"""


class NewWeb(object):
  """Returns a configured closure for handling page requests.

  This closure is configured with a precomputed set of routes and handlers using
  the Router function. After this, incoming requests are processed and delegated
  to the correct PageMaker handler.

  The url in the received `req` object is taken and matches against the
  `router`` (refer to Router() for more documentation on this).


  Takes:
    @ page_class: PageMaker
      Class that holds request handling methods as defined in the `routes`
    @ router: request router
      The result of the Router() function.
    @ config: dict
      Configuration for the PageMaker. Typically contains entries for database
      connections, default search paths etc.

  Returns:
    RequestHandler: Configured closure that is ready to process requests.
  """
  def __init__(self, page_class, routes, config):
    self.page_class = page_class
    self.router = Router(routes)
    self.config = config if config is not None else {}

  def __call__(self, env, start_response):
    """WSGI request handler.

    Accpepts the WSGI `environment` dictionary and a function to start the
    response and returns a response iterator.
    """
    req = request.Request(env)
    pages = self.page_class(req, config=self.config)
    try:
      # We're specifically calling _PostInit here as promised in documentation.
      # pylint: disable=W0212
      pages._PostInit()
      # pylint: enable=W0212
      method, args = self.router(req.env['PATH_INFO'])
      response = getattr(pages, method)(*args)
    except pagemaker.ReloadModules, message:
      reload_message = reload(sys.modules[self.page_class.__module__])
      response = Response(
          content='%s\n%s' % (message, reload_message))
    except ImmediateResponse, response:
      response = response[0]
    except (NoRouteError, Exception):
      response = pages.InternalServerError(*sys.exc_info())

    if not isinstance(response, Response):
      response = Response(content=response)
    start_response(response.status, response.headers)
    return [response.content]


def ParseConfig(config_file):
  """Parses the given `config_file` and returns it as a nested dictionary."""
  parser = ConfigParser.SafeConfigParser()
  try:
    parser.read(config_file)
  except ConfigParser.ParsingError:
    raise ValueError('Not a valid config file: %r.' % config_file)
  return dict((section, dict(parser.items(section)))
              for section in parser.sections())


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


def ServerSetup(page_class, routes, config=None):
  """Sets up and starts serving a WSGI application based on wsgiref."""
  # Configuration based on constants provided
  application = NewWeb(page_class, routes, config=config)

  from wsgiref.simple_server import make_server
  wsgi_server = make_server('localhost', 8001, application)
  wsgi_server.serve_forever()
