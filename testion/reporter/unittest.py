from .base import TestReporterBase
from .mixins import SlackReportMixin, S3LogUploadMixin


class UnitTestReporter(S3LogUploadMixin, SlackReportMixin, TestReporterBase):

    context = 'ci/testion/unit-test'
    test_type = 'unit_test'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sha       = self.data['after']
        self.short_sha = self.sha[:7]

    async def mark_status(self, state, desc, target_url):
        if not self.remote_repo:
            return
        result = self.remote_repo.create_status(
            sha=self.sha, state=state,
            description=desc,
            context=self.context,
            target_url=target_url
        )
        if result:
            msg = "Marked '{0}' status for commit {1}".format(state, self.short_sha)
            self.logger.info(msg)
        else:
            msg = "Error on creating status for commit {}".format(self.short_sha)
            self.logger.error(msg)

