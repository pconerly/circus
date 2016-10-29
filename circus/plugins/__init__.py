""" Base class to create Circus subscribers plugins.
"""
import json
import sys
import errno
import uuid
import argparse

import zmq
import zmq.utils.jsonapi as json
from zmq.eventloop import ioloop, zmqstream

from circus import logger, __version__
from circus.client import make_message, cast_message
from circus.py3compat import b, s
from circus.util import (debuglog, to_bool, resolve_name, configure_logger,
                         DEFAULT_ENDPOINT_DEALER, DEFAULT_ENDPOINT_SUB,
                         get_connection, get_python_version)


class CircusPlugin(object):
    """Base class to write plugins.

    Options:

    - **context** -- the ZMQ context to use
    - **endpoint** -- the circusd ZMQ endpoint
    - **pubsub_endpoint** -- the circusd ZMQ pub/sub endpoint
    - **check_delay** -- the configured check delay
    - **config** -- free config mapping
    """
    name = ''

    def __init__(self, endpoint, pubsub_endpoint, check_delay, ssh_server=None,
                 **config):
        self.daemon = True
        self.config = config
        self.active = to_bool(config.get('active', True))
        self.pubsub_endpoint = pubsub_endpoint
        self.endpoint = endpoint
        self.check_delay = check_delay
        self.ssh_server = ssh_server
        self._id = b(uuid.uuid4().hex)
        self.running = False
        self.loop = ioloop.IOLoop()

    @debuglog
    def initialize(self):
        self.context = zmq.Context()
        self.client = self.context.socket(zmq.DEALER)
        self.client.setsockopt(zmq.IDENTITY, self._id)
        get_connection(self.client, self.endpoint, self.ssh_server)
        self.client.linger = 0
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'watcher.')
        self.sub_socket.connect(self.pubsub_endpoint)
        self.substream = zmqstream.ZMQStream(self.sub_socket, self.loop)
        self.substream.on_recv(self.handle_recv)

    @debuglog
    def start(self):
        if not self.active:
            raise ValueError('Will not start an inactive plugin')
        self.handle_init()
        self.initialize()
        self.running = True

        while True:
            try:
                self.loop.start()
            except zmq.ZMQError as e:
                logger.debug(str(e))

                if e.errno == errno.EINTR:
                    continue
                elif e.errno == zmq.ETERM:
                    break
                else:
                    logger.debug("got an unexpected error %s (%s)", str(e),
                                 e.errno)
                    raise
            else:
                break

        self.substream.close()
        self.client.close()
        self.sub_socket.close()
        self.context.destroy()

    @debuglog
    def stop(self):
        if not self.running:
            self.loop.close()
            return

        try:
            self.handle_stop()
        finally:
            self.loop.stop()

        self.running = False

    def call(self, command, **props):
        """Sends the command to **circusd**

        Options:

        - **command** -- the command to call
        - **props** -- keyword arguments to add to the call

        Returns the JSON mapping sent back by **circusd**
        """
        msg = make_message(command, **props)
        self.client.send(json.dumps(msg))
        msg = self.client.recv()
        return json.loads(msg)

    def cast(self, command, **props):
        """Fire-and-forget a command to **circusd**

        Options:

        - **command** -- the command to call
        - **props** -- keyword arguments to add to the call
        """
        msg = cast_message(command, **props)
        self.client.send(json.dumps(msg))

    #
    # methods to override.
    #
    def handle_recv(self, data):
        """Receives every event published by **circusd**

        Options:

        - **data** -- a tuple containing the topic and the message.
        """
        raise NotImplementedError()

    def handle_stop(self):
        """Called right before the plugin is stopped by Circus.
        """
        pass

    def handle_init(self):
        """Called right before a plugin is started - in the thread context.
        """
        pass

    @staticmethod
    def split_data(data):
        topic, msg = data
        topic_parts = s(topic).split(".")
        return topic_parts[1], topic_parts[2], msg

    @staticmethod
    def load_message(msg):
        return json.loads(msg)

    @classmethod
    def load_from_config(cls, config):
        print "watcher:load_from_config"
        if 'env' in config:
            # print "we got env: %s" % config['env']['PYTHONPATH']
            # print "we got env: %s" % config['env']['PATH']
            config['env'] = parse_env_dict(config['env'])
            # print "after-env: %s" % config['env']['PYTHONPATH']
            # print "after-env: %s" % config['env']['PATH']
        # cfg = config.copy()

        # w = cls(name=config.pop('name'), cmd=config.pop('cmd'), **config)
        # w._cfg = cfg

        return config

import os
LOG_FILE = os.path.join('/Users/peterconerly/code/circus', 'derp.txt')

def shitty_log(msg):
    with open(LOG_FILE, 'a') as fout:
        print msg
        try:
            fout.write(msg)
            fout.write('\n')
        except:
            pass


def _cfg2str(cfg):
    json_cfg = json.dumps(cfg, separators=(':::', ':'))
    if get_python_version() < (3, 0, 0):
        return json_cfg.encode('unicode-escape').replace(b'"', b'\\"')
    else:
        return json_cfg.encode('string-escape').replace('"', '\\"')


def _str2cfg(data):
    data = data.replace(':::', ',')
    # json.JSONEncoder(separators)
    shitty_log( "What's data?")
    shitty_log( data)
    shitty_log( "-----")
    result = json.loads(data)
    shitty_log( "What's result?")
    shitty_log( result)
    shitty_log( "-----")
    return result
    # cfg = {}
    # if data is None:
    #     return cfg

    # for item in data.split(':::'):
    #     item = item.split(':', 1)
    #     if len(item) != 2:
    #         continue
    #     key, value = item
    #     cfg[key.strip()] = value.strip()

    # return cfg


def get_plugin_cmd(config, endpoint, pubsub, check_delay, ssh_server,
                   debug=False, loglevel=None, logoutput=None):
    fqn = config['use']
    # makes sure the name exists

    # resolve_name(fqn)

    # we're good, serializing the config
    del config['use']
    config = _cfg2str(config)
    cmd = "%s -c 'from circus import plugins;plugins.main()'" % sys.executable
    cmd += ' --endpoint %s' % endpoint
    cmd += ' --pubsub %s' % pubsub
    if ssh_server is not None:
        cmd += ' --ssh %s' % ssh_server
    if len(config) > 0:
        cmd += ' --config %s' % config
    if debug:
        cmd += ' --log-level DEBUG'
    elif loglevel:
        cmd += ' --log-level ' + loglevel
    if logoutput:
        cmd += ' --log-output ' + logoutput
    cmd += ' %s' % fqn
    return cmd


def main():
    parser = argparse.ArgumentParser(description='Runs a plugin.')

    parser.add_argument('--endpoint',
                        help='The circusd ZeroMQ socket to connect to',
                        default=DEFAULT_ENDPOINT_DEALER)

    parser.add_argument('--pubsub',
                        help='The circusd ZeroMQ pub/sub socket to connect to',
                        default=DEFAULT_ENDPOINT_SUB)

    parser.add_argument('--config', help='The plugin configuration',
                        default=None)

    parser.add_argument('--version', action='store_true', default=False,
                        help='Displays Circus version and exits.')

    parser.add_argument('--check-delay', type=float, default=5.,
                        help='Checck delay.')

    parser.add_argument('plugin',
                        help='Fully qualified name of the plugin class.',
                        nargs='?')

    parser.add_argument('--log-level', dest='loglevel', default='info',
                        help="log level")

    parser.add_argument('--log-output', dest='logoutput', default='-',
                        help="log output")

    parser.add_argument('--ssh', default=None, help='SSH Server')

    args = parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)

    if args.plugin is None:
        parser.print_usage()
        sys.exit(0)

    shitty_log("resolving name")


    cfg = _str2cfg(args.config)
    shitty_log(cfg)

    import site

    # import ipdb
    # ipdb.set_trace()

    env = cfg.get('env', dict())

    if cfg.get('copy_env'):
        cfg['env'] = os.environ.copy()
        if cfg.get('copy_path'):
            path = os.pathsep.join(sys.path)
            cfg['env']['PYTHONPATH'] = path
        if env is not None:
            cfg['env'].update(env)
    else:
        if cfg.get('copy_path'):
            raise ValueError(('copy_env and copy_path must have the '
                              'same value'))
        cfg['env'] = env

    # if cfg.has_key('virtualenv'):
    #     util.load_virtualenv(cfg, py_ver=virtualenv_py_ver)

    # load directories in PYTHONPATH if provided
    # so if a hook is there, it can be loaded
    if cfg.get('env', None) is not None and 'PYTHONPATH' in cfg['env']:
        shitty_log("first hurdle")
        for path in cfg['env']['PYTHONPATH'].split(os.pathsep):
            if path in sys.path:
                continue
            shitty_log("adding path to site")
            site.addsitedir(path)

    print "--------- about to explode"
    factory = resolve_name(args.plugin)

    # configure the logger
    configure_logger(logger, args.loglevel, args.logoutput, name=factory.name)

    # load the plugin and run it.
    logger.info('Loading the plugin...')
    logger.info('Endpoint: %r' % args.endpoint)
    logger.info('Pub/sub: %r' % args.pubsub)
    plugin = factory(args.endpoint, args.pubsub,
                     args.check_delay, args.ssh,
                     **cfg)
    logger.info('Starting')
    try:
        plugin.start()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info('Stopping')
        plugin.stop()
    sys.exit(0)


if __name__ == '__main__':
    main()
