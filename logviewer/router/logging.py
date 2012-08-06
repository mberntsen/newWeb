#!/usr/bin/python
"""Web interface for Underdark LogViewer"""

# Custom modules
import uweb
from uweb.logviewer import viewer

__author__ = 'Elmer de Looff'
__version__ = '0.3'

CONFIG = '../logging.conf'
PACKAGE = 'logviewer'

PAGE_CLASS = viewer.Viewer
ROUTES = (
    ('/', 'Index'),
    ('/db/(.*)', 'Database'),
    ('/static/(.*)', 'Static'),
    ('/(.*)', 'Invalidcommand'))

uweb.ServerSetup()
