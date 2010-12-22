#!/usr/bin/python
"""Html generators for the minimal uweb server"""

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.3'

# Standard modules
import time

# Custom modules
from underdark.libs import logging
from underdark.libs import uweb

class PageMaker(uweb.BasePageMaker):
  """Holds all the html generators for the webapp

  Each page as a separate method.
  """
  def CommonBlocks(self):
    return {'header': self.parser.Parse('header.html'),
            'footer': self.parser.Parse(
                'footer.html',
                year=time.strftime('%Y'),
                version=uweb.__version__)}

  def RequestIndex(self, path=None):
    """Returns the index.html template"""
    logging.LogInfo('Index page requested')

    gethtml = []
    for getvar in sorted(self.get):
      gethtml.append(self.parser.Parse(
          'varlisting.html', (getvar, self.get[getvar])))

    posthtml = []
    for postvar in sorted(self.post):
      posthtml.append(self.parser.Parse(
          'varlisting.html', var=(postvar, self.post.getlist(postvar))))

    cookieshtml = []
    for cookie in sorted(self.cookies):
      cookieshtml.append(self.parser.Parse(
          'varlisting.html', var=(cookie, self.cookies[cookie])))

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
                              **self.CommonBlocks())

  def RequestText(self):
    """Returns a page with data in text/plain.

    To return a different content type, the returned object must be a Page,
    where the `content_type` argument can be set to any desired mimetype.
    """
    # if a different content_type should be returned, create a Page object
    logging.LogInfo('Text page requested')
    text = """
        <h1>This is a text-only page.</h1>

        Linebreaks and leading whitespace are honored.
        <strong>HTML tags do nothing, as demonstrated above<strong>.
        """
    return uweb.Page(content=text, content_type='text/plain')

  @staticmethod
  def RequestRedirect(location):
    """Generated a temporary redirect to the given URL.

    Returns a Page object with a custom HTTP Code (302 in our case), which
    trigger uWeb to send a HTTP_MOVED_TEMPORARILY. The custom Location: header
    then directs the client to the given URL.

    Arguments:
      @ location: str
        The full URL the client should be redirected to, including schema.
    """
    return uweb.Page('', headers={'Location': location}, httpcode=302)

  def RequestInvalidcommand(self, command):
    """Returns an error message"""
    logging.LogWarning('Bad page %r requested', command)
    return uweb.Page(self.parser.Parse(
        '404.html', error=command, **self.CommonBlocks()), httpcode=404)
