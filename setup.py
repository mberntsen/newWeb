"""newWeb installer."""

import os
import re
from setuptools import setup, find_packages

REQUIREMENTS = [
    'decorator',
    'mysql-python',
    'python-magic',
    'python-openid',
    'pytz',
    'simplejson',
]


def description():
  with file(os.path.join(os.path.dirname(__file__), 'README.md')) as r_file:
    return r_file.read()


def version():
  main_lib = os.path.join(os.path.dirname(__file__), 'newweb', '__init__.py')
  with file(main_lib) as v_file:
    return re.match(".*__version__ = '(.*?)'", v_file.read(), re.S).group(1)


setup(
    name='newWeb',
    version=version(),
    description='A fork to bring uWeb closer to WSGI and proper design',
    long_description=description(),
    license='ISC',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Operating System :: POSIX :: Linux',
    ],
    author='Elmer de Looff',
    author_email='elmer.delooff@gmail.com',
    url='https://github.com/edelooff/newWeb',
    keywords='minimal web framework',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=REQUIREMENTS)
