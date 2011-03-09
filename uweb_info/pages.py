#!/usr/bin/python
"""Html generators for the minimal uweb server"""

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.3'

# Standard modules
import time

# Custom modules
from underdark.libs import logging
from underdark.libs import uweb
from underdark.libs.uweb import uwebopenid

class PageMaker(uweb.DebuggingPageMaker):
  """Holds all the html generators for the webapp

  Each page as a separate method.
  """
  def CommonBlocks(self, page_id):
    """Returns the common header and footer blocks for this project."""
    return {'header': self.parser.Parse('header.html', page_id=page_id),
            'footer': self.parser.Parse(
                'footer.html',
                year=time.strftime('%Y'),
                version=uweb.__version__)}

  def Index(self, _path):
    """Returns the index.html template"""
    logging.LogInfo('Index page requested')

    gethtml = []
    for getvar in sorted(self.get):
      gethtml.append(self.parser.Parse(
          'varlisting.html', var=(getvar, self.get[getvar])))

    posthtml = []
    for postvar in sorted(self.post):
      posthtml.append(self.parser.Parse(
          'varlisting.html', var=(postvar, self.post.getlist(postvar))))

    cookieshtml = []
    for cookie in sorted(self.cookies):
      cookieshtml.append(self.parser.Parse(
          'varlisting.html', var=(cookie, self.cookies[cookie].value)))

    headershtml = []
    for header in sorted(self.req.headers.items()):
      headershtml.append(self.parser.Parse('varlisting.html', var=header))

    envhtml = []
    for environ_item in sorted(self.req.env.items()):
      envhtml.append(self.parser.Parse('varlisting.html', var=environ_item))

    extenvhtml = []
    environ_keys = set(self.req.env)
    for ext_only in sorted(set(self.req.ExtendedEnvironment()) - environ_keys):
      extenvhtml.append(self.parser.Parse(
          'varlisting.html', var=(ext_only, self.req.env[ext_only])))

    nulldata = '<li><em>NULL</em></li>'
    return self.parser.Parse('index.html',
                              method=self.req.env['REQUEST_METHOD'],
                              getvars=''.join(gethtml) or nulldata,
                              postvars=''.join(posthtml) or nulldata,
                              cookies=''.join(cookieshtml) or nulldata,
                              headers=''.join(headershtml),
                              env=''.join(envhtml),
                              ext_env=''.join(extenvhtml),
                              **self.CommonBlocks('main'))

  @staticmethod
  def MakeFail():
    """Triggers a HTTP 500 Internal Server Error in uWeb.

    This is a demonstration of the (limited) debugging facilities in uWeb.
    A small stack of calls is created, the last of which raises an error.
    The resulting stack trace and a short introductory message is returned to
    the browser, tagged with a HTTP response code 500.
    """
    def _Processor(function):
      """Uses the given `function` to process the string literal 'foo' with."""
      function('foo')

    def _MakeInteger(numeric_string):
      """Returns the integer value of a numeric string using int()."""
      return int(numeric_string)

    return _Processor(_MakeInteger)

  @staticmethod
  def Text():
    """Returns a page with data in text/plain.

    To return a different content type, the returned object must be a Page,
    where the `content_type` argument can be set to any desired mimetype.
    """
    logging.LogInfo('Text page requested')
    text = """
        <h1>This is a text-only page.</h1>

        Linebreaks and leading whitespace are honored.
        <strong>HTML tags do nothing, as demonstrated above<strong>.
        """
    return uweb.Response(content=text, content_type='text/plain')

  @staticmethod
  def Redirect(location):
    """Generated a temporary redirect to the given URL.

    Returns a Page object with a custom HTTP Code (307 in our case), which
    trigger uWeb to send a HTTP_TEMPORARY_REDIRECT. The custom Location: header
    then directs the client to the given URL.

    From the specification:
      [http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html]

      The requested resource resides temporarily under a different URI. Since
      the redirection MAY be altered on occasion, the client SHOULD continue to
      use the Request-URI for future requests. This response is only cacheable
      if indicated by a Cache-Control or Expires header field.

      The temporary URI SHOULD be given by the Location field in the response.
      Unless the request method was HEAD, the entity of the response SHOULD
      contain a short hypertext note with a hyperlink to the new URI(s) , since
      many pre-HTTP/1.1 user agents do not understand the 307 status. Therefore,
      the note SHOULD contain the information necessary for a user to repeat the
      original request on the new URI.

      If the 307 status code is received in response to a request other than GET
      or HEAD, the user agent MUST NOT automatically redirect the request unless
      it can be confirmed by the user, since this might change the conditions
      under which the request was issued.

    Arguments:
      @ location: str
        The full URL the client should be redirected to, including schema.
    """
    return uweb.Response(headers={'Location': location}, httpcode=307)

  def FourOhFour(self, path):
    """The request could not be fulfilled, this returns a 404."""
    logging.LogWarning('Bad page %r requested', path)
    return uweb.Response(
        httpcode=404,
        content=self.parser.Parse(
            '404.html', path=path, **self.CommonBlocks('http404')))

  def InternalServerError(self):
    """Returns a HTTP 500 page, since the request failed elsewhere."""
    if ('debug' in self.req.env['QUERY_STRING'].lower() or
        'openid' in self.req.env['PATH_INFO'].lower()):
      # Returns the default HTTP 500 handler result. For this class, since we
      # subclassed DebuggingPageMaker, it has all sorts of debug info.
      return super(PageMaker, self).InternalServerError()
    else:
      # Return our custom styled HTTP 500 handler instead, this is what you'll
      # want to serve during production; the debugging one gives too much info.
      path = self.req.env['PATH_INFO']
      logging.LogError('Execution of %r triggered an exception', path)
      return uweb.Response(
          httpcode=500,
          content=self.parser.Parse(
              '500.html', path=path, **self.CommonBlocks('http500')))

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
      user = uwebopenid.OpenId(self.req).doProcess()
    except uwebopenid.VerificationFailed, error:
      return self.OpenIdAuthFailure(error)
    except uwebopenid.VerificationCanceled, error:
      return self.OpenIdAuthCancel(error)
    return self.OpenIdAuthSuccess('welcome %s, %r, %r, %s' % user)


  def OpenIdProviderBadLink(self, err_obj):
    return self.parser.Parse(
        'freetext.html',
        title='Bad OpenID Provider URL',
        message=err_obj,
        **self.CommonBlocks('uweb'))

  def OpenIdProviderError(self, err_obj):
    message = 'The OpenID provider did not respond as expected: %r' % err_obj
    return self.parser.Parse(
        'freetext.html',
        title='Bad OpenID Provider',
        message=message,
        **self.CommonBlocks('uweb'))

  def OpenIdAuthCancel(self, err_obj):
    return self.parser.Parse(
        'freetext.html',
        title='OpenID Authentication canceled by user',
        message=err_obj,
        **self.CommonBlocks('uweb'))

  def OpenIdAuthFailure(self, err_obj):
    return self.parser.Parse(
        'freetext.html',
        title='OpenID Authentication failed',
        message=err_obj,
        **self.CommonBlocks('uweb'))

  def OpenIdAuthSuccess(self, message):
    import base64
    import os
    message = 'You are now known as ' + message
    self.req.AddCookie('FirstMinuteLogin', 'True', max_age=60)
    self.req.AddCookie(
        'OpenIDSession', base64.urlsafe_b64encode(os.urandom(30)), max_age=3600)
    return self.parser.Parse(
        'freetext.html',
        title='OpenID Authentication successful',
        message=message,
        **self.CommonBlocks('uweb'))
