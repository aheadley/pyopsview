#!/usr/bin/python
import httplib, urllib
import socket

class OpsviewServer(object):
    def __init__(self, domain, path='/', port=httplib.HTTPS_PORT):
        self.domain = domain
        self.path = path
        self.port = port

    def _connect(self):
        pass

    def getStatusAll(self):
        pass

    def getStatusService(self, host, service):
        pass

    def getStatusHost(self, host):
        pass

    def getStatusHostgroup(self, hostgroup):
        pass

    def acknowledgeService(self, host, service, comment, notify=True, auto_remove_comment=True):
        pass

    def acknowledgeHost(self, host, comment, notify=True, auto_remove_comment=True):
        pass

    def acknowledgeAll(self, comment, notify=True, auto_remove_comment=True):
        pass

    def createHost(self, new_host_name):
        pass

    def cloneHost(self, new_host_name, old_host_name):
        pass

    def createHost(self, host):
        pass

    def reload(self):
        pass

class OpsviewHost(object):
    def __init__(self, name, services=None):
        self.name = name
        self.services = services or []

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'Host %s (%s)' & (self.name, self.services)

class OpsviewService(object):
    def __init__(self, host, name):
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'Service %s' % self.name

if __name__ == '__main__':
    #tests go here
    pass