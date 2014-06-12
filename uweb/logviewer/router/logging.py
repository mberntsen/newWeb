#!/usr/bin/python
"""Web interface for Underdark LogViewer"""

# Custom modules
import uweb
from uweb.logviewer import viewer

CONFIG = '../logging.conf'
PACKAGE = 'logviewer'

PAGE_CLASS = viewer.Viewer
ROUTES = (
    ('/', 'Index'),
    ('/db/(.*)', 'Database'),
    ('/static/(.*)', 'Static'),
    ('/(.*)', 'Invalidcommand'))

uweb.ServerSetup()
