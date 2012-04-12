#!/usr/bin/python
"""Underdark uWeb PageMaker Mixins for login/authentication purposes.

Contains both the Underdark Login Framework and OpenID implementations
"""
from __future__ import with_statement

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.5'

# Standard modules
import binascii
import hashlib
import os
import simplejson

# Package modules
import uweb
from uweb import model
from uweb import uwebopenid

OPENID_PROVIDERS = {'google': 'https://www.google.com/accounts/o8/id',
                    'yahoo': 'http://yahoo.com/',
                    'myopenid': 'http://myopenid.com/'}


# ##############################################################################
# Record classes for Underdark Login Framework
#
# Model classes have many methods, this is acceptable
# pylint: disable=R0904
class Challenge(model.Record):
  """Abstraction for the `challenge` table."""
  _PRIMARY_KEY = 'user', 'remote'
  CHALLENGE_BYTES = 16

  @classmethod
  def ChallengeBytes(cls):
    """Returns the configured number of random bytes for a challenge."""
    return os.urandom(cls.CHALLENGE_BYTES)

  @classmethod
  def MakeChallenge(cls, connection, remote, user):
    """Makes a new, or retrieves an existing challenge for a given IP + user."""
    record = {'remote': remote, 'user': user, 'challenge': cls.ChallengeBytes()}
    try:
      return super(Challenge, cls).Create(connection, record)
    except connection.IntegrityError:
      return cls.FromPrimary(connection, (user, remote))


class User(model.Record):
  """Abstraction for the `user` table."""
  SALT_BYTES = 8

  @classmethod
  def FromName(cls, connection, username):
    """Returns a User object based on the given username."""
    with connection as cursor:
      safe_name = connection.EscapeValues(username)
      user = cursor.Select(
          table=cls.TableName(),
          conditions='name=%s' % safe_name)
    if not user:
      raise cls.NotExistError('No user with name %r' % username)
    return cls(connection, user[0])

  @classmethod
  def SaltBytes(cls):
    """Returns the configured number of random bytes for the salt."""
    return os.urandom(cls.SALT_BYTES)
# pylint: enable=R0904


# ##############################################################################
# Actual Pagemaker mixin class
#
class LoginMixin(object):
  """Provides the Underdark Login Framework for uWeb."""
  ULF_CHALLENGE = Challenge
  ULF_USER = User

  def _ULF_Challenge(self):
    """Answers the AJAJ request from the client, providing salt and challenge.

    The salt is user-dependent and will be gotten from the user model. If no
    user is known for the given name, we fudge the response and give a random
    salt. This is to prevent the client from gaining knowledge as to which
    users exist.

    Salt and challenge lengths are configurable, and indicate the number of
    bytes. These will be sent to the client in hexadecimal format.
    """
    try:
      user = self.ULF_USER.FromName(
          self.connection, self.post.getfirst('username'))
      salt = user['salt']
      challenge = self.ULF_CHALLENGE.MakeChallenge(
          self.connection, self.req.env['REMOTE_ADDR'], user.key)['challenge']
    except model.NotExistError:
      # There is no user by that name. We do not want the client to know this,
      # so we create a random salt for the client and let him proceed with that.
      salt = self.ULF_USER.SaltBytes()
      challenge = self.ULF_CHALLENGE.ChallengeBytes()
    content = {'salt': binascii.hexlify(salt),
               'challenge': binascii.hexlify(challenge)}
    return uweb.Response(content_type='application/json',
                         content=simplejson.dumps(content))

  def _ULF_Verify(self):
    """Verifies the authentication request and dispatches to result renderers.

    Authentication mode is decided on the presence of the 'salted' key in the
    POST request. If this is present, we will use the salt + challenge
    verification mode. The result of HASH(HASH(password + salt) + challenge)
    should be in the 'salted' form field.

    In the other (plaintext) case, the password will be expected in the
    'password' field. This is not yet available for easy adjustment.

    If either of the verification methods raise a model.NotExistError, the
    authentication is automatically considered as failed, and the _ULF_Failure
    method will be called and returned.
    """
    try:
      if 'salted' in self.post:
        return self._ULF_VerifyChallenge()
      return self._ULF_VerifyPlain()
    except model.NotExistError:
      return self._ULF_Failure()

  def _ULF_VerifyPlain(self):
    """Verifies the given password (after hashing) matches the salted password.

    If they match, self._ULF_Success is called and returned. If they do not
    match self.ULF_Failure is called and returned instead.
    """
    user = self.ULF_USER.FromName(self.connection, self.post.getfirst('username'))
    plaintext = str(self.post.getfirst('password', ''))
    if user['password'] == hashlib.sha1(plaintext + user['salt']).digest():
      return self._ULF_Success(False)
    return self._ULF_Failure(False)

  def _ULF_VerifyChallenge(self):
    """Verifies the result of a password + salt + challenge.

    This is the secure mode of operation. The input should be the result of
    HASH(HASH(password + salt) + challenge), and present on the form field
    'salted'. From the local side, the stored challenge and salted password are
    hashed and compared with the provided value.

    If they match, self._ULF_Success is called and returned. If they do not
    match self.ULF_Failure is called and returned instead.
    """
    user = self.ULF_USER.FromName(
        self.connection, self.post.getfirst('username'))
    challenge = self.ULF_CHALLENGE.FromPrimary(
        self.connection, (user, self.req.env['REMOTE_ADDR']))
    password = binascii.hexlify(user['password'])
    chall_str = binascii.hexlify(challenge['challenge'])
    challenge.Delete()  # Delete the challenge so we do not re-use it.
    password = hashlib.sha1(password + chall_str).hexdigest()
    if password == self.post.getfirst('salted', ''):
      return self._ULF_Success(True)
    return self._ULF_Failure(True)

  def _ULF_Failure(self, secure):
    """Renders the response to the user upon authentication failure."""
    raise NotImplementedError

  def _ULF_Success(self, secure):
    """Renders the response to the user upon authentication success."""
    raise NotImplementedError


class OpenIdMixin(object):
  """A class that provides rudimentary OpenID authentication.

  At present, it does not support any means of Attribute Exchange (AX) or other
  account information requests (sReg). However, it does provide the base
  necessities for verifying that whoever logs in is still the same person as the
  one that was previously registered.
  """
  def _OpenIdInitiate(self, provider=None):
    """Verifies the supplied OpenID URL and resolves a login through it."""
    if provider:
      try:
        openid_url = OPENID_PROVIDERS[provider.lower()]
      except KeyError:
        return self.OpenIdProviderError('Invalid OpenID provider %r' % provider)
    else:
      openid_url = self.post.getfirst('openid_provider')

    consumer = uwebopenid.OpenId(self.req)
    # set the realm that we want to ask to user to verify to
    trustroot = 'http://%s' % self.req.env['HTTP_HOST']
    # set the return url that handles the validation
    returnurl = trustroot + '/OpenIDValidate'

    try:
      return consumer.Verify(openid_url, trustroot, returnurl)
    except uwebopenid.InvalidOpenIdUrl, error:
      return self.OpenIdProviderBadLink(error)
    except uwebopenid.InvalidOpenIdService, error:
      return self.OpenIdProviderError(error)

  def _OpenIdValidate(self):
    """Handles the return url that openId uses to send the user to"""
    try:
      auth_dict = uwebopenid.OpenId(self.req).doProcess()
    except uwebopenid.VerificationFailed, error:
      return self.OpenIdAuthFailure(error)
    except uwebopenid.VerificationCanceled, error:
      return self.OpenIdAuthCancel(error)
    return self.OpenIdAuthSuccess(auth_dict)

  def OpenIdProviderBadLink(self, err_obj):
    """Handles the case where the OpenID provider link is faulty."""
    raise NotImplementedError

  def OpenIdProviderError(self, err_obj):
    """Handles the case where the OpenID provider responds out of spec."""
    raise NotImplementedError

  def OpenIdAuthCancel(self, err_obj):
    """Handles the case where the client cancels OpenID authentication."""
    raise NotImplementedError

  def OpenIdAuthFailure(self, err_obj):
    """Handles the case where the provided authentication is invalid."""
    raise NotImplementedError

  def OpenIdAuthSuccess(self, auth_dict):
    """Handles the case where the OpenID authentication was successful.

    Implementers should at the very least override this method as this is where
    you will want to mark people as authenticated, either by cookies or sessions
    tracked otherwise.
    """
    raise NotImplementedError
