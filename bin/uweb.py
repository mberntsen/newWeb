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
UWEB_DATA_FOLDER = os.path.expanduser('~/.uweb')
SITES_FILE_NAME = 'sites.json'
SITES_FILE_PATH = os.path.join(UWEB_DATA_FOLDER, SITES_FILE_NAME)

# Navigate one directory up to get the library path
LOCAL_FILE = os.path.realpath(__file__)
LIBRARY_PATH = os.path.dirname(os.path.dirname(LOCAL_FILE))

class BaseOperation(object):
  """A simple class which parses command line values and call's it self."""
  def ParseCall(self):
    """Base method to parse arguments and options."""
    raise NotImplementedError

  def DoThings(self):
    """Default method to parse arguments/options and activate class"""
    opts, args = self.ParseCall()
    self(*args[1:], **opts)

  def __call__(self, *args, **kwds):
    """Base method to activate class"""
    raise NotImplementedError


class Init(BaseOperation):
  """Inintialize uweb generator which create new uweb instance"""
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

    project_path = os.path.abspath(name)
    source_path = os.path.dirname('%s/base_project/' % LIBRARY_PATH)
    apache_path = os.path.join(project_path, APACHE_CONFIG_NAME)


    logging.debug('--------------------------------------------')
    logging.debug('initializing uweb')
    logging.debug('--------------------------------------------')

    if force:
      logging.debug('wiping old project')
      Init.RemoveProject(project_path)

    try:
      logging.debug('cloning uweb source')
      shutil.copytree(source_path, project_path)
    except OSError:
      logging.debug('Project already excist, use -f (force) to wipe project.')
      Init.Fail()
      return False

    router_path = os.path.join(project_path, ROUTER_PATH, ROUTER_NAME)
    router_destination = os.path.join(project_path, ROUTER_PATH,
                                      name + '.py')

    logging.debug('setting up router')
    shutil.move(router_path, router_destination)

    logging.debug('setting up apache config')
    GenerateApacheConfig.WriteApacheConfig(name,
                                           host,
                                           apache_path,
                                           project_path)

    logging.debug('setting up apache config')
    Add()(name, router_destination)
    Init.Succes()

  @staticmethod
  def RemoveProject(project_path):
    """Removes project"""
    try:
      shutil.rmtree(project_path)
    except OSError:
      pass

  @staticmethod
  def Succes():
    """Script has succeeded"""
    logging.debug('--------------------------------------------')
    logging.debug('initialization complete - have fun with uweb')
    logging.debug('--------------------------------------------')

  @staticmethod
  def Fail():
    """Script has failed"""
    logging.debug('--------------------------------------------')
    logging.debug('initialization failed - check details above')
    logging.debug('--------------------------------------------')

class GenerateApacheConfig(BaseOperation):
  """Generate apache config file for uweb project"""
  def ParseCall(self):
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

  def __call__(self, name, host, path, *args):
    """Returns apache config string based on arguments"""
    return ('<VirtualHost *:80>\n'
            '  documentroot %(path)s\n'
            '  servername %(host)s\n'
            '</VirtualHost>\n\n'
            '<Directory "%(path)s">\n'
            '  SetHandler mod_python\n'
            '  PythonHandler %(name)s\n'
            '  PythonAutoReload on\n'
            '  PythonDebug on\n'
            '</Directory>') % {'path':path,
                                'name':name,
                                'host':host}

  @staticmethod
  def WriteApacheConfig(name, host, apache_config_path, project_path):
    """write apache config file"""
    with open(apache_config_path, 'w') as apache_file:
      string = GenerateApacheConfig()(name, host, project_path)
      apache_file.write(string)

class Sites(BaseOperation):
  """Print availible uweb sites."""
  def ParseCall(self):
    return {}, ()

  def __call__(self, *args):
    sites = LoadSites()
    for site in sites:
      print '%s: %s' % (site, sites[site]['router'])

    if not sites:
      print 'no sites active'


class Add(BaseOperation):
  """Register uweb site"""
  def ParseCall(self):
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

  def __call__(self, name, router, auto_enable=False, force=False, *args):
    data = LoadSites()

    if name in data and not force:
      logging.debug('Could not add site, site already does excist')
      logging.debug('add -f (force) flag to overwrite')
      return False

    data[name] = {'router':router}

    if auto_enable:
      #TODO: start router automaticly when added
      pass

    with open(SITES_FILE_PATH, 'w') as sites_file:
      sites_file.write(json.dumps(data))

class Remove(BaseOperation):
  """Unregister uweb site"""
  def ParseCall(self):
    parser = OptionParser(add_help_option=True)
    parser.add_option('-n',
                      '--name',
                       action='store',
                       default='uweb_project',
                       dest='name')

    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name, *args):
    data = LoadSites()

    if not name in data:
      return False

    del data[name]
    with open(SITES_FILE_PATH, 'w') as sites_file:
      sites_file.write(json.dumps(data))

    return True

class Start(BaseOperation):
  """Start project router"""
  def ParseCall(self):
    parser = OptionParser(add_help_option=True)
    parser.add_option('-n',
                      '--name',
                       action='store',
                       default='uweb_project',
                       dest='name')

    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name, *args):
    data = LoadSites()
    os.system('%s start' % data[name]['router'])


class Restart(BaseOperation):
  """Restart project router"""
  def ParseCall(self):
    parser = OptionParser(add_help_option=True)
    parser.add_option('-n',
                      '--name',
                       action='store',
                       default='uweb_project',
                       dest='name')

    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name, *args):
    data = LoadSites()
    os.system('%s restart' % data[name]['router'])


class Stop(BaseOperation):
  """Stop project router"""
  def ParseCall(self):
    parser = OptionParser(add_help_option=True)
    parser.add_option('-n',
                      '--name',
                       action='store',
                       default='uweb_project',
                       dest='name')

    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name, *args):
    data = LoadSites()
    os.system('%s stop' % data[name]['router'])


def LoadSites():
  """Load uweb sites from file, create new file if needed"""
  if not os.path.isfile(SITES_FILE_PATH):
    return {}
  with open(SITES_FILE_PATH) as sites_file:
    return json.load(sites_file)

FUNCTIONS = {'init': Init,
             'genconf': GenerateApacheConfig,
             'sites':Sites,
             'add':Add,
             'remove':Remove,
             'start':Start,
             'restart':Restart,
             'stop':Stop}

def main():
  """Main uweb method"""
  if not os.path.isdir(UWEB_DATA_FOLDER):
    os.mkdir(UWEB_DATA_FOLDER)

  root_logger = logging.getLogger()
  root_logger.setLevel(logging.DEBUG)
  handler = logging.StreamHandler(sys.stdout)
  root_logger.addHandler(handler)


  FUNCTIONS[sys.argv[1]]().DoThings()

if __name__ == '__main__':
  main()
