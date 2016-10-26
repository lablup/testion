import argparse
import asyncio
import json
import logging
import signal
import traceback
from pathlib import Path

from aiohttp import web
import coloredlogs
import uvloop
import yaml

from .exceptions import UnsupportedEventError
from .reporter.unittest import UnitTestReporter
from .reporter.functest import SeleniumFunctionalTestReporter


reporter_map = {
    'unit': UnitTestReporter,
    'slfunc': SeleniumFunctionalTestReporter,
}

here = Path(__file__).resolve().parent.parent


async def job_loop(loop, queue):
    log = logging.getLogger('testion.jobqueue')
    while True:
        try:
            job = await queue.get()
            log.info('Fetched a new job and executing it. (current qsize: {})'
                     .format(queue.qsize()))
            await job
            queue.task_done()
        except asyncio.CancelledError:
            break

async def github_webhook(request):
    app = request.app
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
        app._last_reporter = reporter  # for tests
        if app._job_queue.qsize() > 0:
            reporter._mark_status('pending', msg='Waiting for other tests to finish...')
        await app._job_queue.put(reporter.run())
    except UnsupportedEventError:
        return web.Response(status=400, text='Unsupported GitHub event type.')
    except Exception as e:
        print(traceback.format_exc())
        return web.Response(status=500, text=traceback.format_exc())
    return web.Response(status=204)

def handle_signal(loop, term_ev):
    if not term_ev.is_set():
        loop.stop()


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

    #asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    app = web.Application(loop=loop)
    app.config = config
    app.sslctx = None
    app.router.add_post('/webhook', github_webhook)
    app._job_queue = asyncio.Queue(loop=loop)
    term_ev = asyncio.Event(loop=loop)
    loop.add_signal_handler(signal.SIGINT, handle_signal, loop, term_ev)
    loop.add_signal_handler(signal.SIGTERM, handle_signal, loop, term_ev)
    try:
        web_handler = app.make_handler(keep_alive_on=False)
        job_task = asyncio.ensure_future(job_loop(loop, app._job_queue))
        server = loop.run_until_complete(
            loop.create_server(web_handler, '0.0.0.0',
                               app.config['service_port']))
        logger.info('Running the server on port {}'
                    .format(app.config['service_port']))
        loop.run_forever()
        # interrupted
        term_ev.set()
        async def finish_web():
            server.close()
            job_task.cancel()
            await server.wait_closed()
            await app.shutdown()
            await web_handler.finish_connections()
            await app.cleanup()
        loop.run_until_complete(finish_web())
    finally:
        loop.close()
        logger.info('terminated.')
