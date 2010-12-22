= Uweb Info =
This is a uWeb demo project that provides an insight in how uWeb is used. It's
a simple set of webpages that by default shows a listing of incoming headers,
query arguments, POST and Cookie data, and various environment variables.

Code-wise, it showcases the following:
* uWeb request routing and server setup (in 'www/router.py');
* use of PageMaker, and Page classes (in 'pages.py');
* use of the templateparser (in 'pages.py') and templates (in 'templates/').

It doesn't showcase the following:
* Configuration files and automatic parsing thereof;
* Database connectivity.


= How to run =
You can either set this project up for Apache + mod_python use, or standalone:
* mod_python
  * Copy 'apache.conf' to /etc/apache2/sites-available/uweb_info
  * Enable the site (`sudo a2ensite uweb_info`)
  * Reload apache config (`sudo service apache2 reload`)
* standalone
  * `python www/router.py`
  * The server is bound to 0.0.0.0:8082 (reachable via 'http://localhost:8082')


--- 2010-12-22 @ 13:38:25 CET (+0100)
