#!/usr/bin/python
"""An uweb info page and testcase."""

# Custom modules
import uweb
from uweb.uweb_info import pages

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.3'

CONFIG = '../example.conf'
PACKAGE = 'uweb_info'

# PAGE_CLASS is the constant that defines the class that should handle requests
# from clients. The method to call is defined by the ROUTES constant below.
PAGE_CLASS = pages.PageMaker

# This router uses the constant `ROUTES` to provide a request router for the
# uWeb Handler. `ROUTES` is an iterable consisting of 2-tuples, each of which
# defines a regular expression and a method name. The regular expressions are
# tested in order, and must match the whole URL that is requested.
# If a match is found, traversal stops and the method name corresponding the
# regex is looked up on the provided `PAGE_CLASS`. This method is then used to
# generate a response.
#
# Any capture groups defined in the regular expressions of the `ROUTES` will
# be provided as arguments on the methods they call to.
ROUTES = (
    ('/static/(.*)', 'Static'),
    ('/(broken.*)', 'FourOhFour'),
    ('/haltandcatchfire', 'MakeFail'),
    ('/json', 'Json'),
    ('/text', 'Text'),
    ('/redirect/(.*)', 'Redirect'),
    ('/OpenIDLogin', '_OpenIdInitiate'),
    ('/OpenIDValidate', '_OpenIdValidate'),
    ('/ULF-Challenge', '_ULF_Challenge'),
    ('/ULF-Login', '_ULF_Verify'),
    ('/([\w\-_/]*)', 'Index'),
    ('/(.*)', 'NonWordCatchall'))


uweb.ServerSetup(apache_logging=True)
