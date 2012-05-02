"""Create apache config file based on given arguments"""
__author__ = "Underdark (Jacko Hoogeveen, jacko@underdark.nl)"
__version__ = "1.0"

import os
from optparse import OptionParser

def ParseArguments():
  parser = OptionParser(add_help_option=False)
  parser.add_option('-r', '--router', action='store', dest='router',
                      help='The absolute folder location of your router.')
  parser.add_option('-h', '--host', action='store', dest='host',
                      help='The host name. (example: underdark.nl)')
  parser.add_option('--help', action="store_true", dest="help",
                      help='Displays this help description.')

  arguments = parser.parse_args()[0]
  if arguments.help or (not arguments.router or not arguments.host):
    parser.print_help()
    return False

  return arguments

def GenerateConfig(document_root, server_name, router_file, uweb_path):
  print """NameVirtualHost *:80
  <VirtualHost *:80>
    document_root %(document_root)s
    server_name %(server_name)s
  </VirtualHost>

  <Directory "%(document_root)s/">
    SetHandler mod_python
    PythonHandler %(router_name)s
    PythonPath "['%(uweb_path)s'] + sys.path"
    PythonAutoReload on
    PythonDebug on
  </Directory>
  """ % {'document_root':document_root,
         'server_name':server_name,
         'router_name':router_file,
         'uweb_path':uweb_path}

def main():
  """Create apache config file based on given arguments"""
  arguments = ParseArguments()
  if arguments:
    uweb_path = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
    document_root, router_file = os.path.split(arguments.router)

    GenerateConfig(document_root, arguments.host,
        os.path.splitext(router_file)[0], uweb_path)

if __name__ == '__main__':
  main()
