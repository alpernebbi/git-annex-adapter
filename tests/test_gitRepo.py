from unittest import TestCase
from tests.utils import with_temp_repo
from tests.utils import with_tar_repo


class TestGitRepo(TestCase):
    @with_temp_repo
    def test_git(self, repo):
        repo._git('--version')

    @with_temp_repo
    def test_git_status(self, repo):
        assert not repo.status

    @with_temp_repo
    def test_git_commit(self, repo):
        repo.commit('Test commit', allow_empty=True)

    @with_tar_repo('repo-initial-commit.tar.gz')
    def test_git_from_tar_1(self, repo):
        assert repo.tree_hash == \
               '4b825dc642cb6eb9a060e54bf8d69288fbee4904'

    @with_tar_repo('repo-empty.tar.gz')
    def test_git_from_tar_2(self, repo):
        assert repo.branches == ('master',)

    @with_tar_repo('repo-three-branches-a.tar.gz')
    def test_git_branches_1(self, repo):
        assert repo.branches == \
               ('a', 'master', 'x')

    @with_tar_repo('repo-three-branches-m.tar.gz')
    def test_git_branches_2(self, repo):
        assert repo.branches == \
               ('master', 'a', 'x')

    @with_tar_repo('repo-three-branches-x.tar.gz')
    def test_git_branches_3(self, repo):
        assert repo.branches == \
               ('x', 'a', 'master')

    @with_tar_repo('repo-three-branches-m.tar.gz')
    def test_git_checkout(self, repo):
        assert repo.branches == \
               ('master', 'a', 'x')

        repo.checkout('a')
        assert repo.branches == \
               ('a', 'master', 'x')

        repo.checkout('x')
        assert repo.branches == \
               ('x', 'a', 'master')

        repo.checkout('n')
        assert repo.branches == \
               ('n', 'a', 'master', 'x')

    @with_tar_repo('repo-detached-head.tar.gz')
    def test_git_detached_head(self, repo):
        assert repo.branches == \
               ('(HEAD detached at ae034d5)', 'master')

    @with_tar_repo('repo-two-files-extend.tar.gz')
    def test_git_cherry_pick(self, repo):
        repo.checkout('895131e', new_branch=False)
        repo.checkout('alt')
        repo.cherry_pick('678ff80')
        assert repo.tree_hash == \
            '9af9706879aba9cbfc7e8f70e8fe87c20d6678db'

    @with_tar_repo('repo-two-half-files-extend.tar.gz')
    def test_git_stash(self, repo):
        assert repo.status
        repo.stash()
        assert not repo.status
        repo.checkout('master')
        repo.cherry_pick('e21989f')
        repo.stash(pop=True)
        repo.commit('extend file c')
        assert repo.tree_hash == \
            '149cb6cb6b7ffa7508ce5b4936f307de2acdbe17'