#!/usr/bin/env python
from distutils.core import setup
import os

long_desc = ''

try:
    long_desc = os.path.join(os.path.dirname(__file__), 'README.rst').read()
except:
    # The description isn't worth a failed install...
    pass

setup(
    name='walker',
    version='0.1.0',
    description='Walker - walk urls and generate code coverage for PHP code',
    long_description=long_desc,
    author='Oleg Fedoseev',
    author_email='oleg.fedoseev@me.com',
    url='http://github.com/aryoh/walker/',
    py_modules=['walker'],
    license='http://www.apache.org/licenses/LICENSE-2.0',
    classifiers=[],
)