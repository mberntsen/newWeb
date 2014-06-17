#!/usr/bin/python
"""Underdark uWeb Response object."""

# Standard modules
import httplib


class Response(object):
  """Defines a full HTTP response.

  The full response consists of a required content part, and then optional
  http response code, cookies, additional headers, and a content-type.
  """
  # Default content-type for Page objects
  CONTENT_TYPE = 'text/html'

  def __init__(self, content='', content_type=CONTENT_TYPE,
               httpcode=200, headers=None):
    """Initializes a Page object.

    Arguments:
      @ content: str
        The content to return to the client. This can be either plain text, html
        or the contents of a file (images for example).
      % content_type: str ~~ CONTENT_TYPE ('text/html' by default)
        The content type of the response. This should NOT be set in headers.
      % httpcode: int ~~ 200
        The HTTP response code to attach to the response.
      % headers: dict ~~ None
        A dictionary with header names and their associated values.
    """
    if isinstance(content, unicode):
      self.content = content.encode('utf8')
    else:
      self.content = content
    self.httpcode = httpcode
    self._headers = headers or {}
    self.content_type = content_type

  def headers_iter(self):
    yield 'content-type', self.content_type
    for name, value in self._headers.iteritems():
      yield name, value.encode('ascii')

  @property
  def headers(self):
    return list(self.headers_iter())

  @property
  def status(self):
    return '%d %s' % (self.httpcode, httplib.responses[self.httpcode])

  def __repr__(self):
    return '<%s instance at %#x>' % (self.__class__.__name__, id(self))

  def __str__(self):
    return self.content


class Redirect(Response):
  """A response tailored to do redirects."""
  REDIRECT_PAGE = ('<!DOCTYPE html><html><head><title>Page moved</title></head>'
                   '<body>Page moved, please follow <a href="%s">this link</a>'
                   '</body></html>')

  def __init__(self, location, httpcode=307):
    super(Redirect, self).__init__(
        self.REDIRECT_PAGE % location,
        content_type='text/html',
        httpcode=httpcode,
        headers={'Location': location})
