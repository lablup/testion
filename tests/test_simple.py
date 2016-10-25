import asyncio
import json
import os
from pathlib import Path
from unittest import mock

import github3
import pytest

rootdir = Path(__file__).resolve().parent.parent

common_data = {
    'after': '31bbcd1a2067f8bb8cdcc71ae8abf566f25c41af',
    'repository': {
        'full_name': 'lablup/testion-test',
        'owner': {
            'name': 'lablup',
        },
        'name': 'testion-test',
        'clone_url': 'https://github.com/lablup/testion-test',
    },
}


@pytest.yield_fixture
def github_mock():
    o = mock.patch('github3.login')
    with o:
        yield o

@pytest.yield_fixture
def requests_mock():
    o = mock.patch('requests.post')
    with o:
        yield o

@pytest.yield_fixture
def aws_mock():
    o = mock.patch('testion.reporter.mixins.S3LogUploadMixin')
    with o:
        yield o

@pytest.yield_fixture
def env_mock():
    o = mock.patch.dict('os.environ', {
        'GH_USERNAME': 'dummy-user',
        'GH_TOKEN': 'dummy-password',
        'AWS_ACCESS_KEY_ID': 'MyPreciousKey',
        'AWS_SECRET_ACCESS_KEY': 'MyPreciousSecret',
        'AWS_DEFAULT_REGION': 'ap-northeast-2',
    })
    with o:
        yield o

async def test_setup(create_app_and_client):
    app, client = await create_app_and_client()

async def test_unittest_mixed(capsys, create_app_and_client,
                              github_mock, requests_mock,
                              aws_mock, env_mock):
    app, client = await create_app_and_client()
    with capsys.disabled():
        resp = await client.post(
            '/webhook?report=unit-mixed',
            headers={'X-GitHub-Event': 'push'},
            data=json.dumps(common_data)
        )
        assert resp.status == 204
        resp.close()
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[0]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'pending'
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[-1]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'failure'
        assert '(2 / 4) passed' in kwargs['description']
        assert kwargs['context'] == 'ci/testion/unit-test'

async def test_unittest_success(capsys, create_app_and_client,
                                github_mock, requests_mock,
                                aws_mock, env_mock):
    app, client = await create_app_and_client()
    with capsys.disabled():
        resp = await client.post(
            '/webhook?report=unit-success',
            headers={'X-GitHub-Event': 'push'},
            data=json.dumps(common_data)
        )
        assert resp.status == 204
        resp.close()
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[0]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'pending'
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[-1]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'success'
        assert 'All 2 tests OK' in kwargs['description']
        assert kwargs['context'] == 'ci/testion/unit-test'

async def test_unittest_failure(capsys, create_app_and_client,
                                github_mock, requests_mock,
                                aws_mock, env_mock):
    app, client = await create_app_and_client()
    with capsys.disabled():
        resp = await client.post(
            '/webhook?report=unit-failure',
            headers={'X-GitHub-Event': 'push'},
            data=json.dumps(common_data)
        )
        assert resp.status == 204
        resp.close()
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[0]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'pending'
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[-1]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'failure'
        assert '(0 / 1) passed' in kwargs['description']
        assert kwargs['context'] == 'ci/testion/unit-test'

async def test_unittest_errors(capsys, create_app_and_client,
                               github_mock, requests_mock,
                               aws_mock, env_mock):
    app, client = await create_app_and_client()
    with capsys.disabled():
        resp = await client.post(
            '/webhook?report=unit-errors',
            headers={'X-GitHub-Event': 'push'},
            data=json.dumps(common_data)
        )
        assert resp.status == 204
        resp.close()
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[0]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'pending'
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[-1]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'failure'
        assert '(0 / 1) passed' in kwargs['description']
        assert kwargs['context'] == 'ci/testion/unit-test'

async def test_pytest_mixed(capsys, create_app_and_client,
                            github_mock, requests_mock,
                            aws_mock, env_mock):
    app, client = await create_app_and_client()
    with capsys.disabled():
        resp = await client.post(
            '/webhook?report=pytest-mixed',
            headers={'X-GitHub-Event': 'push'},
            data=json.dumps(common_data)
        )
        assert resp.status == 204
        resp.close()
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[0]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'pending'
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[-1]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'failure'
        assert '(2 / 4) passed' in kwargs['description']
        assert kwargs['context'] == 'ci/testion/unit-test'

async def test_pytest_success(capsys, create_app_and_client,
                              github_mock, requests_mock,
                              aws_mock, env_mock):
    app, client = await create_app_and_client()
    with capsys.disabled():
        resp = await client.post(
            '/webhook?report=pytest-success',
            headers={'X-GitHub-Event': 'push'},
            data=json.dumps(common_data)
        )
        assert resp.status == 204
        resp.close()
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[0]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'pending'
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[-1]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'success'
        assert 'All 2 tests OK' in kwargs['description']
        assert kwargs['context'] == 'ci/testion/unit-test'

async def test_pytest_failure(capsys, create_app_and_client,
                              github_mock, requests_mock,
                              aws_mock, env_mock):
    app, client = await create_app_and_client()
    with capsys.disabled():
        resp = await client.post(
            '/webhook?report=pytest-failure',
            headers={'X-GitHub-Event': 'push'},
            data=json.dumps(common_data)
        )
        assert resp.status == 204
        resp.close()
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[0]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'pending'
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[-1]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'failure'
        assert '(0 / 1) passed' in kwargs['description']
        assert kwargs['context'] == 'ci/testion/unit-test'

async def test_pytest_errors(capsys, create_app_and_client,
                             github_mock, requests_mock,
                             aws_mock, env_mock):
    app, client = await create_app_and_client()
    with capsys.disabled():
        resp = await client.post(
            '/webhook?report=pytest-errors',
            headers={'X-GitHub-Event': 'push'},
            data=json.dumps(common_data)
        )
        assert resp.status == 204
        resp.close()
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[0]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'pending'
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[-1]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'failure'
        assert '(0 / 1) passed' in kwargs['description']
        assert kwargs['context'] == 'ci/testion/unit-test'


async def test_unit_mixed_branch(capsys, create_app_and_client,
                                 github_mock, requests_mock,
                                 aws_mock, env_mock):
    app, client = await create_app_and_client()
    with capsys.disabled():
        resp = await client.post(
            '/webhook?report=unit-mixed-branch',
            headers={'X-GitHub-Event': 'push'},
            data=json.dumps(common_data)
        )
        assert resp.status == 204
        resp.close()
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[0]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'pending'
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[-1]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'failure'
        assert '(2 / 4) passed' in kwargs['description']
        assert kwargs['context'] == 'ci/testion/unit-test'

async def test_pytest_mixed_branch(capsys, create_app_and_client,
                                   github_mock, requests_mock,
                                   aws_mock, env_mock):
    app, client = await create_app_and_client()
    with capsys.disabled():
        resp = await client.post(
            '/webhook?report=pytest-mixed-branch',
            headers={'X-GitHub-Event': 'push'},
            data=json.dumps(common_data)
        )
        assert resp.status == 204
        resp.close()
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[0]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'pending'
        args, kwargs = app._last_reporter.remote_repo.create_status.call_args_list[-1]
        assert kwargs['sha'] == common_data['after']
        assert kwargs['state'] == 'failure'
        assert '(2 / 4) passed' in kwargs['description']
        assert kwargs['context'] == 'ci/testion/unit-test'

