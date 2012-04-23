"""Create apache config file based on given arguments"""
__author__ = "Underdark (Jacko Hoogeveen, jacko@underdark.nl)"
__version__ = "1.0"


import os

def main():
  """Create apache config file based on given arguments"""
  uweb_path = os.path.abspath(os.path.dirname(__file__))
  uweb_path = uweb_path[:uweb_path.rindex('/')]

  file_name = raw_input ('Enter the name of the destionation file.\nfile name: ')
  server_name = raw_input ('Enter the server name:\n for example: myserver.com\nserver name: ')
  router_path = raw_input ('Enter the absolute folder location of your router.\nrouter path: ')
  document_root = router_path[:router_path.rindex('/')+1]
  router_name = router_path[router_path.rindex('/')+1:]

  if '.py' in router_name:
    router_name = router_name[:-3]

  with open(file_name, 'w') as config:
    config.write("""NameVirtualHost *:80

    <VirtualHost *:80>
      document_root %(document_root)s
      server_name %(server_name)s
    </VirtualHost>

    <Directory "%(document_root)s">
      SetHandler mod_python
      PythonHandler %(router_name)s
      PythonPath "['%(uweb_path)s'] + sys.path"
      PythonAutoReload on
      PythonDebug on
    </Directory>
    """ % {'document_root':document_root,
           'server_name':server_name,
           'router_name':router_name,
           'uweb_path':uweb_path})
