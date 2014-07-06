#!/usr/bin/python
"""Request handlers for the newWeb project scaffold"""

import newweb

class PageMaker(newweb.DebuggingPageMaker):
  """Holds all the request handlers for the application"""

  def Index(self):
    """Returns the index template"""
    return self.parser.Parse('index.utp')

  def FourOhFour(self, path):
    """The request could not be fulfilled, this returns a 404."""
    self.req.response.httpcode = 404
    return self.parser.Parse('404.utp', path=path)
