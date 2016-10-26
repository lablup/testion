import asyncio
import subprocess
from collections import namedtuple, OrderedDict as odict
import contextlib
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid

import github3
import pygit2

TestResult = namedtuple('TestResult', 'state num_tests num_passes num_fails')


def parse_test_result(output, parser='unittest'):
    if output is None:
        return None
    if parser == 'unittest':
        m = re.search(r'Ran (\d+) test', output)
        if not m:
            return None
        num_tests = int(m.group(1))
        m = re.search(r'FAILED \(([^\)]*)\)', output)
        num_fails = 0
        if m:
            fail_msg = m.group(1)
            # There are two kinds of error: failures and errors.
            m = re.search(r'failures?=(\d+)', fail_msg)
            num_fails += int(m.group(1)) if m else 0
            m = re.search(r'errors?=(\d+)', fail_msg)
            num_fails += int(m.group(1)) if m else 0
        num_passes = num_tests - num_fails
        state = 'success' if num_fails == 0 else 'failure'
        return TestResult(state, num_tests, num_passes, num_fails)
    elif parser == 'pytest':
        m = re.search(r'==== (' +
                      r'((?P<fails>\d+) failed)?' +
                      r'(, )?' +
                      r'((?P<passes>\d+) passed)?' +
                      r') in ([\d.])+ seconds? ====', output)
        if not m:
            return None
        num_fails = int(m.group('fails')) if m.group('fails') else 0
        num_passes = int(m.group('passes')) if m.group('passes') else 0
        num_tests = num_fails + num_passes
        state = 'success' if num_fails == 0 else 'failure'
        return TestResult(state, num_tests, num_passes, num_fails)
    else:
        raise ValueError('Invalid test result parser type.')

def summarize_result(test_result) -> (str, str):
    '''
    Summarize the result and return (title, summary) messages as strings.
    It is useful to construct human-friendly descriptions for test results.
    '''
    if test_result is None:
        return 'Ough!', 'No test results.'
    success_ratio = test_result.num_passes / test_result.num_tests
    if test_result.num_fails == 0:
        return 'Success!', 'All {} tests OK.'.format(test_result.num_tests)
    return 'Failed!', '{0:.1f}% ({1.num_passes} / {1.num_tests}) passed' \
           .format(success_ratio * 100, test_result)

@contextlib.contextmanager
def noop_context():
    yield


class TestReporterBase:

    context = 'ci/testion/test'
    test_type = 'test'
    runner_ctxmgr = noop_context

    def __init__(self, config, report, data):

        self.loop = asyncio.get_event_loop()

        self.config = config
        self.report = report

        self.gh_user = os.environ['GH_USERNAME']
        self.gh_token = os.environ['GH_TOKEN']

        self.target_user = data['repository']['owner']['name']
        self.target_repo = data['repository']['name']
        self.data = data

        # Set the log file name
        here = Path(__file__).parent
        test_date = datetime.today().strftime("%Y%m%d")
        test_time = datetime.now().strftime("%H%M%S")
        test_id = uuid.uuid4().hex
        log_fname = "{}-{}-{}.txt".format(self.test_type, test_time, test_id)

        # Set paths to store logs
        if 'log_path' in config:
            log_path = Path(config['log_path']) / test_date
        else:
            log_path = here.parent.parent / 'logs' / test_date
        log_path.mkdir(parents=True, exist_ok=True)
        self.log_file = str(log_path / log_fname)
        self.s3_dest  = "s3://lablup-testion/{}/{}/{}/{}" \
                        .format(test_date, self.target_user, self.target_repo, log_fname)
        self.log_link = "https://s3.ap-northeast-2.amazonaws.com/lablup-testion/{}/{}/{}/{}" \
                        .format(test_date, self.target_user, self.target_repo, log_fname)

        # Set up the file logger only used for this test run.
        # (Its output will be propagated to the root logger as well, though.)
        self.logger = logging.getLogger('testion.TestRun.{}'.format(test_id))
        self.logfile_handler = logging.FileHandler(self.log_file)
        self.logfile_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(self.logfile_handler)

        # Github & repo objects
        self.remote_gh   = github3.login(self.gh_user, self.gh_token)
        self.remote_repo = self.remote_gh.repository(self.target_user, self.target_repo)

    async def run_command(self, cmd, cwd=None, venv=None, env=None, verbose=False):
        composed_env = {k: v for k, v in os.environ.items() if k != 'PYTHONHOME'}
        if env:
            composed_env.update(env)
        if venv:
            composed_env['VIRTUAL_ENV'] = venv
            composed_env['PATH'] = '{}:{}'.format(Path(venv) / 'bin', composed_env['PATH'])
        p = await asyncio.create_subprocess_shell(
            cmd,
            env=composed_env,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT  # stderr is merged with stdout
        )
        stdout, _ = await p.communicate()
        if stdout is not None:
            stdout = stdout.decode().strip()
        if verbose:
            self.logger.info('>>> {}'.format(cmd))
            printed_stdout = stdout + ('' if stdout is not None and stdout.endswith('\n') else '\n')
            self.logger.info('---\n{}---'.format(printed_stdout))
        return stdout

    async def _mark_status(self, state, test_result=None, msg=''):
        target_url = None
        if state == 'pending':
            desc = msg
        elif state in ('error', 'success', 'failure'):
            target_url = self.log_link
            if test_result is not None:
                assert test_result.state == state
            _, desc = summarize_result(test_result)
        else:
            self.logger.error("Invalid status state: {}".format(state))
            return
        await self.mark_status(state, desc, target_url)

    async def mark_status(self, state, desc, target_url):
        '''
        Report the progress of the currently running test suite.
        If your reporter works in a per-commit basis,
        this is where to annotate commits in your VCS.
        Otherwise, you may just leave it as an empty method
        by not overriding it.
        '''
        pass

    def add_result(self, case_name, ref, test_result):
        '''
        Store the given test result (may be None) in the format(s) you want.
        test_result may be None.
        '''
        pass

    async def flush_results(self):
        '''
        Make a final report from the stored test results and send it.
        '''
        pass

    async def run(self):
        await self._mark_status('pending', msg='Preparing tests...')
        self.logger.info("Start testing procedure at {} ...".format(datetime.now()))

        with tempfile.TemporaryDirectory() as wcdir, tempfile.TemporaryDirectory() as venvdir:
            await self._mark_status('pending', msg='Running tests...')

            # Clone the repository.
            creds = pygit2.UserPass(self.gh_user, self.gh_token)
            callbacks = pygit2.RemoteCallbacks(credentials=creds)
            repo_url = self.data['repository']['clone_url']
            self.local_repo = pygit2.clone_repository(repo_url, wcdir,
                                                      callbacks=callbacks)

            # Create a virtualenv.
            if 'envs' in self.report:
                env = odict(e.split('=', 1) for e in self.report['envs'])
            else:
                env = None
            await self.run_command('python -m venv {}'.format(venvdir), env=env)
            await self.run_command('pip install -U pip wheel setuptools', venv=venvdir, env=env)
            await self.run_command('pip install pytest nose', venv=venvdir, env=env)

            # Run install_cmd if set.
            if 'install_cmd' in self.report:
                output = await self.run_command(self.report['install_cmd'],
                                       venv=venvdir, env=env, cwd=wcdir,
                                       verbose=True)

            case_idx = -1
            for case_idx, ref in enumerate(self.generate_target_refs()):

                co_strategy = pygit2.GIT_CHECKOUT_FORCE \
                              | pygit2.GIT_CHECKOUT_REMOVE_UNTRACKED
                commit = self.local_repo.revparse_single(ref)
                self.local_repo.checkout_tree(commit.tree, strategy=co_strategy)
                msg = 'Checked out to {}'.format(self.local_repo.head.target.hex[:7])
                if not self.local_repo.head_is_detached:
                    self.branch = self.local_repo.head.shorthand
                    case_name = "branch '{}' ({})".format(self.branch, commit.hex[:7])
                    msg += " (branch '{}')".format(self.branch)
                else:
                    self.branch = None
                    case_name = "commit {}".format(commit.hex[:7])
                    msg += " (detached)"
                self.logger.info(msg)

                with type(self).runner_ctxmgr():
                    self.logger.info('=== Test[{}] started at {} ===' \
                                     .format(case_idx, datetime.now()))
                    output = await self.run_command(self.report['test_cmd'],
                                                    venv=venvdir, env=env,
                                                    cwd=wcdir,
                                                    verbose=True)
                    self.logger.info('=== Test[{}] finished at {} ===' \
                                     .format(case_idx, datetime.now()))

                test_result = parse_test_result(output, self.report['parser'])
                if test_result is not None:
                    await self._mark_status(test_result.state, test_result)
                else:
                    await self._mark_status('error', None)
                self.add_result(case_name, ref, test_result)

            if case_idx == -1:
                self.logger.info('No test commands executed.')
                await self._mark_status('success', None)

            self.local_repo = None
            self.logger.info("Finished at {}\n".format(datetime.now()))
            self.logger.removeHandler(self.logfile_handler)
            await self.flush_results()

    def get_recently_updated_branches(self):
        """
        Find all branches which have new commits within last 24 hours.
        """
        assert self.local_repo is not None
        # Since we have just cloned the repo recently (at the beginning of test),
        # we don't have to fetch again here.
        branches = []
        branch_heads = set()  # to skip identical (merged or local==remote) branches
        all_branches = self.local_repo.listall_branches(pygit2.GIT_BRANCH_LOCAL |
                                                        pygit2.GIT_BRANCH_REMOTE)
        now = time.time()  # in UTC
        for branch in all_branches:
            if branch.endswith('/HEAD'):
                continue
            has_recent_commits = False
            branch_head = self.local_repo.revparse_single(branch)
            for commit in self.local_repo.walk(branch_head.hex, pygit2.GIT_SORT_TIME):
                if commit.commit_time < now - 86400:
                    break
                else:
                    has_recent_commits = True
            if has_recent_commits and branch_head.hex not in branch_heads:
                branches.append(branch)
                branch_heads.add(branch_head.hex)
        self.logger.info('Non-identical branches with new commits within last 24 hours:\n' +
                         '\n'.join(' - {}'.format(name) for name in branches))
        return branches

    def generate_target_refs(self):
        if self.report['branches'] == '!HEAD':
            yield from [self.data['after']]
        elif self.report['branches'] == '!OUTSTANDING':
            yield from self.get_recently_updated_branches()
        else:
            assert isinstance(self.report['branches'], (list, tuple))
            yield from self.report['branches']
