import sys

from .base import TestReporterBase
from .mixins import SlackReportMixin, GHIssueCommentMixin, S3LogUploadMixin


def pid_of(name):
    try:
        pid = subprocess.run(['pidof', name], check=True, stdout=subprocess.PIPE).stdout.decode()
        return str(int(pid))
    except subprocess.CalledProcessError:
        return None


class FunctionalTestReporter(
        SlackReportMixin, GHIssueCommentMixin, S3LogUploadMixin,
        TestReporterBase):

    context = 'ci/testion/functional-test'
    test_type = 'functional_test'

    gh_issue_num = 466

    def __init__(self, ev_type, data):
        super().__init__(ev_type, data)

    def get_test_branches(self):
        """
        Get list of branches which have commits from yesterday
        """
        test_branches = set()

        # Find all branches which have commits yesterday
        commits, stderr = self.run_command("git rev-list HEAD --all --after='yesterday'")
        for commit in commits.split():
            branches, stdout = self.run_command("git branch --contains {} --sort=-committerdate".format(commit))
            for branch in branches.split():
                if branch != "*":
                    test_branches.add(branch)
                    break

        return list(test_branches)

    def prepare_selenium_server(self):
        self.logger.info("Xvfb started")
        run("Xvfb :0 -screen 0 1440x900x16 -ac 2>&1 > /dev/null &", shell=True)
        self.logger.info("Selenium server started")
        run("java -jar /home/jpark/selenium-server-standalone-2.53.0.jar -port 8080 –maxSession 1 &",
            shell=True)

    def terminate_selenium_server(self):
        # Kill Xvfb process
        pid = pid_of("Xvfb")
        if pid:
            self.logger.info("Xvfb terminated")
            run("kill {}".format(pid), shell=True)

        # Kill java (selenium server) process
        pid = pid_of("java")
        if pid:
            run("kill {}".format(pid), shell=True)
            self.logger.info("Selenium server terminated")

    def test_commands(self):
        # Get all branches which have commits yesterday
        test_branches = self.get_test_branches()
        self.logger.info('Branches which have commits yesterday:\n' +
                         '\n'.join(' - {}'.format(name) for name in test_branches))
        new_branch = self.branch
        try:
            self.prepare_selenium_server()

            # Run tests for each target branches
            for branch in test_branches:
                new_branch = self.checkout_to_branch(branch)
                if branch != new_branch:
                    continue  # did not change branch (stash and stash pop needed?)
                self.branch = new_branch

                cmd = sys.executable + " manage.py test --noinput functional_tests"
                yield 'branch {}'.format(new_branch), cmd

        finally:
            self.terminate_selenium_server()

