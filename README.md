newWeb installation
===================

The easiest and quickest way to install newWeb is using Python's `virtualenv`. Install using the setuptools installation script, which will automatically gather dependencies.

```bash
# Set up the Python virtualenv
virtualenv env
source env/bin/activate

# Install newWeb
python setup.py install

# Or you can install in development mode which allows easy modification of the source:
python setup.py develop
```

Installation requirements
-------------------------

newWeb depends on mysql-python. To build the database connector from source you will need development headers for your version of Python and MySQL client. For debian-like linux these can be installed as follows:

```bash
sudo apt-get install python-dev libmysqlclient-dev
```