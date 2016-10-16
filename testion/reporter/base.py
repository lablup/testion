import asyncio
from asyncio import subprocess
from collections import namedtuple
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import tempfile
import uuid

import github3
import pygit2


TestResult = namedtuple('TestResult', 'num_tests num_success num_fails')

_entrance_lock = None


class EntranceLock():

    def __init__(self, concurrency=1, loop=None):
        self.concurrency = concurrency
        self.count = 0
        self.loop = loop if loop else asyncio.get_event_loop()
        self.cond = asyncio.Condition(loop=loop)

    class _AContext:

        def __init__(self, elock, pending_cb):
            self.elock = elock
            self.pending_cb = pending_cb

        async def __aenter__(self):
            await self.elock.cond.acquire()
            while self.elock.count == self.elock.concurrency:
                await self.elock.conf.wait()
                if self.elock.count == self.elock.concurrency and self.pending_cb:
                    await self.pending_cb()
            self.elock.count += 1
            self.elock.cond.release()

        async def __aexit__(self, exc_type, exc_value, tb):
            await self.elock.cond.acquire()
            self.elock.count -= 1
            self.elock.cond.notify()
            self.elock.cond.release()

    def lock(self, pending_cb=None):
        return type(self)._AContext(self, pending_cb)

    @staticmethod
    def init_global(concurrency, loop=None):
        global _entrance_lock
        if _entrance_lock is None:
            _entrance_lock = EntranceLock(concurrency, loop)


def parse_test_result(output):
    if output is None:
        return None
    m = re.search(r'Ran ([0-9]+) tests?', output)
    if not m:
        return None
    num_tests = int(m.group(1))
    m = re.search(r'FAILED \(errors=([0-9]+)\)', output)
    num_fails = int(m.group(1)) if m else 0
    num_success = num_tests - num_fails
    return TestResult(num_tests, num_success, num_fails)

def summarize_result(test_result) -> (str, str):
    '''
    Summarize the result and return (title, summary) messages as strings.
    It is useful to construct human-friendly descriptions for test results.
    '''
    if test_result is None:
        return 'Ough!', 'No test results.'
    success_ratio = test_result.num_success / test_result.num_tests
    if test_result.num_fails == 0:
        return 'Success!', 'All {} tests OK.'.format(test_result.num_tests)
    return 'Failed!', '{0:.1f}% ({1.num_success} / {1.num_tests}) passed' \
           .format(success_ratio * 100, test_result)


class TestReporterBase:

    context = 'ci/testion/test'
    test_type = 'test'

    def __init__(self, ev_type, data):

        self.loop = asyncio.get_event_loop()

        self.gh_user = os.environ['GH_USERNAME']
        self.gh_token = os.environ['GH_TOKEN']

        self.target_user = data['repository']['owner']['name']
        self.target_repo = data['repository']['name']

        # Set the log file name
        here = Path(__file__).parent
        test_date = datetime.today().strftime("%Y%m%d")
        test_time = datetime.now().strftime("%H%M%S")
        test_id = uuid.uuid4().hex
        log_fname = "{}-{}-{}.txt".format(self.test_type, test_time, test_id)

        # Set paths to store logs
        log_path = here.parent / 'log' / test_date
        log_path.mkdir(parents=True, exist_ok=True)
        self.log_file = str(log_path / log_fname)
        self.s3_dest  = "s3://lablup-testion/{}/{}/{}/{}" \
                        .format(test_date, self.target_user, self.target_repo, log_fname)
        self.log_link = "https://s3.ap-northeast-2.amazonaws.com/lablup-testion/{}/{}/{}/{}" \
                        .format(test_date, self.target_user, self.target_repo, log_fname)

        # Set up the logger
        logger = logging.getLogger(self.test_type)
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(self.log_file)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)
        self.logger = logger

        # Github & repo objects
        self.remote_gh   = github3.login(self.gh_user, self.gh_token)
        self.remote_repo = self.remote_gh.repository(self.target_user, self.target_repo)

    async def run_command(self, cmd, verbose=False):
        p = await asyncio.create_subprocess_shell(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT  # stderr is merged with stdout
        )
        stdout, _ = await p.communicate()
        stdout = stdout.decode()
        if verbose:
            self.logger.info('>>> {}'.format(cmd))
            printed_stdout = stdout + '' if stdout.endswith('\n') else '\n'
            self.logger.info('---\n{}---'.format(printed_stdout))
        return stdout.strip()

    async def _mark_status(self, state, test_result=None, msg=''):
        target_url = None
        if state == 'pending':
            desc = msg
        elif state in ('error', 'success', 'failure'):
            target_url = self.log_link
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

        async def pending_cb():
            await self._mark_Status('pending', msg='Waiting for other tests to finish...')

        async with _entrance_lock.lock(pending_cb):
            with tempfile.TemporaryDirectory() as tmpdir:
                await self._mark_status('pending', msg='Running tests...')

                os.chdir(tmpdir)

                # Clone the repository.
                creds = pygit2.UserPass(self.gh_user, self.gh_token)
                callbacks = pygit2.RemoteCallbacks(credentials=creds)
                repo_url = 'https://github.com/{}/{}.git' \
                           .format(self.target_user, self.target_repo)
                self.local_repo = pygit2.clone_repository(repo_url, tmpdir,
                                                          callbacks=callbacks)

                case_idx = -1
                for case_idx, (case_name, ref, cmd) in enumerate(self.test_commands(tmpdir)):

                    co_strategy = pygit2.GIT_CHECKOUT_FORCE \
                                  | pygit2.GIT_CHECKOUT_REMOVE_UNTRACKED
                    commit = self.local_repo.revparse_single(ref)
                    self.local_repo.checkout_tree(commit.tree, strategy=co_strategy)
                    msg = 'Checked out to {}'.format(self.local_repo.head.target.hex[:7])
                    if not self.local_repo.head_is_detached:
                        self.branch = self.local_repo.head.shorthand
                        msg += " (branch '{}')".format(self.branch)
                    else:
                        self.branch = None
                        msg += " (detached)".format(self.branch)
                    self.logger.info(msg)

                    self.logger.info('=== Test[{}] started at {} ===' \
                                     .format(case_idx, datetime.now()))
                    output = await self.run_command(cmd, verbose=True)
                    self.logger.info('=== Test[{}] finished at {} ===' \
                                     .format(case_idx, datetime.now()))

                    test_result = parse_test_result(output)
                    if "Error:" in output:
                        await self._mark_status('error', test_result)
                    elif "FAIL:" in output:
                        await self._mark_status('failure', test_result)
                    else:
                        await self._mark_status('success', test_result)
                    self.add_result(case_name, ref, test_result)

                if case_idx == -1:
                    self.logger.info('No test commands executed.')
                    await self._mark_status('success', None)

                self.local_repo = None
                self.logger.info("Finished at {}\n".format(datetime.now()))
                await self.flush_results()

    def test_commands(self, tmpdir):
        '''
        The main method to override.
        It should yield a tuple of the human-readable case name, the refspec that git can fetch, and the command to run a test suite.
        You may return as many tuples as you want for multiple test suites (e.g., tests per each branch).
        '''
        raise NotImplementedError
