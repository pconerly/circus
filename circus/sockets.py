import socket


_FAMILY = {
    'AF_UNIX': socket.AF_UNIX,
    'AF_INET': socket.AF_INET,
    'AF_INET6': socket.AF_INET6
}

_TYPE = {
    'SOCK_STREAM': socket.SOCK_STREAM,
    'SOCK_DGRAM': socket.SOCK_DGRAM,
    'SOCK_RAW': socket.SOCK_RAW,
    'SOCK_RDM': socket.SOCK_RDM,
    'SOCK_SEQPACKET': socket.SOCK_SEQPACKET
}


def addrinfo(host, port):
    return socket.getaddrinfo(host, port)[0][-1]


class CircusSocket(socket.socket):
    """Inherits from socket, to add a few extra options.
    """
    def __init__(self, name='', host='localhost', port=8080,
                 family=socket.AF_INET, type=socket.SOCK_STREAM,
                 proto=0, backlog=1):
        self.name = name
        self.host, self.port = addrinfo(host, port)
        self.backlog = backlog
        socket.socket.__init__(self, family, type, proto=proto)
        self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def bind_and_listen(self):
        self.bind((self.host, self.port))
        self.listen(self.backlog)
        self.host, self.port = self.getsockname()

    @classmethod
    def load_from_config(cls, config):
        name = config['name']
        host = config.get('host', 'localhost')
        port = int(config.get('port', '8080'))
        family = _FAMILY[config.get('family', 'AF_INET').upper()]
        type = _TYPE[config.get('type', 'SOCK_STREAM').upper()]
        proto = socket.getprotobyname(config.get('proto', 'ip'))
        backlog = int(config.get('backlog', '1'))
        return cls(name, host, port, family, type, proto, backlog)


class CircusSockets(dict):
    """Manage CircusSockets objects.
    """
    def __init__(self, sockets=None, backlog=-1):
        self.backlog = backlog
        if sockets is not None:
            for sock in sockets:
                self[sock.name] = sock

    def add(self, name, host='localhost', port=8080, family=socket.AF_INET,
            type=socket.SOCK_STREAM, proto=0, backlog=None):

        if backlog is None:
            backlog = self.backlog

        sock = self.get(name)
        if sock is not None:
            raise ValueError('A socket already exists %s' % sock)

        sock = CircusSocket(name, host, port, family, type, proto, backlog)
        self[name] = sock
        return sock

    def close_all(self):
        for sock in self.values():
            sock.close()

    def bind_and_listen_all(self):
        for sock in self.values():
            sock.bind_and_listen()
