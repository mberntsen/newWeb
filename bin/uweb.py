#!/usr/bin/python
"""uweb factory script"""
__author__ = "Underdark (Jacko Hoogeveen, jacko@underdark.nl)"
__version__ = "1.0"

import os
import shutil
import simplejson
import sys
import logging
import subprocess
from optparse import OptionParser

# Application specific modules
import tables


class Error(Exception):
  """Base class for application errors."""


class UwebSites(object):
  SITES_BASE = {'uweb_info': {'router': 'uweb.uweb_info.router.uweb_info',
                              'workdir': '/'},
                'logviewer': {'router': 'uweb.logviewer.router.logging',
                              'workdir': '/'}}

  """Abstraction for the uWeb site managing JSON file."""
  def __init__(self):
    self.sites_file = os.path.expanduser('~/.uweb/sites.json')
    self.sites = self._LoadSites()

  def _InstallBaseSites(self):
    """Create sites file with default data, and directory where necessary."""
    dirname = os.path.dirname(self.sites_file)
    if not os.path.isdir(dirname):
      print '.. no uweb data directory; creating %r' % dirname
      os.mkdir(os.path.dirname(self.sites_file))
    with file(self.sites_file, 'w') as sites:
      print '.. creating %r with default sites' % self.sites_file
      sites.write(simplejson.dumps(self.SITES_BASE))
    print ''

  def _LoadSites(self):
    """Load the sites file and return parsed JSON."""
    if not os.path.exists(self.sites_file):
      self._InstallBaseSites()
    with file(self.sites_file) as sites:
      try:
        return simplejson.loads(sites.read())
      except simplejson.JSONDecodeError:
        raise Error('Could not read %r: Illegal JSON syntax' % self.sites_file)

  def _WriteSites(self):
    """Write a new sites file after changes were made."""
    with file(self.sites_file, 'w') as sites:
      sites.write(simplejson.dumps(self.sites))

  def __contains__(self, key):
    return key in self.sites

  def __iter__(self):
    return iter(sorted(self.sites.items()))

  def __nonzero__(self):
    return bool(self.sites)

  def __getitem__(self, name):
    return self.sites[name]

  def __setitem__(self, name, router):
    self.sites[name] = router
    self._WriteSites()

  def __delitem__(self, name):
    if name not in self.sites:
      raise ValueError('There is no site with name %r' % name)
    del self.sites[name]
    self._WriteSites()


class BaseOperation(object):
  """A simple class which parses command line values and call's it self."""
  def ParseCall(self):
    """Base method to parse arguments and options."""
    raise NotImplementedError

  @staticmethod
  def Banner(message):
    line = '-' * 62
    return '+%s+\n| %-60s |\n+%s+' % (line, message[:60], line)

  def Run(self):
    """Default method to parse arguments/options and activate class"""
    opts, args = self.ParseCall()
    self(*args[1:], **opts)

  def __call__(self, *args, **kwds):
    """Base method to activate class"""
    raise NotImplementedError


# ##############################################################################
# Initialization of and Apache configuration for projects
#
class Init(BaseOperation):
  """Inintialize uweb generator which create new uweb instance"""
  # Base directory where the uWeb library lives
  LIBRARY_PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
  ROUTER_PATH = 'router'
  ROUTER_NAME = 'router.py'
  APACHE_CONFIG_NAME = 'apache.conf'

  def ParseCall(self):
    parser = OptionParser(add_help_option=False)
    parser.add_option('-f', '--force', action='store_true',
                      default=False, dest='force')
    parser.add_option('-h', '--host', action='store', dest='host')
    parser.add_option('-p', '--path', action='store',
                    default=os.getcwd(), dest='path')
    parser.add_option('-s', '--silent', action='store_true',
                    default=False, dest='silent')

    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name=None, force=False, path=None, silent=False,
               host='uweb.local'):
    if name is None:
      raise Error('Initialization requires a project name.')
    project_path = os.path.abspath(name)
    source_path = os.path.dirname('%s/base_project/' % self.LIBRARY_PATH)
    apache_path = os.path.join(project_path, self.APACHE_CONFIG_NAME)

    print self.Banner('initializing new uWeb project %r' % name)
    if os.path.exists(project_path):
      if force:
        print '* Removing existing project directory'
        shutil.rmtree(project_path)
      else:
        raise Error('Target already exists, use -f (force) to overwrite.')
    print '* copying uWeb base project directory'
    shutil.copytree(source_path, project_path)
    os.chdir(project_path)
    print '* setting up router'
    router_path = os.path.join(self.ROUTER_PATH, self.ROUTER_NAME)
    router_destination = os.path.join(self.ROUTER_PATH, '%s.py' % name)
    shutil.move(router_path, router_destination)

    print '* setting up apache config'
    GenerateApacheConfig.WriteApacheConfig(name,
                                           host,
                                           apache_path,
                                           project_path)

    # Make sure we add the project to the sites list
#    sites = UwebSites()
#    sites[name] = router
    print self.Banner('initialization complete - have fun with uWeb')


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

  def __call__(self, name, host, path):
    """Returns apache config string based on arguments"""
    return ('<VirtualHost *:80>\n'
            '    documentroot %(path)s\n'
            '    servername %(host)s\n'
            '</VirtualHost>\n\n'
            '<Directory "%(path)s">\n'
            '    SetHandler mod_python\n'
            '    PythonHandler %(name)s\n'
            '    PythonAutoReload on\n'
            '    PythonDebug on\n'
            '</Directory>') % {'path': path, 'name': name, 'host': host}

  @staticmethod
  def WriteApacheConfig(name, host, apache_config_path, project_path):
    """write apache config file"""
    with open(apache_config_path, 'w') as apache_file:
      string = GenerateApacheConfig()(name, host, project_path)
      apache_file.write(string)


# ##############################################################################
# Commands to manage configured uWeb sites.
#
class ListSites(BaseOperation):
  """Print availible uweb sites."""
  def ParseCall(self):
    return {}, ()

  def __call__(self, *args):
    sites = UwebSites()
    if not sites:
      raise Error('No configured uWeb sites.')
    print 'Overview of active sites:\n'
    configs = [(name, site['router'], site['workdir']) for name, site in sites]
    names, routers, dirs = zip(*configs)
    print tables.Table(tables.Column('Name', names),
                       tables.Column('Router', routers),
                       tables.Column('Working dir', dirs))


class Add(BaseOperation):
  """Register uweb site"""
  def ParseCall(self):
    parser = OptionParser()
    parser.add_option('-d', '--directory', action='store',
                    default='/', dest='directory')
    parser.add_option('-u', '--update', action='store_true',
                    default=False, dest='update')

    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name, router, directory='/', update=False):
    sites = UwebSites()
    if name in sites and not update:
      raise Error('Could not add a router with this name, one already exists.'
                  '\n\nTo update the existing, use the --update flag')
    sites[name] = {'router': router, 'workdir': directory}


class Remove(BaseOperation):
  """Unregister uweb site"""
  def ParseCall(self):
    parser = OptionParser()
    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name, *args):
    try:
      sites = UwebSites()
      del sites[name]
    except ValueError:
      raise Error('There was no site named %r' % name)


# ##############################################################################
# Commands to control configured uWeb routers.
#
class Start(BaseOperation):
  """Start project router"""
  def ParseCall(self):
    parser = OptionParser()
    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name, *args):
    site = UwebSites()[name]
    return subprocess.Popen(['python', '-m', site['router'], 'start'],
                            cwd=site['workdir']).wait()


class Stop(BaseOperation):
  """Stop project router"""
  def ParseCall(self):
    parser = OptionParser()
    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name, *args):
    site = UwebSites()[name]
    return subprocess.Popen(['python', '-m', site['router'], 'stop'],
                            cwd=site['workdir']).wait()


class Restart(BaseOperation):
  """Restart project router"""
  def ParseCall(self):
    parser = OptionParser()
    opts, args = parser.parse_args()
    return vars(opts), args

  def __call__(self, name, *args):
    site = UwebSites()[name]
    return subprocess.Popen(['python', '-m', site['router'], 'restart'],
                            cwd=site['workdir']).wait()


FUNCTIONS = {'init': Init,
             'genconf': GenerateApacheConfig,
             'list': ListSites,
             'add': Add,
             'remove': Remove,
             'start': Start,
             'restart': Restart,
             'stop': Stop}


def LongestImportPrefix(package):
  import sys
  candidates = []
  for path in sys.path:
    if package.startswith(path + os.sep):
      candidates.append(path)
  print max(candidates, key=len)



def main():
  """Main uweb method"""
  root_logger = logging.getLogger()
  root_logger.setLevel(logging.DEBUG)
  handler = logging.StreamHandler(sys.stdout)
  root_logger.addHandler(handler)

  try:
    FUNCTIONS[sys.argv[1]]().Run()
  except Error, err_obj:
    sys.exit('Error: %s' % err_obj)
  except (IOError, OSError), err_obj:
    sys.exit('I/O Error: %s' % err_obj)

if __name__ == '__main__':
  main()
