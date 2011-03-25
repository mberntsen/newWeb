#!/usr/bin/python
"""Underdark uWeb PageMaker Mixins for login/authentication purposes."""
from __future__ import with_statement

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.3'

# Custom modules
from underdark.libs.uweb import uwebopenid


class OpenIdMixin(object):
  def _OpenIdInitiate(self):
    """Verifies the supplied OpenID URL and resolves a login through it."""
    consumer = uwebopenid.OpenId(self.req)

    # set the realm that we want to ask to user to verify to
    trustroot = 'http://%s' % self.req.env['HTTP_HOST']
    # set the return url that handles the validation
    returnurl = trustroot + '/OpenIDValidate'
    openid_url = self.post.getfirst('openid_provider')
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
    message = 'Bad OpenID Provider URL: %r' % err_obj
    return message + ImplementYourself()

  def OpenIdProviderError(self, err_obj):
    message = 'The OpenID provider did not respond as expected: %r' % err_obj
    return message + ImplementYourself()

  def OpenIdAuthCancel(self, err_obj):
    message = 'OpenID Authentication canceled by user: %s' % err_obj
    return message + ImplementYourself()

  def OpenIdAuthFailure(self, err_obj):
    message = 'OpenID Authentication failed: %s' % err_obj
    return message + ImplementYourself()

  def OpenIdAuthSuccess(self, auth_dict):
    message = 'OpenID Authentication successful:\n\n%s' % (
        '\n'.join('* %s = %r' % pair for pair in sorted(auth_dict.items())))
    return message + ImplementYourself()


def ImplementYourself():
  import inspect
  meth_name = inspect.stack()[1][3]
  return '\n\nTo customize response and behavior, override %r.' % meth_name
