import sys

from ..exceptions import UnsupportedEventError
from .base import TestReporterBase


class UnitTestReporter(TestReporterBase):

    context = 'ci/testion/unit-test'
    test_type = 'unit_test'

    def __init__(self, ev_type, data):
        if ev_type != 'push':
            raise UnsupportedEventError
        super().__init__(ev_type, data)

    def test_commands(self):
        case_name = 'commit {}'.format(self.short_sha)
        cmd = sys.executable + ' manage.py test --noinput ' \
              + '`ls -d */ | egrep -v "^functional_tests/"`'
        yield case_name, cmd

