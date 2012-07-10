#!/usr/bin/python
"""Html generators for the base uweb server"""

__author__ = 'Jan Kopper <jan@underdark.nl>'
__version__ = '0.1'

# Custom modules
import uweb

class PageMaker(uweb.DebuggingPageMaker):
  """Holds all the html generators for the webapp

  Each page as a separate method.
  """

  def Index(self):
    """Returns the index.html template"""
    return self.parser.Parse('index.utp')

  def FourOhFour(self, path):
    """The request could not be fulfilled, this returns a 404."""
    return uweb.Response(self.parser.Parse('404.utp', path=path),
                         httpcode=404)
