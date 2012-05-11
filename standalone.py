#!/usr/bin/python
"""uweb standalone webserver"""
__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.3'

# Standard modules
import BaseHTTPServer
import errno
import sys

# Custom modules
from underdark.libs.app import logging


class ServerRunningError(Exception):
  """Another process is already using this port."""


class StandAloneServer(BaseHTTPServer.HTTPServer):
  CONFIG_SECTION = 'standalone'
  DEFAULT_HOST = '0.0.0.0'
  DEFAULT_PORT = 8082

  def __init__(self, router, router_name, config):
    self.access_logging = self._ConfigVariable(
        'access_logging', config, router_name, default=True)
    self.error_logging = self._ConfigVariable(
        'error_logging', config, router_name, default=True)
    try:
      host = self._ConfigVariable(
          'host', config, router_name, default=self.DEFAULT_HOST)
      port = self._ConfigVariable(
          'port', config, router_name, default=self.DEFAULT_PORT)
      BaseHTTPServer.HTTPServer.__init__(self, (host, port), StandAloneHandler)
      self.router = router
    except BaseHTTPServer.socket.error:
      raise ServerRunningError(
          'Could not bind to %r:%d. Socket already in use?' % (host, port))
    except ValueError:
      raise ValueError('The configured port %r is not a valid number' % port)
    print 'Running uWeb on %s:%d' % self.server_address

  def _ConfigVariable(self, key, config, name, default=None):
    router_specific_config = '%s:%s' % (self.CONFIG_SECTION, name)
    router_config = config.get(router_specific_config, {})
    if key in router_config:
      value = router_config[key]
    else:
      router_config = config.get(self.CONFIG_SECTION, {})
      value = router_config.get(key, default)
    if isinstance(value, basestring):
      if value.lower() in ('true', 'false'):
        return value.lower() == 'true'
      elif value.isdigit():
        return int(value)
    return value

  def handle_error(self, _request, client_address):
    error = sys.exc_info()[1]
    # Ignore known errors that happen if the client closes the socket.
    if error.args[0] not in (
        errno.EPIPE,         # Unix: Broken pipe.
        errno.ECONNABORTED,  # Unix: Connection aborted.
        errno.ECONNRESET,    # Unix: Connection reset by peer.
        10053,               # Winsock: Connection aborted. (WSAECONNABORTED)
        10054):              # Winsock: Connection reset. (WSAECONNRESET)
      message = 'Exception happened during processing of request from %s:%s.\n'
      sys.stderr.write(message % client_address)
      logging.LogException(message, *client_address)


class StandAloneHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  server_version = 'uWeb StandAlone/%s' % __version__
  sys_version = ''

  def handle_one_request(self):
    self.raw_requestline = self.rfile.readline()
    if not self.raw_requestline:
      self.close_connection = 1
      return
    if not self.parse_request():
      # An error code has been sent, just exit
      return
    self.server.router(self)

  #TODO(Elmer): Move logging to the Request object.
  def log_error(self, logmsg, *args):
    """Logs an error both to logging module (as ERROR) and to sys.stderr."""
    if self.server.error_logging:
      logline = logmsg % args
      logging.LogError('Origin [%s] - - %s', self.address_string(), logline)
      sys.stderr.write('%s [%s] - - %s\n' % (
          self.log_date_time_string(), self.client_address[0], logline))

  def log_message(self, logmsg, *args):
    """Logs messages both to logging module (as DEBUG) and to sys.stdout."""
    if self.server.access_logging:
      logline = logmsg % args
      logging.LogDebug('Origin [%s] - - %s', self.address_string(), logline)
      sys.stdout.write('%s [%s] - - %s\n' % (
          self.log_date_time_string(), self.client_address[0], logline))
