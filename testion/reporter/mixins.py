import json
import os

import github3
import requests

from .base import summarize_result


class SlackReportMixin:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slack_items = []
        self.slack_hook_url = os.environ.get('TESTION_SLACK_HOOK_URL', None)

    def add_result(self, case_name, ref, test_result):
        super().add_result(case_name, ref, test_result)

        if case_name.startswith('branch '):
            gh_url = 'https://github.com/{}/{}/commits/{}' \
                     .format(self.target_user, self.target_repo, ref)
        else:
            gh_url = 'https://github.com/{}/{}/commit/{}' \
                     .format(self.target_user, self.target_repo, ref)
        title, summary = summarize_result(test_result)
        desc = '`<{}|{}>`: {}'.format(gh_url, case_name.capitalize(), summary)

        if test_result is None:
            color = 'danger'
        else:
            success_ratio = test_result.num_passes / test_result.num_tests
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

    async def flush_results(self):
        await super().flush_results()

        if self.slack_hook_url:
            self.logger.info('Flushing test result reports for Slack...')
            text = '[{}/{}] We have <{}|a new {} report>.' \
                   .format(self.target_user, self.target_repo,
                           self.log_link, self.test_type.replace('_', ' '))
            if not self.slack_items:
                # when there is no test commands given...
                self.slack_items.append({
                    'color': '#e8e8e8',
                    'title': 'Empty result.',
                    'text': 'No tests have been executed.',
                })
            r = requests.post(self.slack_hook_url, data=json.dumps({
                'text': text,
                'attachments': self.slack_items,
            }))
            # ignore the request result

        self.slack_items.clear()


class GHIssueCommentMixin:

    gh_issue_num = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.comment_items = []
        assert self.gh_issue_num is not None
        if not hasattr(self, 'remote_gh') or self.remote_gh is None:
            self.remote_gh = github3.login(user, token)
            self.remote_repo = self.remote_gh.repository(self.target_user,
                                                         self.target_repo)

    def add_result(self, case_name, ref, test_result):
        super().add_result(case_name, ref, test_result)
        _, summary = summarize_result(test_result)
        desc = '{}: {}'.format(case_name.capitalize(), summary)
        self.comment_items.append(desc)

    async def flush_results(self):
        await super().flush_results()

        if self.remote_repo:
            desc = self.test_type.upper() + ':\n' + '\n'.join(self.comment_items)
            issue = self.remote_repo.issue(issue_num)
            if issue:  # When there is a corresponding issue
                cmt = issue.create_comment(desc)
                if cmt:
                    self.logger.info('Error comment posted on issue #{}'.format(issue_num))
                else:
                    self.logger.error('Error on posting comment')

        self.comment_items.clear()


class S3LogUploadMixin:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aws_available = 'AWS_ACCESS_KEY_ID' in os.environ

    async def flush_results(self):
        await super().flush_results()

        if self.aws_available:
            cmd = "aws s3 cp {0} {1}".format(self.log_file, self.s3_dest)
            await self.run_command(cmd, verbose=True)
