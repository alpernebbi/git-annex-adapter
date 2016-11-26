#!/usr/bin/env python3

import os
import codecs
import setuptools

root = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(root, 'README.rst'), encoding='utf-8') as f:
    readme = f.read()

setuptools.setup(
    name='git-annex-adapter',
    version='0.1.0',
    description='Call git-annex commands from Python',
    long_description=readme,
    url='https://github.com/alpernebbi/git-annex-adapter',
    author='Alper Nebi Yasak',
    author_email='alpernebiyasak@gmail.com',
    license='GPL3+',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='git-annex metadata',
    py_modules=['git_annex_adapter'],
)