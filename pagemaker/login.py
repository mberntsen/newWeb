#!/usr/bin/python
"""Underdark uWeb PageMaker Mixins for login/authentication purposes."""
from __future__ import with_statement

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.3'

# Custom modules
from underdark.libs.uweb import uwebopenid

OPENID_PROVIDERS = {'google': 'https://www.google.com/accounts/o8/id',
                    'yahoo': 'http://yahoo.com/',
                    'myopenid': 'http://myopenid.com/'}


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

  # The following methods are suggeted by pylint to be made static or functions.
  # We do not want this because they belong on the (mixin) class, and when
  # implemented, they are expected to make use of `self`, at the least for
  # template parsing uses.
  # pylint: disable=R0201
  def OpenIdProviderBadLink(self, err_obj):
    """Handles the case where the OpenID provider link is faulty."""
    message = 'Bad OpenID Provider URL: %r' % err_obj
    return message + ImplementYourself()

  def OpenIdProviderError(self, err_obj):
    """Handles the case where the OpenID provider responds out of spec."""
    message = 'The OpenID provider did not respond as expected: %r' % err_obj
    return message + ImplementYourself()

  def OpenIdAuthCancel(self, err_obj):
    """Handles the case where the client cancels OpenID authentication."""
    message = 'OpenID Authentication canceled by user: %s' % err_obj
    return message + ImplementYourself()

  def OpenIdAuthFailure(self, err_obj):
    """Handles the case where the provided authentication is invalid."""
    message = 'OpenID Authentication failed: %s' % err_obj
    return message + ImplementYourself()

  def OpenIdAuthSuccess(self, auth_dict):
    """Handles the case where the OpenID authentication was successful.

    Implementers should at the very least override this method as this is where
    you will want to mark people as authenticated, either by cookies or sessions
    tracked otherwise.
    """
    message = 'OpenID Authentication successful:\n\n%s' % (
        '\n'.join('* %s = %r' % pair for pair in sorted(auth_dict.items())))
    return message + ImplementYourself()
  # End of block of methods that could be static.
  # pylint: enable=R0201


def ImplementYourself():
  """Returns the calling function name with an advisory on overriding it."""
  import inspect
  meth_name = inspect.stack()[1][3]
  return '\n\nTo customize response and behavior, override %r.' % meth_name
