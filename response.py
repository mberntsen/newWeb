#!/usr/bin/python
"""Underdark uWeb Response object."""
from __future__ import with_statement

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.1'


class Response(object):
  """Defines a full HTTP response.

  The full response consists of a required content part, and then optional
  http response code, cookies, additional headers, and a content-type.
  """
  # Default content-type for Page objects
  CONTENT_TYPE = 'text/html'

  def __init__(self, content='', content_type=CONTENT_TYPE,
               cookies=(), headers=None,  httpcode=200):
    """Initializes a Page object.

    Arguments:
      @ content: str
        The content to return to the client. This can be either plain text, html
        or the contents of a file (images for example).
      % content_type: str ~~ CONTENT_TYPE ('text/html' by default)
        The content type of the response. This should NOT be set in headers.
      % cookies: dict ~~ None
        Cookies are expected to be dictionaries, made up of the following keys:
        * Keys they MUST contain: `key`, `value`
        * Keys they MAY contain:  `expires`, `path`, `comment`, `domain`,
                                  `max-age`, `secure`, `version`, `httponly`
      % headers: dictionary ~~ None
        A dictionary mappging the header name to its value.
      % httpcode: int ~~ 200
        The HTTP response code to attach to the response.
    """
    if isinstance(content, unicode):
      self.content = content.encode('utf8')
    else:
      self.content = str(content)
    self.cookies = cookies
    self.httpcode = httpcode
    self.headers = headers or {}
    self.content_type = content_type

  def __repr__(self):
    return '<%s instance at %#x>' % (self.__class__.__name__, id(self))

  def __str__(self):
    return self.content
