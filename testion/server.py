import argparse
import asyncio
import json
import logging
import traceback
from pathlib import Path

from aiohttp import web
import coloredlogs
import uvloop
import yaml

from .exceptions import UnsupportedEventError
from .reporter.base import EntranceLock
from .reporter.unittest import UnitTestReporter
from .reporter.functest import SeleniumFunctionalTestReporter


reporter_map = {
    'unit': UnitTestReporter,
    'slfunc': SeleniumFunctionalTestReporter,
}

here = Path(__file__).resolve().parent.parent


async def github_webhook(request):
    try:
        report_key = request.GET['report']
    except KeyError:
        return web.Response(status=400, text='Missing report key.')

    ev_type = request.headers.get('X-GitHub-Event', 'push')
    try:
        data = await request.json()
    except json.decoder.JSONDecodeError:
        return web.Response(status=400, text='Invalid JSON.')

    repo_name = data['repository']['full_name']
    try:
        config = request.app.config[repo_name]
    except KeyError:
        return web.Response(status=400, text='Not configured repository.')

    try:
        report = config['reports'][report_key]
    except KeyError:
        return web.Response(status=400, text='Not configured report key.')

    try:
        reporter_cls = reporter_map[report['cls']]
    except KeyError:
        return web.Response(status=400, text='Invalid reporter class.')

    try:
        reporter = reporter_cls(config, report, data)
        request.app._last_reporter = reporter  # for tests
        if request.GET.get('blocking', '0') == '1':
            await reporter.run()
        else:
            asyncio.ensure_future(reporter.run())
    except UnsupportedEventError:
        return web.Response(status=400, text='Unsupported GitHub event type.')
    except Exception as e:
        print(traceback.format_exc())
        return web.Response(status=500, text=traceback.format_exc())
    return web.Response(status=204)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=9092)
    parser.add_argument('-f', '--config', type=Path, default=here / 'config.yml')
    args = parser.parse_args()
    config = yaml.load(args.config.read_text())
    config['service_port'] = args.port

    # Set up the root logger that prints all test runs.
    coloredlogs.install(
        level='DEBUG',
        fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
        field_styles={'levelname': {'color':'black', 'bold':True},
                      'name': {'color':'black', 'bold':True},
                      'asctime': {'color':'black'}},
        level_styles={'info': {'color':'cyan'},
                      'debug': {'color':'green'},
                      'warning': {'color':'yellow'},
                      'error': {'color':'red'},
                      'critical': {'color':'red', 'bold':True}}
    )
    logger = logging.getLogger('testion')
    logger.info('starting...')

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    EntranceLock.init_global(1, loop)
    app = web.Application()
    app.config = config
    app.sslctx = None
    app.router.add_post('/webhook', github_webhook)
    try:
        web.run_app(app, port=config['service_port'])
    except (KeyboardInterrupt, SystemExit):
        loop.stop()
    finally:
        loop.close()
        logger.info('terminated.')
