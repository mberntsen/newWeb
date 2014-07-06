"""A minimal newWeb project scaffold."""

# Standard modules
import os

# Third-party modules
import newweb

# Application
from . import pages


def main():
  """Creates a newWeb application.

  The application is created from the following components:

  - The presenter class (PageMaker) which implements the request handlers.
  - The routes iterable, where each 2-tuple defines a url-pattern and the
    name of a presenter method which should handle it.
  - The configuration file (ini format) from which settings should be read.
  """
  config_file = os.path.join(os.path.dirname(__file__), 'config.ini')
  config = newweb.read_config(config_file)
  routes = [
      ('/', 'Index'),
      ('/(.*)', 'FourOhFour')]
  return newweb.NewWeb(pages.PageMaker, routes, config=config)
