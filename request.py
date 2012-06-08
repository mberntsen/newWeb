#!/usr/bin/python2.6
"""Underdark micro-Web framework, uWeb, Request module."""

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.8'

# Standard modules
import cgi
import cStringIO
import Cookie as cookie
import os
import re
import socket
import urllib


class Cookie(cookie.SimpleCookie):
  """Cookie class that uses the most specific value for a cookie name.

  According to RFC2965 (http://tools.ietf.org/html/rfc2965):
      If multiple cookies satisfy the criteria above, they are ordered in
      the Cookie header such that those with more specific Path attributes
      precede those with less specific.  Ordering with respect to other
      attributes (e.g., Domain) is unspecified.

  This class adds this behaviour to cookie parsing. That is, a key:value pair
  WILL NOT overwrite an already existing (and thus more specific) pair.

  N.B.: this class assumes the given cookie to follow the standards outlined in
  the RFC. At the moment (2011Q1) this assumption proves to be correct for both
  Chromium (and likely Webkit in general) and Firefox. Other browsers have not
  been testsed, and might possibly deviate from the suggested standard.
  As such, it's recommended not to re-use the cookie name with different values
  for different paths.
  """
  # Unfortunately this works by redefining a private method.
  def _BaseCookie__set(self, key, real_value, coded_value):
    """Inserts a morsel into the Cookie, strictly on the first occurrance."""
    if key not in self:
      morsel = cookie.Morsel()
      morsel.set(key, real_value, coded_value)
      dict.__setitem__(self, key, morsel)


class Request(object):
  def __init__(self, request):
    self._request = request
    if hasattr(request, 'path'):
      self._modpython = False
      self.env = EnvironBaseHttp(request)
      self.headers = request.headers
      self._out_headers = []
      self._out_status = 200
      post_data_fp = request.rfile
    else:
      self._modpython = True
      self.env = EnvironModPython(request)
      self.headers = request.headers_in
      post_data_fp = request

    try:
      self.env['PATH_INFO'] = self.env['PATH_INFO'].decode('UTF8')
    except UnicodeDecodeError:
      pass # Work with possibly borky encoding on PATH_INFO

    # `self.vars` setup, will contain keys 'cookie', 'get' and 'post'
    self.vars = {'cookie': dict((name, value.value) for name, value in
                                Cookie(self.env.get('HTTP_COOKIE')).items()),
                 'get': QueryArgsDict(cgi.parse_qs(self.env['QUERY_STRING']))}
    if self.env['REQUEST_METHOD'] == 'POST':
      self.vars['post'] = ParseForm(post_data_fp, self.env)
    else:
      self.vars['post'] = IndexedFieldStorage()

  def AddCookie(self, key, value, **attrs):
    """Adds a new cookie header to the repsonse.

    Arguments:
      @ key: str
        The name of the cookie.
      @ value: str
        The actual value to store in the cookie.
      % expires: str ~~ None
        The date + time when the cookie should expire. The format should be:
        "Wdy, DD-Mon-YYYY HH:MM:SS GMT" and the time specified in UTC.
        The default means the cookie never expires.
        N.B. Specifying both this and `max_age` leads to undefined behavior.
      % path: str ~~ '/'
        The path for which this cookie is valid. This default ('/') is different
        from the rule stated on Wikipedia: "If not specified, they default to
        the domain and path of the object that was requested".
      % domain: str ~~ None
        The domain for which the cookie is valid. The default is that of the
        requested domain.
      % max_age: int
        The number of seconds this cookie should be used for. After this period,
        the cookie should be deleted by the client.
        N.B. Specifying both this and `expires` leads to undefined behavior.
      % secure: boolean
        When True, the cookie is only used on https connections.
      % httponly: boolean
        When True, the cookie is only used for http(s) requests, and is not
        accessible through Javascript (DOM).
    """
    new_cookie = Cookie({key.encode('ascii'): value})
    if 'max_age' in attrs:
      attrs['max-age'] = attrs.pop('max_age')
    new_cookie[key].update(attrs)
    self.AddHeader('Set-Cookie', new_cookie[key].OutputString())

  def AddHeader(self, name, value):
    if self._modpython:
      self._request.headers_out.add(name, value)
    else:
      self._out_headers.append((name, value))

  def ExtendedEnvironment(self):
    if self._modpython:
      return ExtendEnvironModPython(self.env, self._request)
    else:
      return ExtendEnvironBaseHttp(self.env, self._request)

  def SetContentType(self, content_type):
    """Sets outgoing header 'content-type' to the given value."""
    if self._modpython:
      self._request.content_type = '%s; charset=utf-8' % content_type
    else:
      self.AddHeader('content-type', '%s; charset=utf-8' % content_type)

  def SetHttpCode(self, http_status_code):
    if self._modpython:
      self._request.status = http_status_code
    else:
      self._out_status = http_status_code

  def Write(self, data):
    """Writes the HTTP reply to the requesting party.

    N.B. For the BaseHTTP variant, this is where status and headers are written.
    """
    if self._modpython:
      if self.env['REQUEST_METHOD'] != 'HEAD':
        self._request.write(data)
    else:
      self._request.send_response(self._out_status)
      for name, value in self._out_headers:
        self._request.send_header(name, value)
      self._request.end_headers()
      if self.env['REQUEST_METHOD'] != 'HEAD':
        self._request.wfile.write(data)


class IndexedFieldStorage(cgi.FieldStorage):
  """Adaption of cgi.FieldStorage with a few specific changes.

  Notable differences with cgi.FieldStorage:
    1) `environ.QUERY_STRING` does not add to the returned FieldStorage
       This way we maintain a strict separation between POST and GET variables.
    2) Field names in the form 'foo[bar]=baz' will generate a dictionary:
         foo = {'bar': 'baz'}
       Multiple statements of the form 'foo[%s]' will expand this dictionary.
       Multiple occurrances of 'foo[bar]' will result in unspecified behavior.
    3) Automatically attempts to parse all input as UTF8. This is the proposed
       standard as of 2005: http://tools.ietf.org/html/rfc3986.
  """
  FIELD_AS_ARRAY = re.compile(r'(.*)\[(.*)\]')
  def iteritems(self):
    return ((key, self.getlist(key)) for key in self)

  def items(self):
    return list(self.iteritems())

  def read_urlencoded(self):
    indexed = {}
    self.list = []
    for field, value in cgi.parse_qsl(self.fp.read(self.length),
                                      self.keep_blank_values,
                                      self.strict_parsing):
      if self.FIELD_AS_ARRAY.match(field):
        field_group, field_key = self.FIELD_AS_ARRAY.match(field).groups()
        indexed.setdefault(field_group, cgi.MiniFieldStorage(field_group, {}))
        indexed[field_group].value[field_key] = value.decode('utf8')
      else:
        self.list.append(cgi.MiniFieldStorage(field, value.decode('utf8')))
    self.list = indexed.values() + self.list
    self.skip_lines()


class QueryArgsDict(dict):
  def getfirst(self, key, default=None):
    """Returns the first value for the requested key, or a fallback value."""
    try:
      return self[key][0]
    except KeyError:
      return default

  def getlist(self, key):
    """Returns a list with all values that were given for the requested key.

    N.B. If the given key does not exist, an empty list is returned.
    """
    try:
      return self[key]
    except KeyError:
      return []


def EnvironBaseHttp(request):
  path_info, _sep, query_string = request.path.partition('?')
  environ = {'CONTENT_TYPE': request.headers.get('content-type', ''),
             'CONTENT_LENGTH': request.headers.get('content-length', 0),
             'HTTP_COOKIE': request.headers.get('cookie', ''),
             'HTTP_HOST': request.headers.get('host', ''),
             'HTTP_REFERER': request.headers.get('referer', ''),
             'HTTP_USER_AGENT': request.headers.get('user-agent', ''),
             'PATH_INFO': urllib.unquote_plus(path_info),
             'QUERY_STRING': query_string,
             'REMOTE_ADDR': request.client_address[0],
             'REQUEST_METHOD': request.command,
             'UWEB_MODE': 'STANDALONE'}
  return HeadersIntoEnviron(environ, request.headers)


def EnvironModPython(request):
  environ = {'CONTENT_TYPE': request.headers_in.get('content-type', ''),
             'CONTENT_LENGTH': request.headers_in.get('content-length', 0),
             'HTTP_COOKIE': request.headers_in.get('cookie', ''),
             'HTTP_HOST': request.hostname,
             'HTTP_REFERER': request.headers_in.get('referer', ''),
             'HTTP_USER_AGENT': request.headers_in.get('user-agent', ''),
             'PATH_INFO': urllib.unquote_plus(request.uri),
             'QUERY_STRING': request.args or '',
             'REMOTE_ADDR': request.connection.remote_ip,
             'REQUEST_METHOD': request.method,
             'UWEB_MODE': 'MOD_PYTHON'}
  return HeadersIntoEnviron(environ, request.headers_in)


def ExtendEnvironBaseHttp(environ, request):
  environ.update(
      {'AUTH_TYPE': None,
       'CONNECTION_ID': None,
       'DOCUMENT_ROOT': os.getcwd(),
       'RAW_REQUEST': request.raw_requestline,
       'REMOTE_HOST': socket.getfqdn(environ['REMOTE_ADDR']),
       'REMOTE_USER': None,
       'SERVER_NAME': request.server.server_name,
       'SERVER_PORT': request.server.server_port,
       'SERVER_LOCAL_NAME': socket.gethostname(),
       'SERVER_LOCAL_IP': GetLocalIp(environ['REMOTE_ADDR']),
       'SERVER_PROTOCOL': request.request_version})
  return environ


def ExtendEnvironModPython(environ, request):
  environ.update(
      {'AUTH_TYPE': request.ap_auth_type,
       'CONNECTION_ID': request.connection.id,
       'DOCUMENT_ROOT': request.document_root(),
       'RAW_REQUEST': request.the_request,
       'REMOTE_HOST': socket.getfqdn(environ['REMOTE_ADDR']),
       'REMOTE_USER': request.user,
       'SERVER_NAME': request.server.server_hostname,
       'SERVER_PORT': request.connection.local_addr[1],
       'SERVER_LOCAL_NAME': socket.gethostname(),
       'SERVER_LOCAL_IP': request.connection.local_ip,
       'SERVER_PROTOCOL': request.protocol,
       # Some specific mod_python love
       'MODPYTHON_HANDLER': request.handler,
       'MODPYTHON_INTERPRETER': request.interpreter,
       'MODPYTHON_PHASE': request.phase})
  return environ


def GetLocalIp(remote_addr):
  """Returns the local IP address of the server.

  BaseHTTP itself only knows the IP address it's bound to. This is likely to be
  a bogus address, such as '0.0.0.0'. Unfortunately, with BaseHTTP, it's
  impossible to know which internal address rreceived the incoming request.

  What is done to make a best guess:
  - A UDP socket to the `remote_addr` is set up. Opening a UDP socket does not
    initiate a handshake, transfers no data, and is super-fast.
  - The name of the socket is retrieved, which is the local address and port.

  Arguments:
    @ remote_addr: str
      The content of the REMOTE_ADDR as present in the requests' environment.

  Returns:
    str: the local IP address, dot separated.
  """
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  # The port is irrelevant as we're not going to transfer any data.
  sock.connect((remote_addr, 80))
  return sock.getsockname()[0]


def HeadersIntoEnviron(environ, headers, skip_pre_existing_http=True):
  """Adds the headers into the environment.

  If a header is already present, it's skipped, otherwise it's added with a
  leading 'HTTP_'.

  Arguments:
    @ environ: dict
      Dictionary of environment variables as (roughly) defined in CGI spec.
    @ headers: dict-like
      Dictionary of HTTP-response headers. Any object with a tuple-iterator
      on .items() method will do.
    % skip_pre_existing_http: boolean ~~ True
      A list of pre-existing 'HTTP_*' environment vars is made, and any headers
      that match, will *not* be added to the environment again.

  Returns
   dict: the environ as passed in, with added HTTP environment variables.
  """
  pre_existing_http = ()
  if skip_pre_existing_http:
    pre_existing_http = set(var[5:] for var in environ if var[:5] == 'HTTP_')
  for name, value in headers.items():
    name = name.replace('-', '_').upper()
    if name in environ or name in pre_existing_http:
      continue  # Skip headers we already have in environ
    if 'HTTP_' + name in environ:
      # Comma-separate headers that occur more than once
      environ['HTTP_' + name] += ',' + value
    else:
      environ['HTTP_' + name] = value
  return environ


def ParseForm(file_handle, environ):
  """Returns an IndexedFieldStorage object from the POST data and environment.

  This small wrapper is necessary because cgi.FieldStorage assumes that the
  provided file handles supports .readline() iteration. File handles as provided
  by BaseHTTPServer do not support this, so we need to convert them to proper
  cStringIO objects first.
  """
  data = cStringIO.StringIO(file_handle.read(int(environ['CONTENT_LENGTH'])))
  return IndexedFieldStorage(fp=data, environ=environ)
