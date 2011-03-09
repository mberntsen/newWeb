#!/usr/bin/python
"""An uweb info page and testcase."""

# Custom modules
from underdark.libs import uweb
from underdark.libs.uweb.uweb_info import pages

__author__ = 'Jan Klopper <jan@underdark.nl>'
__version__ = '0.1'

PACKAGE = 'uweb_info'
PAGE_CLASS = pages.PageMaker
ROUTES = (
    ('/static/(.*)', 'Static'),
    ('/(broken.*)', 'FourOhFour'),
    ('/haltandcatchfire', 'MakeFail'),
    ('/text', 'Text'),
    ('/redirect/(.*)', 'Redirect'),
    ('/OpenIDLogin', '_OpenIdInitiate'),
    ('/OpenIDValidate', '_OpenIdValidate'),
    ('/(.*)', 'Index'))


# This function needs to be called `handler` for use with the default mod_python
# processor (publisher). If you're only using it for the standalone version of
# uWeb, you could give it another name if you have a good reason for it.
def handler(request):
  """uWeb request router.

  This router uses the constant `ROUTES` to provide a request router for the
  uWeb Handler. `ROUTES` is an iterable consisting of 2-tuples, each of which
  defines a regular expression and a method name. The regular expressions are
  tested in order, and must match the whole URL that is requested.
  If a match is found, traversal stops and the method name corresponding the
  regex is looked up on the provided `PAGE_CLASS`. This method is then used to
  generate a response.

  Any capture groups defined in the regular expressions of the `ROUTES` will
  be provided as arguments on the methods they call to.

  If none of the regexen match, the uWeb.Handler will issue a HTTP 500.

  Additionally, a constant `PATH` is used, which provides mod_python with the
  base path to find its dependencies (e.g. template directories).

  Arguments:
    @ request: apache.request or BaseHTTPServer.request
      The basic request object as received by the webserver. This same object
      will be used to generate a response with, as it represents a socket
      connection to the requesting entity.

  Returns:
    @ object: The response received from the uweb.Handler after processing the
              request. In most cases, the return value is of little interest,
              as the `request` argument will be used to generate a response.
  """
  return uweb.Handler(request, PAGE_CLASS, ROUTES)


uweb.ServerSetup(handler)
