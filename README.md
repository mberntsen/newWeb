# Handle with care

This fork of µWeb is very much a work in progress to fix some of the bad design decisions made during its development. For a full description of the rough edges of it, refer to the two relevant blog posts:

* [µWeb analysis part 1](http://variable-scope.com/posts/reflection-and-introspection-an-analysis-of-uweb) - general design and template system
* [µWeb analysis part 2](http://variable-scope.com/posts/reflection-and-introspection-an-analysis-of-uweb-part-2) - presenter, database layer and debug server

## Work so far

* Cut tons of code for the **standalone** module
* Started work on making newWeb a WSGI application framework
* Cut all but one of the packages from ext_lib

## Included (demo) projects

The following µWeb applications are included in the project:

* `uweb_info`: This demonstrates most µWeb/newWeb features, and gives you examples on how to use most of them.
* `base_project`: this is a bare bones, Hello World-like application and provides a scaffold for your own projects -- ***broken***
* `logviewer`: This allows you to see and browse errors reported by your µWeb applications -- ***broken***

# newWeb installation

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

## Installation requirements

newWeb depends on mysql-python. To build the database connector from source you will need development headers for your version of Python and MySQL client. For Debian and Debian-derived flavors Linux these can be installed using apt:

```bash
sudo apt-get install python-dev libmysqlclient-dev
```

Alternatively, you can choose to install a precompiled database driver. For Debian and Debian-derived flavors of Linux this is available as `python-mysqldb`.