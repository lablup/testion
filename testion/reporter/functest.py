import contextlib
import subprocess
import sys
import time

from .base import TestReporterBase
from .mixins import SlackReportMixin, GHIssueCommentMixin, S3LogUploadMixin


def pid_of(name):
    try:
        pid = subprocess.run(['pidof', name], check=True, stdout=subprocess.PIPE).stdout.decode()
        return str(int(pid))
    except subprocess.CalledProcessError:
        return None


@contextlib.contextmanager
def selenium_server(logger):

    # Start Xvfb and Selenium server.
    logger.info("Xvfb started")
    subprocess.run("Xvfb :0 -screen 0 1440x900x16 -ac 2>&1 > /dev/null &", shell=True)
    logger.info("Selenium server started")
    subprocess.run("java -jar /home/jpark/selenium-server-standalone-2.53.0.jar -port 8080 –maxSession 1 &",
        shell=True)

    yield

    # Kill Xvfb process
    pid = pid_of("Xvfb")
    if pid:
        logger.info("Xvfb terminated")
        subprocess.run("kill {}".format(pid), shell=True)

    # Kill java (Selenium server) process
    pid = pid_of("java")
    if pid:
        subprocess.run("kill {}".format(pid), shell=True)
        logger.info("Selenium server terminated")


class SeleniumFunctionalTestReporter(
        S3LogUploadMixin, SlackReportMixin, GHIssueCommentMixin,
        TestReporterBase):

    context = 'ci/testion/functional-test'
    test_type = 'functional_test'

    gh_issue_num = 466

    def __init__(self, ev_type, data):
        super().__init__(ev_type, data)

    def get_recently_updated_branches(self):
        """
        Find all branches which have commits from yesterday.
        """
        assert self.local_repo is not None
        branches = []

        all_branches = self.local_repo.listall_branches()
        now = time.time()  # TODO: timezone check?
        for branch in all_branches:
            branch_head = self.local_repo.revparse_single(branch)
            for commit in self.local_repo.walk(branch_head.hex, pygit2.GIT_SORT_TIME):
                if commit.commit_time >= now - 86400:
                    branches.append(branch)
                    break
        return branches

    def test_commands(self, tmpdir):
        test_branches = self.get_recently_updated_branches()
        self.logger.info('Branches which have commits yesterday:\n' +
                         '\n'.join(' - {}'.format(name) for name in test_branches))
        for branch in test_branches:
            with selenium_server(self.logger):
                cmd = sys.executable + " manage.py test --noinput functional_tests"
                yield 'branch {}'.format(branch), branch, cmd

