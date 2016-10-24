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

dummy_env = {
    'GH_USERNAME': 'dummy-user',
    'GH_TOKEN': 'dummy-password',
}


@pytest.fixture
def dummy_github():
    return mock.patch('github3.login')


async def test_setup(create_app_and_client):
    app, client = await create_app_and_client()


async def test_unittest_mixed(capsys, create_app_and_client, dummy_github):
    app, client = await create_app_and_client()
    with capsys.disabled(), mock.patch.dict('os.environ', dummy_env), dummy_github:
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

async def test_unittest_success(capsys, create_app_and_client, dummy_github):
    app, client = await create_app_and_client()
    with capsys.disabled(), mock.patch.dict('os.environ', dummy_env), dummy_github:
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

async def test_unittest_failure(capsys, create_app_and_client, dummy_github):
    app, client = await create_app_and_client()
    with capsys.disabled(), mock.patch.dict('os.environ', dummy_env), dummy_github:
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

async def test_unittest_errors(capsys, create_app_and_client, dummy_github):
    app, client = await create_app_and_client()
    with capsys.disabled(), mock.patch.dict('os.environ', dummy_env), dummy_github:
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

async def test_pytest_mixed(capsys, create_app_and_client, dummy_github):
    app, client = await create_app_and_client()
    with capsys.disabled(), mock.patch.dict('os.environ', dummy_env), dummy_github:
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

async def test_pytest_success(capsys, create_app_and_client, dummy_github):
    app, client = await create_app_and_client()
    with capsys.disabled(), mock.patch.dict('os.environ', dummy_env), dummy_github:
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

async def test_pytest_failure(capsys, create_app_and_client, dummy_github):
    app, client = await create_app_and_client()
    with capsys.disabled(), mock.patch.dict('os.environ', dummy_env), dummy_github:
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

async def test_pytest_errors(capsys, create_app_and_client, dummy_github):
    app, client = await create_app_and_client()
    with capsys.disabled(), mock.patch.dict('os.environ', dummy_env), dummy_github:
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


async def test_unit_mixed_branch(capsys, create_app_and_client, dummy_github):
    app, client = await create_app_and_client()
    with capsys.disabled(), mock.patch.dict('os.environ', dummy_env), dummy_github:
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

async def test_pytest_mixed_branch(capsys, create_app_and_client, dummy_github):
    app, client = await create_app_and_client()
    with capsys.disabled(), mock.patch.dict('os.environ', dummy_env), dummy_github:
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

