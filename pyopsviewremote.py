#!/usr/bin/python
import urllib2
from urllib import urlencode
import xml.dom.minidom as minidom

class OpsviewException(Exception):
    def __init__(self, msg=None):
        self.msg = msg or 'Unknown Error'

    def __str__(self):
        return self.msg

class OpsviewRemote(object):
    def __init__(self, domain, username, password, path=''):
        self.domain = domain
        self.username = username
        self.password = password
        self.path = path
        self.api_urls = dict({
            'acknowledge':          '%sstatus/service/acknowledge' % self.path,
            'status_all':           '%sapi/status/service' % self.path,
            'status_service':       '%sapi/status/service' % self.path,
            'status_host':          '%sapi/status/service' % self.path,
            'status_byhostgroup':   '%sapi/status/service' % self.path,
            'status_hostgroup':     '%sapi/status/hostgroup' % self.path,
            'login':                '%slogin' % self.path,
            'api':                  '%sapi' % self.path,
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
        self._content_type = 'text/xml'
        self._login()

    def __str__(self):
        return 'https://%s@%s/%s' % (self.username, self.domain, self.path)

    def __repr__(self):
        return 'ServerRemote %s' % self

    def _login(self):
        """Attempt to login if there isn't an auth cookie already in the cookiejar"""

        if 'auth_tkt' not in [cookie.name for cookie in self._cookies.cookiejar]:
            self._sendPost(self.api_urls['login'], dict({'login':'Log In', 'back':'', 'login_username':self.username, 'login_password':self.password}))
        assert 'auth_tkt' in [cookie.name for cookie in self._cookies.cookiejar], OpsviewException('Login failed')

    def _acknowledge(self, targets, comment=None, notify=True, auto_remove_comment=True):
        data = urlencode(dict({
            'from':     'https://%s/%s' % (self.domain, self.path),
            'submit':   'Submit',
            'comment':  comment,
            'notify':   (notify and 'on') or 'off',
            'autoremovecomment':
                        (auto_remove_comment and 'on') or 'off',
        }))
        data += '&'
        #this makes me feel like a goddamn genius
        data += '&'.join([urlencode((service and 'service_selection=%s;%s' % (host, service)) or 'host_selection=%s' % host) \
            for host in targets for service in targets[host]])

        self.sendPost(self.api_urls['acknowledge'], data)

    def _sendXML(self, payload):
        pass

    def _sendGet(self, location, parameters=None, headers=None):
        """Send a GET request to the Opsview server/location?parameters
        and optional headers as a list of tuples.
        (parameters) should already be urlencoded."""

        request = urllib2.Request('https://%s/%s?%s' % (self.domain, location, parameters))
        if headers:
            map(lambda header_key: request.add_header(header_key, headers[header_key]), headers)
        request.add_header('Content-Type', self._content_type)
        try:
            reply = self._opener.open(request)
        except urllib2.HTTPError, reply:
            return reply
        else:
            return reply

    def _sendPost(self, location, data, headers=None):
        """Send a POST request to the Opsview server/location with data
        and optional headers as a list of tuples.
        (data) should already be urlencoded."""

        request = urllib2.Request('https://%s/%s' % (self.domain, location), data)
        if headers:
            map(lambda header_key: request.add_header(header_key, headers[header_key]), headers)
        try:
            reply = self._opener.open(request)
        except urllib2.HTTPError, reply:
            return reply
        else:
            return reply

    def getStatusAll(self, filters=[]):
        filters = [self.filters[filter] for filter in filters]
        return minidom.parse(self._sendGet(self.api_urls['status_all'], urlencode(filters)))

    def getStatusHost(self, host, filters=[]):
        filters = [self.filters[filter] for filter in filters]
        filters.append(('host', host))
        return minidom.parse(self._sendGet(self.api_urls['status_host'], urlencode(filters)))

    def getStatusService(self, host, service):
        host_xml = self.getStatusHost(host)
        services = host_xml.getElementsByTagName('services')
        for svc_iter in services:
            if svc_iter.getAttribute('name').lower() == service.lower():
                return svc_iter
        raise OpsviewException('Service not found: %s:%s' % (host, service))

    def getStatusByHostgroup(self, hostgroup, filters=[]):
        filters = [self.filters[filter] for filter in filters]
        filters.append(('hostgroupid', int(hostgroup)))
        return minidom.parse(self._sendGet(self.api_urls['status_hostgroup'], urlencode(filters)))

    def getStatusHostgroup(self, hostgroup=None):
        return minidom.parse(self._sendGet('%s/%s' % (self.api_urls['status_hostgroup'], hostgroup or '')))

    def acknowledgeService(self, host, service, comment, notify=True, auto_remove_comment=True):
        return self._acknowledge(dict({host:[service]}), comment, notify, auto_remove_comment)

    def acknowledgeHost(self, host, comment, notify=True, auto_remove_comment=True):
        self._acknowledge(dict({host:[None]}), comment, notify, auto_remove_comment)

    def acknowledgeAll(self, comment, notify=True, auto_remove_comment=True):
        pass

    def createHost(self, new_host_name):
        pass

    def cloneHost(self, old_host_name, new_host_name):
        pass

    def createHost(self, host):
        pass

    def reload(self):
        pass

class OpsviewServer(object):
    def __init__(self, name, hosts=None):
        self.name = name
        self.hosts = hosts or []

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'Server: %s (%i Hosts)' % (self.name, len(self.hosts))

class OpsviewHost(object):
    def __init__(self, name, services=None):
        self.name = name
        self.alias = None
        self.services = services or []

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'Host %s (%i Services)' & (self.name, len(self.services))

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