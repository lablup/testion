import contextlib
import logging
import subprocess
import sys
import time

import pygit2

from .base import TestReporterBase
from .mixins import SlackReportMixin, GHIssueCommentMixin, S3LogUploadMixin


def pid_of(name):
    try:
        pid = subprocess.run(['pidof', name], check=True, stdout=subprocess.PIPE).stdout.decode()
        return str(int(pid))
    except subprocess.CalledProcessError:
        return None


@contextlib.contextmanager
def selenium_server():
    log = logging.getLogger('testion.helpers.selenium_server')

    # Start Xvfb and Selenium server.
    log.info("Xvfb started")
    subprocess.run("Xvfb :0 -screen 0 1440x900x16 -ac 2>&1 > /dev/null &", shell=True)
    log.info("Selenium server started")
    subprocess.run("java -jar /home/jpark/selenium-server-standalone-2.53.0.jar -port 8080 –maxSession 1 &",
        shell=True)

    yield

    # Kill Xvfb process
    pid = pid_of("Xvfb")
    if pid:
        log.info("Xvfb terminated")
        subprocess.run("kill {}".format(pid), shell=True)

    # Kill java (Selenium server) process
    pid = pid_of("java")
    if pid:
        subprocess.run("kill {}".format(pid), shell=True)
        log.info("Selenium server terminated")


class SeleniumFunctionalTestReporter(
        S3LogUploadMixin, SlackReportMixin, GHIssueCommentMixin,
        TestReporterBase):

    context = 'ci/testion/functional-test'
    test_type = 'functional_test'

    gh_issue_num = 466
    runner_ctxmgr = selenium_server
