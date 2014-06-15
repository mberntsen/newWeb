"""A uWeb base project."""

# Standard modules
import os

# Third-party modules
import uweb

# Application
from . import pages


def main():
  """Creates a newWeb application.

  The application is created from the following components:

  - The presenter class (PageMaker) which implements the request handlers.
  - The routes iterable, where each 2-tuple defines a url-pattern and a the
    name of a presenter method which should handle it.
  - The configuration file (ini format) from which settings should be read.
  """
  config = os.path.join(os.path.dirname(__file__), 'config.ini')
  routes = [
      ('/', 'Index'),
      ('/(.*)', 'FourOhFour')]
  return uweb.NewWeb(pages.PageMaker, routes, config=uweb.read_config(config))
