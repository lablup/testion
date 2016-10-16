import argparse
import asyncio
import json
import traceback

import aiohttp
from aiohttp import web
import uvloop

from .exceptions import UnsupportedEventError
from .reporter.base import EntranceLock
from .reporter.unittest import UnitTestReporter
from .reporter.functest import SeleniumFunctionalTestReporter


reporter_map = {
    'unit': UnitTestReporter,
    'slfunc': SeleniumFunctionalTestReporter,
}


async def github_webhook(request):
    try:
        reporter_cls = reporter_map[request.GET['report_type']]
    except KeyError:
        return web.Response(status=400, text='Invalid or missing test reporter type.')

    ev_type = request.headers.get('X-GitHub-Event', 'push')
    try:
        data = await request.json()
    except json.decoder.JSONDecodeError:
        return web.Response(status=400, text='Invalid JSON.')

    try:
        reporter = reporter_cls(ev_type, data)
        await reporter.run()
    except UnsupportedEventError:
        return web.Response(status=400, text='Unsupported GitHub event type.')
    except Exception as e:
        return web.Response(status=500, text=traceback.format_exc())
    return web.Response(status=204)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=9092)
    args = parser.parse_args()

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    EntranceLock.init_global(1, loop)
    app = web.Application()
    app.router.add_post('/webhook', github_webhook)
    try:
        web.run_app(app, port=args.port)
    except (KeyboardInterrupt, SystemExit):
        loop.stop()
    finally:
        loop.close()
        print('terminated.')
