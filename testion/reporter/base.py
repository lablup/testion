import asyncio
from asyncio import subprocess
from collections import namedtuple
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import tempfile

import github3
import pygit2


TestResult = namedtuple('TestResult', 'num_tests num_success num_fails')


def parse_test_result(output):
    if output is None:
        return None
    m = re.search(r'Ran ([0-9]+) tests', output)
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

    # Github
    target_user = "lablup"
    target_repo = "neumann"


    def __init__(self, ev_type, data):
        self.gh_user = os.environ['GH_USERNAME']
        self.gh_token = os.environ['GH_TOKEN']

        # Set the log file name
        here = Path(__file__).parent
        test_date = datetime.today().strftime("%Y%m%d")
        if self.test_type == "functional_test":
            suffix = datetime.now().strftime("%H:%M:%S")
        else:
            suffix = self.sha
        log_fname = "{0}-{1}.txt".format(self.test_type, suffix)

        # Set paths to store logs
        log_path = here.parent / 'log' / test_date
        log_path.mkdir(parents=True, exist_ok=True)
        self.log_file = str(log_path / log_fname)
        self.s3_dest  = "s3://lablup-testion/{}/{}".format(test_date, log_fname)
        self.log_link = "https://s3.ap-northeast-2.amazonaws.com/lablup-testion/{}/{}" \
                        .format(test_date, log_fname)

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
        p = asyncio.create_subprocess_shell(
            cmd, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        stdout, _ = p.communicate()
        stdout = stdout.decode()
        if verbose:  # stderr is merged with stdout
            self.logger.info(stdout)
        return stdout.strip()

    def _mark_status(self, state, test_result=None, preparing=False):
        target_url = None
        if state == 'pending':
            if preparing:
                desc = "Preparing tests..."
            else:
                desc = "Running tests..."
        elif state in ('error', 'success', 'failure'):
            target_url = self.log_link
            _, desc = summarize_result(test_result)
        else:
            self.logger.error("Invalid status state: {}".format(state))
            return
        self.mark_status(state, desc, target_url)

    def mark_status(self, state, desc, target_url):
        '''
        Report the progress of the currently running test suite.
        If your reporter works in a per-commit basis,
        this is where to annotate commits in your VCS.
        Otherwise, you may just leave it as an empty method
        by not overriding it.
        '''
        pass

    def add_result(self, case_name, test_result):
        '''
        Store the given test result (may be None) in the format(s) you want.
        test_result may be None.
        '''
        pass

    def flush_results(self):
        '''
        Make a final report from the stored test results and send it.
        '''
        pass

    async def run(self, cmd):
        self._mark_status('pending', preparing=True)
        self.logger.info("Start testing procedure at {} ...".format(datetime.now()))

        with tempfile.TemporaryDirectory() as tmpdir:

            creds = pygit2.UserPass(self.gh_user, self.gh_token)
            callbacks = pygit2.RemoteCallbacks(credentials=creds)
            repo_url = 'https://github.com/{}/{}.git' \
                       .format(self.target_user, self.target_repo)
            self.local_repo = pygit2.clone_repository(repo_url, tmpdir,
                                                      callbacks=callbacks)

            for case_name, ref, cmd in self.test_commands(tmpdir):

                self.local_repo.checkout(ref)
                msg = 'Checked out to {}'.format(self.head.target[:7])
                if not self.local_repo.head_is_detached:
                    self.branch = self.local_repo.head.shorthand
                    msg += " (branch '{}')".format(self.branch)
                else:
                    self.branch = None
                    msg += " (detached)".format(self.branch)
                self.logger.info(msg)
                os.chdir(tmpdir)

                self.logger.info('=== Test started at {} ==='.format(datetime.now()))
                output = await self.run_command(cmd, verbose=True)
                self.logger.info('=== Test finished at {} ==='.format(datetime.now()))

                test_result = parse_test_result(output)
                if "Error:" in output:
                    self._mark_status('error', test_result)
                elif "FAIL:" in output:
                    self._mark_status('failure', test_result)
                else:
                    self._mark_status('success', test_result)
                self.add_result(test_result)

            # TODO: handle when there is no test cases

        self.local_repo = None
        self.logger.info("Finished at {}\n".format(datetime.now()))
        self.flush_results()

    def test_commands(self, tmpdir):
        '''
        The main method to override.
        It should yield a tuple of the human-readable case name, the refspec that git can fetch, and the command to run a test suite.
        You may return as many tuples as you want for multiple test suites (e.g., tests per each branch).
        '''
        raise NotImplementedError
