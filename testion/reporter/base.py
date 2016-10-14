from collections import namedtuple
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import requests
import sys
import subprocess

import github3


TestResult = namedtuple('TestResult', 'num_tests num_success num_fails')


def parse_test_result(output):
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
    '''
    if test_result is None:
        return 'Ough!', 'No test results.'
    success_ratio = test_result.num_success / test_result.num_tests
    if test_result.num_fails == 0:
        return 'Success!', 'All {} tests OK.'.format(test_result.num_tests)
    return 'Failed!', '{:.1f}% passed ({} failures)'.format(success_ratio * 100, test_result.num_fails)


class TestReporterBase:

    context = 'ci/testion/test'
    test_type = 'test'

    # Github
    target_user = "lablup"
    target_repo = "neumann"


    def __init__(self):
        user = os.environ['GH_USERNAME']
        token = os.environ['GH_TOKEN']

        # Check if we can run awscli without problems.
        self.aws_available = 'AWS_ACCESS_KEY_ID' in os.environ

        # Commit & branch information
        if self.test_type == "unit_test":
            self.sha = self.get_latest_commit_sha()
            self.short_sha = self.get_latest_commit_sha(short=True)
            self.branch = self.get_latest_commit_branch()

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
        self.slack_hook_url = os.environ.get('TESTION_SLACK_HOOK_URL', None)

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
        self.gh = github3.login(user, token)
        self.repo = self.gh.repository(self.target_user, self.target_repo)

        # Slack notification items
        self.slack_items = []

    def run_command(self, cmd, verbose=False):
        p = subprocess.run(cmd, shell=True,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT if verbose else subprocess.PIPE)
        stdout = p.stdout.decode("utf-8") if p.stdout else ''
        stderr = p.stderr.decode("utf-8") if p.stderr else ''
        if verbose:  # stderr is merged with stdout
            self.logger.info(stdout)
        return stdout, stderr

    def get_latest_commit_sha(self, short=False):
        extra_arg = ' --abbrev-commit' if short else ''
        sha, _ = self.run_command("git rev-list HEAD -1" + extra_arg)
        return sha.strip()

    def get_latest_commit_branch(self):
        sha = self.get_latest_commit_sha()
        cmd = "git branch --contains {} --sort=-committerdate".format(sha)
        branches, _ = self.run_command(cmd)

        # If multiple branches have the commit (in this case, merge occurred),
        # return the first branch. The branch list is sorted by committerdate, so
        # the first branch in the list is where the merge occurred.
        for branch in branches.strip().split():
            if branch != "*":
                return branch
        return "master"

    def checkout_to_branch(self, name):
        self.logger.info("Checking out to '{}' branch".format(name))
        self.run_command("git checkout {}".format(name), verbose=True)

        branch, _ = self.run_command("git branch | grep \* | cut -d ' ' -f2")
        branch = branch.strip()
        self.logger.info("On branch '{}'".format(branch))

        return branch

    def comment_issue(self, issue_num, test_result, err_prefix=''):
        # Render error message
        _, summary = summarize_result(test_result)
        desc = err_prefix + summary

        # Get issue for functional test logging
        if self.repo:
            issue = self.repo.issue(issue_num)
            if issue:  # When there is a corresponding issue
                cmt = issue.create_comment(desc)
                if cmt:
                    self.logger.info('Error comment posted on issue #{}'.format(issue_num))
                else:
                    self.logger.error('Error on posting comment')
            else:  # When there is no such issue or it is closed
                self.logger.error('Missing issue (#{})! Skipping error reports there...'.format(issue_num))

    def add_slack_result(self, test_result):
        if self.test_type == 'functional_test':
            gh_branch_url = 'https://github.com/{}/{}/commits/{}'.format(self.target_user, self.target_repo, self.branch)
            desc = 'On branch `<{}|{}>`: '.format(gh_branch_url, self.branch)
        else:
            gh_commit_url = 'https://github.com/{}/{}/commit/{}'.format(self.target_user, self.target_repo, self.sha)
            desc = 'On commit `<{}|{}@{}>`: '.format(gh_commit_url, self.branch, self.short_sha)
        title, summary = summarize_result(test_result)
        desc += summary
        if test_result is None:
            color = 'danger'
        else:
            success_ratio = test_result.num_success / test_result.num_tests
            if success_ratio > 0.999:
                color = 'good'
            elif success_ratio > 0.9:
                color = 'warning'
            else:
                color = 'danger'
        self.slack_items.append({
            'color': color,
            'title': title,
            'text': desc,
            'mrkdwn_in': ['text'],
        })

    def add_slack_custom(self, title, desc, color=None):
        self.slack_items.append({
            'color': color,
            'title': title,
            'text': desc,
            'mrkdwn_in': ['text'],
        })

    def flush_slack_results(self):
        if self.slack_hook_url:
            self.logger.info('Flushing test result reports for Slack...')
            text = 'We have a new {} report (<{}|complete logs here>).' \
                   .format(self.test_type.replace('_', ' '), self.log_link)
            r = requests.post(self.slack_hook_url, data=json.dumps({
                'text': text,
                'attachments': self.slack_items,
            }))
            r.raise_for_status()
        self.slack_items.clear()

    def mark_status(self, state, test_result=None, preparing=False):
        # Set description text
        if state == 'pending':
            if preparing:
                desc = "Preparing tests..."
            else:
                desc = "Running tests on branch {}...".format(self.branch)
        elif state in ('error', 'success', 'failure'):
            _, desc = summarize_result(test_result)
        else:
            self.logger.error("Invalid status state: {}".format(state))
            return

        # Set the details URL
        target_url = self.log_link if state != "pending" else None

        # Create status for current commit
        if self.repo:
            result = self.repo.create_status(
                sha=self.sha, state=state, description=desc,
                context=self.context, target_url=target_url
            )
            if result:
                self.logger.info("Marked '{0}' status for commit {1}".format(state, self.sha))
            else:
                self.logger.error("Error on creating status for commit {}".format(self.sha))

    def upload_log(self):
        if self.aws_available:
            self.run_command(
                "aws s3 cp {0} {1}".format(self.log_file, self.s3_dest),
                verbose=True)
        else:
            print('Skipping log upload to S3 since AWS credentials are not configured.', file=sys.stderr)

    async def run(self, cmd):
        self.mark_status('pending', preparing=True)
        self.logger.info("Start testing procedure at {} ...".format(datetime.now()))

        # Checkout to the branch where the latest commit is pushed
        if self.branch not in ["master", "", None]:
            self.branch = self.checkout_to_branch(self.branch)

        # Run tests
        for case_name, cmd in self.test_commands():
            self.logger.info('Running tests at {}...'.format(datetime.now()))
            output, _ = self.run_command(cmd, verbose=True)
            self.logger.info('Test finished at {}'.format(datetime.now()))

            # Checkout back to master branch always
            if self.branch != "master":
                self.checkout_to_branch("master")

            test_result = parse_test_result(output)
            if "Error:" in output:
                self.mark_status('error', test_result)
            elif "FAIL:" in output:
                self.mark_status('failure', test_result)
            else:
                self.mark_status('success', test_result)

            # Add reports.
            # TODO: self.comment_issue(466, test_result, err_prefix="FUNCTIONAL_TEST:\n")
            self.add_slack_result(test_result)

        if new_branch != "master":
            self.checkout_to_branch("master")
        self.logger.info("Finished at {}\n".format(datetime.now()))

        self.flush_slack_results()
        self.upload_log()


    def test_commands(self):
        '''
        The main method to override.
        '''
        raise NotImplementedError
