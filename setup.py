#!/usr/bin/env python3

# Git-Annex-Adapter Setup
# Copyright (C) 2016 Alper Nebi Yasak
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import os
import codecs
import setuptools

root = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(root, 'README.rst'), encoding='utf-8') as f:
    readme = f.read()

setuptools.setup(
    name='git-annex-adapter',
    version='0.2.1',
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
    packages=['git_annex_adapter'],
    install_requires=['pygit2'],
)
