#!/usr/bin/python
"""uweb standalone webserver"""
__author__ = 'Jan Klopper <jan@underdark.nl>'
__version__ = '0.1'

# Standard modules
import BaseHTTPServer
import errno
import sys

# Custom modules
from underdark.libs import logging
import apache_mock as apache


class ServerRunningError(Exception):
  """Another process is already using this port."""


class StandaloneServer(object):
  def __init__(self, handler, server=None):
    server = server or {}
    host = server.get('host', '0.0.0.0')
    port = int(server.get('port', '8082'))
    try:
      self.httpd = BaseHTTPServer.HTTPServer((host, port), StandaloneHandler)
      self.httpd.handler = handler
    except BaseHTTPServer.socket.error:
      raise ServerRunningError(
          'A server is already running on host %r, port %r' % (host, port))

  def Start(self):
    self.httpd.serve_forever()


class StandaloneHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  server_version = 'uweb Standalone/%s' % __version__
  sys_version = ''

  def handle_one_request(self):
    try:
      self.raw_requestline = self.rfile.readline()
      if not self.raw_requestline:
        self.close_connection = 1
        return
      if not self.parse_request(): # An error code has been sent, just exit
        return
    except (IOError, BaseHTTPServer.socket.error), error:
      logging.LogException('From what I understand, this should never raise().')
      if error.args[0] in (
          errno.EPIPE,         # Unix: Broken pipe.
          errno.ECONNABORTED,  # Unix: Connection aborted.
          errno.ECONNRESET,    # Unix: Connection reset by peer.
          10053,               # Winsock: Connection aborted. (WSAECONNABORTED)
          10054):              # Winsock: Connection reset. (WSAECONNRESET)
        self.close_connection = 1
      else:
        logging.LogCritical('This is REALLY unexpected, beyond the previous.')

    try:
      self.server.handler(self)
    except apache.SERVER_RETURN:
      pass

  #TODO(Elmer): Move logging to the Request object.
  def log_error(self, logmsg, *args):
    """Logs an error both to logging module (as ERROR) and to sys.stderr."""
    logging.LogError('Origin [%s] - - %s', self.address_string(), logmsg % args)
    sys.stderr.write('%s [%s] - - %s\n' % (
        self.log_date_time_string(), self.client_address[0], logmsg % args))

  def log_message(self, logmsg, *args):
    """Logs messages both to logging module (as DEBUG) and to sys.stdout."""
    logging.LogDebug('Origin [%s] - - %s', self.address_string(), logmsg % args)
    sys.stdout.write('%s [%s] - - %s\n' % (
        self.log_date_time_string(), self.client_address[0], logmsg % args))


def RunStandAlone(handler, **config):
  server = StandaloneServer(handler, server=config.get('server'))
  print 'running locally on %s:%d' % server.httpd.server_address
  try:
    server.Start()
  except KeyboardInterrupt:
    print 'shutting down'
