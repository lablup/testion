import json
import os

import aiohttp
import github3
import requests

from .base import summarize_result

class SlackReportMixin:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slack_items = []
        self.slack_hook_url = os.environ.get('TESTION_SLACK_HOOK_URL', None)
    
    def add_result(self, test_result):
        super().add_result(test_result)

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

    def flush_results(self):
        super().flush_results()

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


class GHIssueCommentMixin:

    gh_issue_num = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, 'gh') or self.gh is None:
            self.gh = github3.login(user, token)
            self.repo = self.gh.repository(self.target_user, self.target_repo)

    def flush_results(self, test_result):
        super().flush_results()

        if self.gh_issue_num is None:
            return

        # Render error message
        _, desc = summarize_result(test_result)

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


class S3LogUploadMixin:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aws_available = 'AWS_ACCESS_KEY_ID' in os.environ

    def flush_results(self):
        super().flush_results()

        if self.aws_available:
            self.run_command(
                "aws s3 cp {0} {1}".format(self.log_file, self.s3_dest),
                verbose=True)
        else:
            print('Skipping log upload to S3 since AWS credentials are not configured.', file=sys.stderr)
