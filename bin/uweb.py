"""uweb factory script"""
__author__ = "Underdark (Jacko Hoogeveen, jacko@underdark.nl)"
__version__ = "1.0"

import os
import shutil
import sys
import logging
from optparse import OptionParser
           
ROUTER_PATH = 'router'
ROUTER_NAME = 'router.py'
APACHE_CONFIG_NAME = 'apache.conf'

def ParseArguments():
  """Parse project arguments and objects"""
  parser = OptionParser(add_help_option=True)
  parser.add_option('-n',
                    '--name',
                     action='store',
                     default='uweb_project',
                     dest='name')
  
  parser.add_option('-d',
                    '--domain',
                    action='store',
                    default='uweb.local',
                    dest='host')
  
  parser.add_option('-p',
                    '--path',
                    action='store',
                    default=os.getcwd(),
                    dest='path')
  
  parser.add_option('-f',
                    '--force',
                    action='store_true',
                    default=False,
                    dest='force')
                    
  parser.add_option('-s',
                    '--silent',
                    action='store_true',
                    default=False,
                    dest='silent')
  
  return parser.parse_args()

def GenerateApacheConfig(document_root, server_name, router_file):
  """Returns apache config string based on arguments"""
  return """<VirtualHost *:80>
 documentroot %(document_root)s
 servername %(server_name)s
</VirtualHost>

<Directory "%(document_root)s">
 SetHandler mod_python
 PythonHandler %(router_name)s
 PythonAutoReload on
 PythonDebug on
</Directory>""" % {'document_root':document_root,
                   'server_name':server_name,
                   'router_name':router_file}

def Initialize(arguments):
  """Generate new uweb instance"""
  logging.debug('--------------------------------------------')
  logging.debug('initializing uweb')
  logging.debug('--------------------------------------------')
  
  #set al paths
  uweb_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  project_path = os.path.abspath(arguments.name)
  router_path = os.path.join(project_path, ROUTER_PATH, ROUTER_NAME)
  source_path = os.path.dirname('%s/base_project/' % uweb_path)
  
  router_destination = os.path.join(project_path,
                                    ROUTER_PATH, 
                                    arguments.name + '.py')
  
  apache_config_path = os.path.join(project_path,
                                    APACHE_CONFIG_NAME)
  
  #remove original project if needed
  if arguments.force:
    logging.debug('removing original files')
    try:
      shutil.rmtree(project_path) 
    except OSError:
      pass
  
  #copy uweb demo project
  logging.debug('cloning uweb source')
  try:
    shutil.copytree(source_path, project_path)
  except OSError:
    logging.debug('Project already excist, use -f (force) to whipe project.')
    return Fail()
  
  #adjust router name
  logging.debug('setting up router')
  shutil.move(router_path, router_destination)
  router_path = router_destination
  
  #write apache config
  logging.debug('setting up apache config')
  with open(apache_config_path, 'w') as apache_file:
    apache_file.write(GenerateApacheConfig(project_path,
                                           arguments.host,
                                           arguments.name))
  
  return Succes()

def main():
  """Main uweb method"""
  options, arguments = ParseArguments()
  
  
  if not options.silent:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    root_logger.addHandler(handler)
  
  if 'init' in arguments:
    Initialize(options)
  elif 'genconf' in arguments:
    print GenerateApacheConfig(options.path, options.host, options.name)

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

if __name__ == '__main__':
  main()
