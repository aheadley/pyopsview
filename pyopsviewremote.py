#!/usr/bin/python
import httplib
import urllib

class OpsviewServer(object):
    def __init__(self, domain, username, password, path='/', secure=True):
        self.domain = domain
        self.username = username
        self.password = password
        self.path = path
        self.port = port
        self.hosts = []

        self.api_urls = dict({
            'acknowledge':      '%sstatus/service/acknowledge' % self.path,
            'status_all':       '%sapi/status/service',
            'status_service':   '%sapi/status/service',
            'status_host':      '%sapi/status/service',
            'status_hostgroup': '%sapi/status/hostgroup',
            'login':            '%slogin',
            'api':              '%sapi',
        })

    def __str__(self):
        return '%s:%i#%s' % (self.domain, self.port, self.path)

    def __repr__(self):
        return 'Server %s' % self

    def _connect(self):
        pass

    def _login(self):
        self._sendPost(self.api_urls['login'], urllib.urlencode(dict({'login':'Log In', 'back':'', 'login_username':self.username, 'login_password':self.password})))

    def _acknowledge(self, targets, comment, notify, auto_remove_comment):
        pass

    def _sendXML(self, payload):
        pass

    def _sendGet(self, location, parameters=None, headers=None):
        if self.secure:
            connection = httplib.HTTPSConnection(self.host)
        else:
            connection = httplib.HTTPConnection(self.host)
        connection.request('GET', location, urllib.urlencode(parameters), headers)
        response = connection.getresponse()
        connection.close()

        return response.read()

    def _sendPost(self, location, parameters=None, headers=None):
        if self.secure:
            connection = httplib.HTTPSConnection(self.host, self.port)
        else:
            connection = httplib.HTTPConnection(self.host, self.port)
        connection.request('POST', location, urllib.urlencode(parameters), headers)
        response = connection.getresponse()
        connection.close()

        return response.read()

    def getStatusAll(self, filters):
        pass

    def getStatusHost(self, filters, host):
        pass

    def getStatusService(self, host, service):
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
        self.alias = None
        self.services = services or []

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'Host %s (%s)' & (self.name, self.services)

class OpsviewService(object):
    def __init__(self, host, name):
        self.name = name
        self.downtime = None
        self.max_check_attempts = None
        self.current_check_attempts = None
        self.state_duration = None

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'Service %s' % self.name

if __name__ == '__main__':
    #tests go here
    pass