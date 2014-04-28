#!/usr/bin/python
"""Underdark uWeb PageMaker Mixins for session management purposes."""

__author__ = 'Niek Bergman <niek@underdark.nl>'
__version__ = '0.1'

# Standard modules
import binascii
import os
import datetime
import pytz

# Package modules
from uweb import model

# ##############################################################################
# Record classes for session management
#
# Model class have many methods.
# pylint:disable=R0904

class Session(model.Record):
  """Abstraction for the `session` table"""

  _PRIMARY_KEY = 'session'
# pylint:enable=R0904

# ##############################################################################
# Pagemaker Mixin class for session management
#
class SessionMixin(object):
  """Provides session management for the uWeb Framework"""

  class NoSessionError(Exception):
    """Custom exception for user not having a (unexpired) session cookie."""

  class SecurityError(Exception):
    """Custom exception raised for not passing security constraints set on the
    session."""

  class XsrfError(Exception):
    """Custom exception raised in case of a detected XSRF attack."""

  SESSION_TABLE = Session

  def _ULF_DeleteSession(self, cookie_name):
    """Destroys a user session with `cookie_name`. Used for logging out."""
    try:
      sessionid = self.cookies[cookie_name]
    except KeyError:
      raise self.NoSessionError(
          'User does not have a session cookie with name %s' % cookie_name)
    try:
      binsessid = binascii.unhexlify(sessionid)
      self.SESSION_TABLE.DeletePrimary(self.connection, binsessid)
      # Set a junk cookie that expires in 1 second.
      self.req.AddCookie(cookie_name, 'deleted', path='/', max_age=1,
                         httponly=True)
    except model.NotExistError:
      raise self.NoSessionError(
          'There is no session associated with ID %s' % sessionid)

  def _ULF_CheckXsrf(self, cookie_name, field_name="xsrf"):
    """Checks if the cookie named `cookie_name` matches the field `field_name`

    Used to check if an XSRF is happening. Returns `True` if an XSRF is
    detected.
    """
    try:
      sessionid = self.cookies[cookie_name]
    except KeyError:
      raise self.NoSessionError(
          'User does not have a session cookie with name %s' % cookie_name)
    if self.req.env['REQUEST_METHOD'] == "POST":
      if sessionid != self.post.getfirst(field_name):
        raise self.XsrfError("An XSRF attack was detected for this request.")
    else:
      if sessionid != self.get.getfirst(field_name):
        raise self.XsrfError("An XSRF attack was detected for this request.")

  def _ULF_GetSessionId(self, cookie_name):
    try:
      sessionid = self.cookies[cookie_name]
    except KeyError:
      raise self.NoSessionError(
          'User does not have a session cookie with name %s' % cookie_name)
    return sessionid

  def _ULF_GetSession(self, cookie_name):
    """Fetches a user ID associated with a session ID set on `cookie_name`."""
    remote = self.req.env['REMOTE_ADDR'] # Get remote IP of user.
    try:
      sessionid = self.cookies[cookie_name]
    except KeyError:
      raise self.NoSessionError(
          'User does not have a session cookie with name %s' % cookie_name)
    try:
      binsessid = binascii.unhexlify(sessionid)
      session = Session.FromPrimary(self.connection, binsessid)
      remote = self.req.env['REMOTE_ADDR']
      if (session['expiry'] < datetime.datetime.now(pytz.UTC)):
        raise self.NoSessionError('The user session has expired.')
      if (session['iplocked'] and remote != session['remote']):
        raise self.SecurityError('This session is locked to another IP.')
      user = session['user']
    except model.NotExistError:
      raise self.NoSessionError(
          'There is no session associated with ID %s' % sessionid)
    return user

  def _ULF_SetSession(self, cookie_name, uid, expiry=86400, locktoip=True):
    """Sets a user ID to `uid` on cookie `cookie_name`, gives a new cookie to
    the user with this cookie name.

    Takes an optional `expiry` argument which defaults to 86400 seconds.
    Also takes an optional `locktoip` argument which defaults to True --
    which causes the session to be locked to the user's IP"""
    random_id = os.urandom(16)
    # The random ID needs to be converted to hex for the cookie.
    self.req.AddCookie(cookie_name, binascii.hexlify(random_id), path='/',
                       max_age=expiry, httponly=True)
    now = datetime.datetime.utcnow()
    expirationdate = now + datetime.timedelta(seconds=expiry)
    self.SESSION_TABLE.Create(self.connection, {
        'session': random_id, 'user': uid,
        'remote': self.req.env['REMOTE_ADDR'], 'expiry': expirationdate,
        'iplocked': int(locktoip)})
