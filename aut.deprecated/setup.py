#! /usr/bin/python
# Copyright (c) 2011 by cisco Systems, Inc.
# All rights reserved.

"""
 Installation script for accelerated upgrade
"""
import codecs
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

from au.version import __version__

VERSION = __version__
DESCRIPTION = 'Accelerated Upgrade tool for Cisco Devices'
with codecs.open('README.rst', 'r', encoding='UTF-8') as readme:
    LONG_DESCRIPTION = ''.join(readme)

CLASSIFIERS = [
    'Programming Language :: Python',
    'Programming Language :: Python :: 2.7',
]

packages = [
    'au',
    'au.lib',
    'au.utils',
    'au.plugins',
    'au.workqueue',
    'au.condor',
    'au.condor.controllers',
    'au.condor.controllers.protocols',
    'au.condor.platforms',
]

NAME = 'accelerated_upgrade'

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    author='Cisco Systems',
    author_email='[at] cisco.com',
    url='https://sourceforge.net/p/acceleratedupgrade',
    platforms=['any'],
    packages=packages,
    install_requires=['pexpect>=3.1', ],
    classifiers=CLASSIFIERS,
    entry_points={
            'console_scripts': [
                'accelerated_upgrade = au.main:main'
            ],
    },
    zip_safe=False
)
