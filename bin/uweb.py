#!/usr/bin/python
"""uweb factory script"""
__author__ = "Underdark (Jacko Hoogeveen, jacko@underdark.nl)"
__version__ = "1.0"

import os
import shutil
import sys
import logging
import json
from optparse import OptionParser

ROUTER_PATH = 'router'
ROUTER_NAME = 'router.py'
APACHE_CONFIG_NAME = 'apache.conf'

SITES_FILE = 'sites.json'



class BaseOperation(object):
  def ParseCall(self):
    raise NotImplementedError

  def DoThings(self):
    opts, args = self.ParseCall()
    self(*args[1:], **opts)

  def __call__(self, *args, **kwds):
    raise NotImplementedError


class Init(BaseOperation):
  def ParseCall(self):
    parser = OptionParser(add_help_option=False)
    parser.add_option('-n',
                    '--name',
                     action='store',
                     default='uweb_project',
                     dest='name')

    parser.add_option('-f',
                    '--force',
                    action='store_true',
                    default=False,
                    dest='force')

    parser.add_option('-h',
                    '--host',
                    action='store',
                    default='uweb.local',
                    dest='host')

    parser.add_option('-p',
                    '--path',
                    action='store',
                    default=os.getcwd(),
                    dest='path')

    parser.add_option('-s',
                    '--silent',
                    action='store_true',
                    default=False,
                    dest='silent')

    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name='uweb_project', force=False,
      path=os.getcwd(), silent=False, host='uweb.local', *args):
    """Generate new uweb instance"""

    project_path = os.path.abspath(name)
    source_path = os.path.dirname('%s/base_project/' % LibraryLocation())
    apache_path = os.path.join(project_path, APACHE_CONFIG_NAME)


    logging.debug('--------------------------------------------')
    logging.debug('initializing uweb')
    logging.debug('--------------------------------------------')

    if force:
      RemoveProject(project_path)

    if not CopySource(source_path, project_path):
      return Fail()

    router_path = os.path.join(project_path, ROUTER_PATH, ROUTER_NAME)

    router_path = AdjustRouterName(router_path, project_path, name)
    WriteApacheConfig(name, host, apache_path, project_path)

    Add()(name, router_path)

    return Succes()

class GenerateApacheConfig(BaseOperation):
  def ParseCall(self):
    """Parse project arguments and options"""
    parser = OptionParser(add_help_option=True)
    parser.add_option('-n',
                      '--name',
                       action='store',
                       default='uweb_project',
                       dest='name')

    parser.add_option('-p',
                      '--path',
                      action='store',
                      default=os.getcwd(),
                      dest='path')
    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name, host, path):
    """Returns apache config string based on arguments"""
    return ('<VirtualHost *:80>\n'
            '  documentroot %(path)s\n'
            'servername %(host)s\n'
            '</VirtualHost>\n\n'
            '<Directory "%(path)s">\n'
            '  SetHandler mod_python'
            '  PythonHandler %(name)s\n'
            '  PythonAutoReload on\n'
            '  PythonDebug on\n'
            '</Directory>') % {'path':path,
                                'name':name,
                                'host':host}

class Sites(BaseOperation):
  def ParseCall(self):
    return {}, ()

  def __call__(self):
    data = Sites();
    for site in data:
      print '%s: %s' % (site, data[site]['router'])

    if not data:
      print 'no sites active'


class Add(BaseOperation):
  def ParseCall(self):
    """Parse project arguments and options"""
    parser = OptionParser(add_help_option=True)
    parser.add_option('-n',
                      '--name',
                       action='store',
                       default='uweb_project',
                       dest='name')

    parser.add_option('-r',
                      '--router',
                      action='store',
                      dest='router')

    parser.add_option('-e',
                      '--enable',
                      action='store_true',
                      default=os.getcwd(),
                      dest='auto_enable')

    parser.add_option('-f',
                    '--force',
                    action='store_true',
                    default=False,
                    dest='force')

    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name, router, auto_enable=False, force=False):
    data = Sites();

    if name in data and not force:
      logging.debug('Could not add site, site already does excist')
      logging.debug('add -f (force) flag to overwrite')
      return False

    data[name] = {'router':router}

    if auto_enable:
      pass

    with open(SitesLocation(), 'w') as sites_file:
      sites_file.write(json.dumps(data))

class Remove(BaseOperation):
  def ParseCall(self):
    """Parse project arguments and options"""
    parser = OptionParser(add_help_option=True)
    parser.add_option('-n',
                      '--name',
                       action='store',
                       default='uweb_project',
                       dest='name')

    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name):
    data = Sites();

    if not name in data:
      return False

    del data[name]
    with open(SitesLocation(), 'w') as sites_file:
      sites_file.write(json.dumps(data))

    return True

class Start(BaseOperation):
  def ParseCall(self):
    """Parse project arguments and options"""
    parser = OptionParser(add_help_option=True)
    parser.add_option('-n',
                      '--name',
                       action='store',
                       default='uweb_project',
                       dest='name')

    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name):
    data = Sites()
    os.system('%s start' % data[name]['router'])

class Restart(BaseOperation):
  def ParseCall(self):
    """Parse project arguments and options"""
    parser = OptionParser(add_help_option=True)
    parser.add_option('-n',
                      '--name',
                       action='store',
                       default='uweb_project',
                       dest='name')

    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name):
    data = Sites()
    os.system('%s restart' % data[name]['router'])

class Stop(BaseOperation):
  def ParseCall(self):
    """Parse project arguments and options"""
    parser = OptionParser(add_help_option=True)
    parser.add_option('-n',
                      '--name',
                       action='store',
                       default='uweb_project',
                       dest='name')

    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name):
    data = Sites()
    os.system('%s stop' % data[name]['router'])

def Sites():
  if not os.path.isfile(SitesLocation()):
    return Create_sites_location();
  else:
    with open(SitesLocation(), 'r') as sites_file:
      data = json.load(sites_file)
      return data

def CreateSitesFile():
  if not os.path.isfile(SitesLocation()):
    with open(SitesLocation(), 'w') as sites_file:
      sites_file.write(json.dumps({}))
      return {}


def AdjustRouterName(router_path, project_path, name):
  """Rename router and return new name"""
  router_destination = os.path.join(os.path.dirname(router_path),
                                    name + '.py')

  logging.debug('setting up router')
  shutil.move(router_path, router_destination)
  return router_destination

def CopySource(source_path, project_path):
  """Copy source files from uweb demo project"""
  logging.debug('cloning uweb source')
  try:
    shutil.copytree(source_path, project_path)
  except OSError as error:
    logging.debug(error)
    logging.debug('Project already excist, use -f (force) to wipe project.')
    return False
  return True

def RemoveProject(project_path):
  """Removes project"""
  logging.debug('wiping old project')
  try:
    shutil.rmtree(project_path)
  except OSError:
    pass

def WriteApacheConfig(name, host, apache_config_path, project_path):
  """write apache config file"""
  logging.debug('setting up apache config')
  with open(apache_config_path, 'w') as apache_file:
    string = GenerateApacheConfig()(name, host, project_path)
    apache_file.write(string)

FUNCTIONS = {'init': Init,
             'genconf': GenerateApacheConfig,
             'sites':Sites,
             'add':Add,
             'remove':Remove,
             'start':Start,
             'restart':Restart,
             'stop':Stop}

def readlinkabs(l):
  """Return an absolute path for the destination of a symlink"""
  assert (os.path.islink(l))
  p = os.readlink(l)
  if os.path.isabs(p):
      return p
  return os.path.join(os.path.dirname(l), p)

def LibraryLocation():
  return os.path.dirname(os.path.dirname(UwebFileLocation()))

def UwebFileLocation():
  return readlinkabs(os.path.abspath(__file__))

def SitesLocation():
  return os.path.abspath(os.path.join(os.path.dirname(UwebFileLocation()), SITES_FILE))

def Succes():
  """Script has succeeded"""
  logging.debug('--------------------------------------------')
  logging.debug('initialization complete - have fun with uweb')
  logging.debug('--------------------------------------------')
  return True

def Fail():
  """Script has failed"""
  logging.debug('--------------------------------------------')
  logging.debug('initialization failed - check details above')
  logging.debug('--------------------------------------------')
  return False

def main():
  """Main uweb method"""
  if not False:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    root_logger.addHandler(handler)


  FUNCTIONS[sys.argv[1]]().DoThings()

if __name__ == '__main__':
  main()
