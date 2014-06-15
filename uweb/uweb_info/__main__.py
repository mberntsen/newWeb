#!/usr/bin/python
"""An uweb info page and testcase."""

# Standard modules
import os

# Third-party modules
import uweb

# Application components
from . import pages


def application():
  """Creates a newWeb application.

  The application is created from the following arguments:

  - The presenter class (PageMaker) which implements the request handlers.
  - The routes iterable, where each 2-tuple defines a url-pattern and a the
    name of a presenter method which should handle it.
  - The configuration file (ini format) from which settings should be read.
  """
  config = os.path.join(os.path.dirname(__file__), 'config.ini')
  routes = [
      ('/static/(.*)', 'Static'),
      ('/(broken.*)', 'FourOhFour'),
      ('/haltandcatchfire', 'MakeFail'),
      ('/json', 'Json'),
      ('/text', 'Text'),
      ('/redirect/(.*)', 'Redirect'),
      ('/OpenIDLogin', '_OpenIdInitiate'),
      ('/OpenIDValidate', '_OpenIdValidate'),
      ('/ULF-Challenge', '_ULF_Challenge'),
      ('/ULF-Login', '_ULF_Verify'),
      ('/([\w\-_/]*)', 'Index'),
      ('/(.*)', 'NonWordCatchall')]
  return uweb.NewWeb(pages.PageMaker, routes, config=uweb.read_config(config))


if __name__ == '__main__':
  application().serve()
