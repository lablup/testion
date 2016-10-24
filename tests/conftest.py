import asyncio
import contextlib
import gc
from pathlib import Path
import socket
import ssl

import aiohttp
from aiohttp import web
import pytest
import uvloop
import yaml

from testion.server import github_webhook
from testion.reporter.base import EntranceLock


@contextlib.contextmanager
def loop_context(loop=None):
    current_scope = False
    if not loop:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        current_scope = True

    yield loop

    if current_scope:
        if not loop.is_closed():
            loop.call_soon(loop.stop)
            loop.run_forever()
            loop.close()
        gc.collect()
        asyncio.set_event_loop(None)

def pytest_pycollect_makeitem(collector, name, obj):
    # Patch pytest for coroutines
    if collector.funcnamefilter(name) and asyncio.iscoroutinefunction(obj):
        return list(collector._genfunctions(name, obj))

def pytest_pyfunc_call(pyfuncitem):
    # Patch pytest for coroutines.
    if asyncio.iscoroutinefunction(pyfuncitem.function):
        existing_loop = pyfuncitem.funcargs.get('loop', None)
        with loop_context(existing_loop) as loop:
            testargs = {arg: pyfuncitem.funcargs[arg]
                        for arg in pyfuncitem._fixtureinfo.argnames}
            task = loop.create_task(pyfuncitem.obj(**testargs))
            loop.run_until_complete(task)
        return True

@pytest.fixture
def unused_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

@pytest.yield_fixture
def loop():
    with loop_context() as loop:
        yield loop

@pytest.fixture
def root():
    return Path(__file__).resolve().parent.parent

@pytest.yield_fixture
def create_server(loop, unused_port, root):
    app = handler = server = None

    async def create(debug=False):
        nonlocal app, handler, server
        app = web.Application(loop=loop)
        app.config = yaml.load((root / 'config.sample.yml').read_text())
        app.config['service_port'] = unused_port
        app.sslctx = None
        app.router.add_post('/webhook', github_webhook)
        EntranceLock.init_global(1, loop)
        handler = app.make_handler(debug=debug, keep_alive_on=False)
        server = await loop.create_server(handler,
                                          '127.0.0.1',
                                          app.config['service_port'])
        return app, app.config['service_port']

    yield create

    async def finish():
        server.close()
        await server.wait_closed()
        await app.shutdown()
        await handler.finish_connections()
        await app.cleanup()
    loop.run_until_complete(finish())


class Client:
    def __init__(self, session, url):
        self._session = session
        self._url = url

    def close(self):
        self._session.close()

    def post(self, path, **kwargs):
        while path.startswith('/'):
            path = path[1:]
        url = self._url + path
        if 'params' in kwargs:
            params = kwargs['params']
            del kwargs['params']
        else:
            params = {}
        params['blocking'] = '1'
        return self._session.post(url, params=params, **kwargs)


@pytest.yield_fixture
def create_app_and_client(loop, create_server):
    client = None

    async def maker():
        nonlocal client
        server_params = {}
        client_params = {}
        app, port = await create_server(**server_params)
        if app.sslctx:
            url = 'https://localhost:{}/'.format(port)
            client_params['connector'] = aiohttp.TCPConnector(verify_ssl=False)
        else:
            url = 'http://localhost:{}/'.format(port)
        client = Client(aiohttp.ClientSession(loop=loop, **client_params), url)
        return app, client

    yield maker

    if client:
        client.close()
