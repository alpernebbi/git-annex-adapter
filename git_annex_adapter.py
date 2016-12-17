# Git-Annex-Adapter
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

import functools
import subprocess
import os
import json
import collections.abc
from argparse import Namespace


class GitAnnex(collections.abc.Mapping):
    @staticmethod
    def init_path(path, description=None):
        git = RepeatedProcess('git', workdir=path)
        annex = RepeatedProcess('git', 'annex', workdir=path)

        if not os.path.isdir(path):
            print("Creating directory {}".format(path))
            os.makedirs(path)

        if not os.path.isdir(os.path.join(path, '.git')):
            print("Initializing git repo at {}".format(path))
            git('init')

        if 'master' not in git('branch', '--list'):
            git('checkout', '-b', 'master')
            git('commit', '-m', 'Initialize repo', '--allow-empty')

        if not os.path.isdir(os.path.join(path, '.git', 'annex')):
            print("Initializing git-annex at {}".format(path))
            annex('init', description if description else '')

    def __init__(self, path, create=False):
        if create:
            self.init_path(path)

        self.path = path
        self._annex = RepeatedProcess(
            'git', 'annex',
            workdir=self.path
        )

        self._annex('metadata', '--key', 'SHA256E-s0--0')

        self.processes = Namespace()
        batch_processes = {
            'metadata': ('metadata', '--batch', '--json'),
            'calckey': ('calckey', '--batch'),
            'lookupkey': ('lookupkey', '--batch'),
            'contentlocation': ('contentlocation', '--batch'),
            'fromkey': ('fromkey',),
        }
        silent_processes = ['fromkey']

        for proc, cmd in batch_processes.items():
            vars(self.processes)[proc] = BatchProcess(
                'git', 'annex', *cmd,
                workdir=self.path,
                silent=(proc in silent_processes)
            )

        self._meta_cache = [None, None]

    def import_(self, path, duplicate=True):
        if os.path.basename(path) in os.listdir(self.path):
            raise ValueError('Import path basename conflict')
        command = ['import', path]
        if duplicate: command.append('--duplicate')
        return self._annex(*command)

    def calckey(self, file_path):
        return self.processes.calckey(file_path)

    def fromkey(self, key, file_path):
        return self.processes.fromkey(key, file_path)

    def lookupkey(self, file_path):
        return self.processes.lookupkey(file_path)

    def locate(self, key, absolute=False):
        rel_path = self.processes.contentlocation(key)
        if absolute:
            return os.path.join(self.path, rel_path)
        else:
            return rel_path

    def clear_metadata_cache(self):
        self._meta_cache = [None, None]

    def metadata(self, all_keys=False, cached=False):
        if cached and self._meta_cache[all_keys]:
            return self._meta_cache[all_keys]

        try:
            jsons = self._annex(
                'metadata', '--json', ('--all' if all_keys else '')
            ).splitlines()
            metadata = [json.loads(json_) for json_ in jsons]
            self._meta_cache[all_keys] = metadata
            return metadata
        except subprocess.CalledProcessError as err:
            self._meta_cache = [None, None]
            return []

    def keys(self, absent=False, cached=False):
        all_meta = self.metadata(all_keys=True, cached=cached)
        all_keys = {meta['key'] for meta in all_meta}
        if absent:
            file_meta = self.metadata(cached=cached)
            file_keys = {meta['key'] for meta in file_meta}
            return all_keys - file_keys
        else:
            return all_keys

    def files(self, cached=False):
        file_meta = self.metadata(cached=cached)
        return {meta['file'] for meta in file_meta}

    def fields(self, cached=False):
        metadata = self.metadata(all_keys=True, cached=cached)
        fields = [meta.get('fields', {}) for meta in metadata]
        return filter(
            lambda f: not f.endswith('lastchanged'),
            set.union(*map(set, fields + [{}]))
        )

    def __getitem__(self, map_key):
        if map_key in self.files(cached=True):
            key, file = self.lookupkey(map_key), map_key

        elif map_key in self.keys(cached=True):
            key, file = map_key, None

        else:
            raise KeyError(map_key)

        return GitAnnexMetadata(self, key=key, file=file)

    def __contains__(self, map_key):
        return map_key in self.keys(cached=True)

    def __iter__(self):
        yield from self.keys(cached=True)

    def __len__(self):
        return len(self.keys(cached=True))

    def __repr__(self):
        return 'GitAnnex(path={!r})'.format(self.path)


class GitAnnexMetadata(collections.abc.MutableMapping):
    def __init__(self, annex, key, file=None):
        self.key = key
        self.file = file
        self.annex = annex
        self.query = functools.partial(
            self.annex.processes.metadata, key=self.key
        )
        self.fields_cache = None

    def fields(self, **fields):
        if self.fields_cache and not fields:
            return self.fields_cache

        new_fields = self.query(fields=fields).get('fields', {})

        for field, value in fields.items():
            new_value = new_fields.get(field, [])
            if set(new_value) != set(value):
                self.annex.processes.metadata.restart()
                new_fields = self.query(fields=fields).get('fields', {})
                break
        else:
            self.fields_cache = new_fields
            return new_fields

        for field, value in fields.items():
            new_value = new_fields.get(field, [])
            if set(new_value) != set(value):
                self.fields_cache = None
                raise KeyError(field)
        else:
            self.fields_cache = new_fields
            return new_fields

    def locate(self, absolute=False):
        rel_path = self.annex.processes.contentlocation(self.key)
        if absolute:
            return os.path.join(self.annex.path, rel_path)
        else:
            return rel_path

    def __getitem__(self, meta_key):
        if meta_key == 'key':
            return [self.key]
        if meta_key == 'file':
            return [self.file]
        values = self.fields().get(meta_key, [])
        return values

    def __setitem__(self, meta_key, value):
        if meta_key not in ['key', 'file']:
            self.fields(**{meta_key: value})

    def __delitem__(self, meta_key):
        self.fields(**{meta_key: []})

    def __contains__(self, meta_key):
        return meta_key in self.fields()

    def __iter__(self):
        for field in self.fields().keys():
            if not field.endswith('lastchanged'):
                yield field

    def __len__(self):
        return len([x for x in self])

    def __repr__(self):
        repr_ = 'GitAnnexMetadata(key={!r}, path={!r})'
        return repr_.format(self.key, self.annex.path)


class RepeatedProcess:
    def __init__(self, *prefix_command, workdir=None):
        self._prefix = prefix_command
        self._workdir = workdir

    def __call__(self, *commands):
        return subprocess.check_output(
            (*self._prefix, *commands),
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=self._workdir,
        )

    def __repr__(self):
        repr_ = 'RepeatedProcess(prefix={!r}, workdir={!r})'
        return repr_.format(self._prefix, self._workdir)


class BatchProcess:
    def __init__(self, *batch_command, workdir=None, silent=False):
        self._command = batch_command
        self._workdir = workdir
        self._silent = silent
        self._process = self.start()

    def start(self):
        process = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=self._workdir,
        )
        return process

    def running(self):
        return self._process and self._process.poll() is None

    def terminate(self, kill=False):
        self._process.terminate()
        try:
            self._process.wait(5)
        except subprocess.TimeoutExpired:
            if kill:
                self._process.kill()
            else:
                raise

    def restart(self):
        if self.running():
            self.terminate()
        self._process = self.start()

    def __call__(self, *query_line, **query_object):
        while not self.running():
            self._process = self.start()

        query = " ".join(query_line) or json.dumps(query_object)
        print(query, file=self._process.stdin, flush=True)
        if not self._silent:
            response = self._process.stdout.readline().strip()
            return response if query_line else json.loads(response)

    def __repr__(self):
        repr_ = 'BatchProcess(cmd={!r}, cwd={!r}, process={!r})'
        return repr_.format(self._command, self._workdir, self._process)

