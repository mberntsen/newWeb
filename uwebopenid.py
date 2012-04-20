#!/usr/bin/python
"""module to support OpenID login in uWeb"""

__author__ = 'Jan Klopper <jan@underdark.nl>'
__version__ = '0.4'

# Standard modules
import base64
import os
from openid.consumer import consumer
from openid.extensions import pape
from openid.extensions import sreg

# Package modules
from . import response

# Constants used for OpenID provider services.
OPENID_PROVIDER_NAME = 'uweb OpenID'
OPENID_PROVIDER_URL = (
    'https://www.myopenid.com/affiliate_signup?affiliate_id=39')


class Error(Exception):
  """A uweb OpenID error has occured"""


class InvalidOpenIdUrl(Error):
  """The supplied openIDurl is invalid"""


class InvalidOpenIdService(Error):
  """The supplied openID Service is invalid"""


class VerificationFailed(Error):
  """The verification for the user failed"""


class VerificationCanceled(Error):
  """The verification for the user was canceled"""


class OpenId(object):
  """Provides OpenId verification and processing of return values"""
  def __init__(self, request, cookiename='uwebopenid'):
    """Sets up the openId class

    Arguments:
      @ request: uweb.request.Request
        The uweb request object.
      % cookiename: str ~~ 'uwebopenid'
        The name of the cookie that holds the OpenID session token.
    """
    self.request = request
    self.session = {'id': None}
    self.cookiename = cookiename

  def getConsumer(self):
    """Creates a openId consumer class and returns it"""
    #XXX(Elmer): What does having a store change?
    # As far as I can tell, this does *not* maintain sessions of any sort.
    store = None
    return consumer.Consumer(self.getSession(), store)

  def getSession(self):
    """Return the existing session or a new session"""
    if self.session['id'] is not None:
      return self.session

    # Get value of cookie header that was sent
    try:
      self.session['id'] = self.request.vars['cookies'][self.cookiename].value
    except KeyError:
      # 20 chars long, 120 bits of entropy
      self.session['id'] = base64.urlsafe_b64encode(os.urandom(15))

    return self.session

  def setSessionCookie(self):
    """Sets the session cookie on the uweb request"""
    self.request.AddCookie(self.cookiename, self.session['id'])

  def Verify(self, openid_url, trustroot, returnurl):
    """
    Takes the openIdUrl from the user and sets up the request to send the user
    to the correct page that will validate our trustroot to receive the data.

    Arguments:
      @ openid_url: str
        The supplied URL where the OpenID provider lives.
      @ trustroot: str
        The url of our webservice, will be displayed to the user as th
        consuming url
      @ returnurl: str
        The url that will handle the Process step for the user being returned
        to us by the openId supplier

    Returns either an uweb Page object redirectnig the user to the OpenId
    provider or page with some variabeles
    """
    oidconsumer = self.getConsumer()
    if openid_url.strip() == '':
      raise InvalidOpenIdService()
    try:
      request = oidconsumer.begin(openid_url)
    except consumer.DiscoveryFailure:
      raise InvalidOpenIdUrl(openid_url)
    if not request:
      raise InvalidOpenIdService()
    if request.shouldSendRedirect():
      redirect_url = request.redirectURL(trustroot, returnurl)
      return response.Redirect(redirect_url)
    else:
      return request.htmlMarkup(trustroot, returnurl,
                                form_tag_attrs={'id': 'openid_message'})

  def doProcess(self):
    """Handle the redirect from the OpenID server.

    Consumes the query part of the url by reading the get property on the uweb
    request object

    Returns:
      tuple: userId
             requested fields
             phishing resistant info
             canonical user ID

    Raises:
      VerificationCanceled if the user canceled the verification
      VerificationFailed if the verification failed
    """
    oidconsumer = self.getConsumer()

    # Ask the library to check the response that the server sent
    # us.  Status is a code indicating the response type. info is
    # either None or a string containing more information about
    # the return type.
    url = 'http://%s%s' % (
        self.request.env['HTTP_HOST'], self.request.env['PATH_INFO'])
    query_args = dict((key, value[0]) for key, value
                      in self.request.vars['get'].items())
    info = oidconsumer.complete(query_args, url)

    sreg_resp = None
    pape_resp = None
    display_identifier = info.getDisplayIdentifier()

    if info.status == consumer.FAILURE and display_identifier:
      # In the case of failure, if info is non-None, it is the
      # URL that we were verifying. We include it in the error
      # message to help the user figure out what happened.
      raise VerificationFailed('Verification of %s failed: %s' % (
          display_identifier, info.message))

    elif info.status == consumer.SUCCESS:
      # Success means that the transaction completed without
      # error. If info is None, it means that the user cancelled
      # the verification.

      # This is a successful verification attempt. If this
      # was a real application, we would do our login,
      # comment posting, etc. here.
      sreg_resp = sreg.SRegResponse.fromSuccessResponse(info)
      pape_resp = pape.Response.fromSuccessResponse(info)
      # You should authorize i-name users by their canonicalID,
      # rather than their more human-friendly identifiers.  That
      # way their account with you is not compromised if their
      # i-name registration expires and is bought by someone else.
      return {'ident': display_identifier,
              'sreg': sreg_resp,
              'pape': pape_resp,
              'canonicalID': info.endpoint.canonicalID}

    elif info.status == consumer.CANCEL:
      # cancelled
      raise VerificationCanceled('Verification canceled')

    elif info.status == consumer.SETUP_NEEDED:
      if info.setup_url:
        message = '<a href=%s>Setup needed</a>' % info.setup_url
      else:
        # This means auth didn't succeed, but you're welcome to try
        # non-immediate mode.
        message = 'Setup needed'
      raise VerificationFailed(message)
    else:
      # Either we don't understand the code or there is no
      # openid_url included with the error. Give a generic
      # failure message. The library should supply debug
      # information in a log.
      raise VerificationFailed('Verification failed.')
