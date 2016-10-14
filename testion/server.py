import asyncio
import json

import aiohttp
from aiohttp import web
import uvloop

from .exceptions import UnsupportedEventError
from .reporter.unittest import UnitTestReporter
from .reporter.functest import SeleniumFunctionalTestReporter


reporter_map = {
    'unit': UnitTestReporter,
    'slfunc': SeleniumFunctionalTestReporter,
}


async def github_webhook(request):
    user_name = request.match_info['user']
    repo_name = request.match_info['repo']
    try:
        reporter_cls = reporter_map[request.GET['report_type']]
    except KeyError:
        return web.Response(status=400, text='Invalid or missing test reporter type.')

    ev_type = request.headers.get('X-GitHub-Event', 'push')
    try:
        data = await request.json()
    except json.decoder.JSONDecodeError:
        return web.Response(status=400, text='Invalid JSON.')
    print(data)

    try:
        reporter = reporter_cls(ev_type, data)
        await reporter.run()
    except UnsupportedEventError:
        return web.Response(status=204)
    except Exception as e:
        return web.Response(status=500, text='{!r}'.format(e))
    return web.Response(status=204)


if __name__ == '__main__':
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    app = web.Application()
    app.router.add_post('/webhook/{user}/{repo}', github_webhook)
    try:
        web.run_app(app, port=9092)
    except KeyboardInterrupt:
        loop.stop()
    finally:
        loop.close()
        print('terminated.')
