import functools
import subprocess
import os
import json
import collections.abc
from argparse import Namespace

from datetime import datetime
from datetime import tzinfo

import pytz


class GitRepo:
    def __init__(self, path):
        self.path = path
        self._git = RepeatedProcess('git', workdir=self.path)

        if not os.path.isdir(self.path):
            print("Creating directory {}".format(self.path))
            os.makedirs(self.path)

        if not os.path.isdir(os.path.join(self.path, '.git')):
            print("Initializing git repo at {}".format(self.path))
            self._git('init')

        if 'master' not in self.branches:
            self.checkout('master')
            self.commit('Initialize repo', allow_empty=True)

    @property
    def status(self):
        return self._git('status', '-s')

    @property
    def branches(self):
        branch_list = []
        current_exists = False
        for branch in self._git('branch', '--list').splitlines():
            if branch[0] == '*':
                branch_list.insert(0, branch[2:])
                current_exists = True
            else:
                branch_list.append(branch[2:])
        if branch_list and not current_exists:
            raise RuntimeError(
                'No current branch found among: \n'
                '    {}\n    in {}'.format(branch_list, self.path))
        return tuple(branch_list)

    def add(self, path):
        return self._git('add', path)

    def rm(self, path):
        return self._git('rm', '-rf', path)

    def checkout(self, branch, new_branch=True):
        command = ['checkout', branch]
        if new_branch and branch not in self.branches:
            command.insert(1, '-b')
        return self._git(*command)

    def commit(self, message, add=True, allow_empty=False):
        command = ['commit', '-m', message]
        if add: command.append('-a')
        if allow_empty: command.append('--allow-empty')
        return self._git(*command)

    def cherry_pick(self, branch):
        return self._git("cherry-pick", branch)

    def stash(self, pop=False):
        command = ['stash']
        if pop: command.append('pop')
        return self._git(*command)

    @property
    def tree_hash(self):
        commit = self._git('cat-file', 'commit', 'HEAD').split()
        return commit[commit.index('tree') + 1]

    def __repr__(self):
        return 'GitRepo(path={!r})'.format(self.path)


class GitAnnexRepo(GitRepo):
    def __init__(self, path):
        super().__init__(path)
        self.annex = GitAnnex(self)

    @classmethod
    def make_annex(cls, repo):
        repo.annex = GitAnnex(repo)
        repo.__class__ = cls

    def __repr__(self):
        return 'GitAnnexRepo(path={!r})'.format(self.path)


class GitAnnex(collections.abc.Mapping):
    def __init__(self, repo):
        self.repo = repo
        self._annex = RepeatedProcess(
            'git', 'annex',
            workdir=repo.path
        )

        if not os.path.isdir(os.path.join(repo.path, '.git', 'annex')):
            print("Initializing git-annex at {}".format(repo.path))
            self._annex('init', 'albumin')

        self.processes = Namespace()
        batch_processes = {
            'metadata': ('metadata', '--batch', '--json'),
            'calckey': ('calckey', '--batch'),
            'lookupkey': ('lookupkey', '--batch'),
            'contentlocation': ('contentlocation', '--batch')
        }

        for proc, cmd in batch_processes.items():
            vars(self.processes)[proc] = BatchProcess(
                'git', 'annex', *cmd, workdir=repo.path
            )

    def import_(self, path, duplicate=True):
        if os.path.basename(path) in os.listdir(self.repo.path):
            raise ValueError('Import path basename conflict')
        command = ['import', path]
        if duplicate: command.append('--duplicate')
        return self._annex(*command)

    def calckey(self, file_path):
        return self.processes.calckey(file_path)

    def fromkey(self, key, file_path):
        return self._annex('fromkey', key, file_path)

    def lookupkey(self, file_path):
        return self.processes.lookupkey(file_path)

    def locate(self, key, absolute=False):
        rel_path = self.processes.contentlocation(key)
        if absolute:
            return os.path.join(self.repo.path, rel_path)
        else:
            return rel_path

    def metadata(self, all_keys=False):
        try:
            jsons = self._annex(
                'metadata', '--json', ('--all' if all_keys else '')
            ).splitlines()
            metadata = [json.loads(json_) for json_ in jsons]
            return metadata
        except subprocess.CalledProcessError as err:
            return []

    def keys(self, absent=False):
        all_meta = self.metadata(all_keys=True)
        all_keys = {meta['key'] for meta in all_meta}
        if absent:
            file_meta = self.metadata()
            file_keys = {meta['key'] for meta in file_meta}
            return all_keys - file_keys
        else:
            return all_keys

    def files(self):
        file_meta = self.metadata()
        return {meta['file'] for meta in file_meta}

    def __getitem__(self, key):
        return GitAnnexMetadata(self, key)

    def __contains__(self, key):
        return key in self.keys

    def __iter__(self):
        yield from self.keys

    def __len__(self):
        return len(self.keys)

    def __repr__(self):
        return 'GitAnnex(repo={!r})'.format(self.repo)


class GitAnnexMetadata(collections.abc.MutableMapping):
    def __init__(self, annex, key):
        self.key = key
        self.annex = annex

    def _query(self, **fields):
        return self.annex.processes.metadata(
            key=self.key, fields=fields
        )['fields']

    def datetime_format(self, values):
        for v in values:
            if isinstance(v, datetime):
                v_utc = v.astimezone(pytz.utc)
                dt_str = v_utc.strftime('%Y-%m-%d@%H-%M-%S')
                values.remove(v)
                values.add(dt_str)
        return values

    def datetime_parse(self, values, timezone=None):
        if not timezone:
            timezone = self['timezone']
        if not timezone:
            timezone = pytz.utc
        for v in values:
            try:
                dt_obj = datetime.strptime(v, '%Y-%m-%d@%H-%M-%S')
                dt_utc = pytz.utc.localize(dt_obj)
                dt_local = dt_utc.astimezone(timezone)
                values.remove(v)
                values.add(dt_local)
            except (ValueError, TypeError):
                continue
        return values

    def timezone_parse(self, values):
        for v in values:
            try:
                tz = pytz.timezone(v)
                values.remove(v)
                values.add(tz)
            except:
                continue
        return values

    def timezone_format(self, values):
        for v in values:
            if isinstance(v, tzinfo):
                tzname = v.tzname(None)
                values.remove(v)
                values.add(tzname)
        return values

    def __getitem__(self, meta_key):
        fields = self._query()
        values = fields.get(meta_key, [])
        return_value = set(values)

        if meta_key == 'datetime':
            try:
                timezone = pytz.timezone(fields['timezone'])
            except:
                timezone = None
            self.datetime_parse(return_value, timezone=timezone)
        elif meta_key.endswith('lastchanged'):
            self.datetime_parse(return_value, timezone=pytz.utc)
        elif meta_key == 'timezone':
            self.timezone_parse(return_value)

        if len(return_value) == 1:
            return return_value.pop()
        else:
            return return_value

    def __setitem__(self, meta_key, value):
        if meta_key.endswith('lastchanged'):
            raise KeyError(meta_key)

        if not isinstance(value, set):
            value = {value}

        if meta_key == 'datetime':
            self.datetime_format(value)
        elif meta_key == 'timezone':
            self.timezone_format(value)

        fields = self._query(**{meta_key:list(value)})
        if meta_key == 'datetime':
            y, m, d = fields[meta_key][0].split('@')[0].split('-')
            self._query(year=y, month=m, day=d)

    def __delitem__(self, meta_key):
        self._query(**{meta_key: []})

    def __contains__(self, meta_key):
        return meta_key in self._query()

    def __iter__(self):
        for field in self._query().keys():
            if not field.endswith('lastchanged'):
                yield field

    def __len__(self):
        len([x for x in self])

    def __repr__(self):
        repr_ = 'GitAnnexFileMetadata(key={!r}, path={!r})'
        return repr_.format(self.key, self.annex.repo.path)


class RepeatedProcess:
    def __init__(self, *prefix_command, workdir=None):
        self._prefix = prefix_command
        self._workdir = workdir

    def __call__(self, *commands):
        return subprocess.check_output(
            (*self._prefix, *commands),
            universal_newlines=True,
            cwd=self._workdir,
        )


class BatchProcess:
    def __init__(self, *batch_command, workdir=None):
        self._command = batch_command
        self._workdir = workdir
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

        query = query_line or json.dumps(query_object)
        print(*query, file=self._process.stdin, flush=True)
        response = self._process.stdout.readline().strip()
        return response if query_line else json.loads(response)
