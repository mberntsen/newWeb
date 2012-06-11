= Uweb base =
This is a uWeb base project that provides the basic needed files and layout to
build an uWeb project

Code-wise, it holds the following:
* uWeb request routing and server setup (in 'www/router.py');
* the router read the config file in base.conf
* use of PageMaker, and Page classes (in 'pages.py');
* use of the templateparser (in 'pages.py') and templates (in 'templates/').

It doesn't contain the following:
* Database connectivity.

= How to run =
You can either set this project up for Apache + mod_python use, or standalone:
* standalone
  * `python www/router.py`
  * The server is bound to 0.0.0.0:8082 (reachable via 'http://localhost:8082')
* mod_python
  * Symlink the www base folder to /var/www/uweb_base (sudo ln -sf ./www /var/www/uweb_base)
  * Copy 'apache.conf' to /etc/apache2/sites-available/uweb_base
  * Enable the site (`sudo a2ensite uweb_base`)
  * Reload apache config (`sudo service apache2 reload`)

--- 2012-06-01 @ 14:48:10 CET (+0100)
