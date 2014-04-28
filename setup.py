#!/usr/bin/python

# Standard modules
import os
from setuptools import setup, find_packages

HERE = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(HERE, 'README.md')).read()

requires = [
    'decorator',
    'lockfile',
    'mysql-python',
    'python-magic',
    'python-openid',
    'pytz',
    'simplejson',
]

setup(
    name='uWeb',
    version='0.3.0',
    description='Underdark\'s minimal web-framework',
    long_description=README,
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
    scripts=['uweb/scripts/uweb'],
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,
)
