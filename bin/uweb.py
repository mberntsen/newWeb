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
  
  path = Get_paths(arguments)
  
  if arguments.force:
    Remove_project(path['project'])
  
  if not Copy_source(path['source'], path['project']):
    return Fail()
  
  Adjust_router_name(path['router'], path['project'], arguments.name)
  Write_apache_config(arguments, path['apache'], path['project'])
  
  return Succes()
  
def Get_paths(arguments):
  path = {}
  path['uweb'] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  path['project'] = os.path.abspath(arguments.name)
  path['router'] = os.path.join(path['project'], ROUTER_PATH, ROUTER_NAME)
  path['source'] = os.path.dirname('%s/base_project/' % path['uweb'])
  path['apache'] = os.path.join(path['project'],
                                 APACHE_CONFIG_NAME)
                                 
  return path

def Adjust_router_name(router_path, project_path, name):
  """Rename router and return new name"""
  router_destination = os.path.join(project_path, 
                                    name + '.py')
  
  logging.debug('setting up router')
  shutil.move(router_path, router_destination)

def Copy_source(source_path, project_path):
  """Copy source files from uweb demo project"""
  logging.debug('cloning uweb source')
  try:
    shutil.copytree(source_path, project_path)
  except OSError as error:
    logging.debug('Project already excist, use -f (force) to wipe project.')
    return False
  return True

def Remove_project(project_path):
  """Removes project"""
  logging.debug('wiping old project')
  try:
    shutil.rmtree(project_path) 
  except OSError:
    pass
  
def Write_apache_config(arguments, apache_config_path, project_path):
  """write apache config file"""
  logging.debug('setting up apache config')
  with open(apache_config_path, 'w') as apache_file:
    apache_file.write(GenerateApacheConfig(project_path,
                                           arguments.host,
                                           arguments.name))

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
    
if __name__ == '__main__':
  main()  
