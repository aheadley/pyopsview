#!/usr/bin/python
import urllib2
from urllib import urlencode
import xml.dom.minidom as minidom

class OpsviewException(Exception):
    def __init__(self, msg=None):
        self.msg = msg or 'Unknown Error'

    def __str__(self):
        return self.msg

class OpsviewServer(object):
    def __init__(self, domain, username, password, path=''):
        self.domain = domain
        self.username = username
        self.password = password
        self.path = path
        self.hosts = []
        self.api_urls = dict({
            'acknowledge':      '%sstatus/service/acknowledge' % self.path,
            'status_all':       '%sapi/status/service' % self.path,
            'status_service':   '%sapi/status/service' % self.path,
            'status_host':      '%sapi/status/service' % self.path,
            'status_hostgroup': '%sapi/status/hostgroup' % self.path,
            'login':            '%slogin' % self.path,
            'api':              '%sapi' % self.path,
        })

        self.filters = dict({
            'ok':           ('state', 0),
            'warning':      ('state', 1),
            'critical':     ('state', 2),
            'unknown':      ('state', 3),
            'unhandled':    ('filter', 'unhandled'),
        })

        self._cookies = urllib2.HTTPCookieProcessor()
        self._opener = urllib2.build_opener(self._cookies)

    def __str__(self):
        return '%s:%i#%s' % (self.domain, self.port, self.path)

    def __repr__(self):
        return 'Server %s' % self

    def _connect(self):
        pass

    def _login(self):
        if 'auth_tkt' not in [cookie.name for cookie in self._cookies.cookiejar]:
            self._sendPost(self.api_urls['login'], dict({'login':'Log In', 'back':'', 'login_username':self.username, 'login_password':self.password}))
        assert 'auth_tkt' in [cookie.name for cookie in self._cookies.cookiejar], OpsviewException('Login failed')

    def _acknowledge(self, targets, comment, notify, auto_remove_comment):
        pass

    def _sendXML(self, payload):
        pass

    def _sendGet(self, location, parameters=None, headers=None):
        request = urllib2.Request('https://%s/%s?%s' % (self.domain, location, parameters))
        if headers:
            map(lambda header_key: request.add_header(header_key, headers[header_key]), headers)
        request.add_header('Content-Type', 'text/xml')
        try:
            reply = self._opener.open(request)
        except urllib2.HTTPError, reply:
            return reply
        else:
            return reply

    def _sendPost(self, location, data, headers=None):
        request = urllib2.Request('https://%s/%s' % (self.domain, location), urlencode(data))
        if headers:
            map(lambda header_key: request.add_header(header_key, headers[header_key]), headers)
        try:
            reply = self._opener.open(request)
        except urllib2.HTTPError, reply:
            return reply
        else:
            return reply

    def getStatusAll(self, filters=None):
        if filters: filters = [self.filters[filter] for filter in filters]
        return minidom.parse(self._sendGet(self.api_urls['status_all'], urlencode(filters)))

    def getStatusHost(self, host, filters=None):
        if filters:
            filters = [self.filters[filter] for filter in filters]
        else:
            filters = []
        filters.append(('host', host))
        return minidom.parse(self._sendGet(self.api_urls['status_host'], urlencode(filters)))

    def getStatusService(self, host, service):
        host_xml = self.getStatusHost(host)
        services = host_xml.getElementsByTagName('services')
        for svc_iter in services:
            if svc_iter.getAttribute('name').lower() == service.lower():
                return svc_iter
        raise OpsviewException('Service not found: %s:%s' % (host, service))

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