#!/usr/bin/python
import urllib2
from urllib import urlencode, quote_plus
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

    def __str__(self):
        return 'https://%s@%s/%s' % (self.username, self.domain, self.path)

    def __repr__(self):
        return 'ServerRemote %s' % self

    def _login(self):
        """Attempt to login if there isn't an auth cookie already in the cookiejar"""

        if 'auth_tkt' not in [cookie.name for cookie in self._cookies.cookiejar]:
            try:
                self._opener.open(urllib2.Request('https://%s/%s' % (self.domain, self.api_urls['login']),
                    urlencode(dict({
                        'login':'Log In',
                        'back':'',
                        'login_username':self.username,
                        'login_password':self.password
                    }))
                ))
            except urllib2.HTTPError:
                pass
        assert 'auth_tkt' in [cookie.name for cookie in self._cookies.cookiejar], OpsviewException('Login failed')

    def _acknowledge(self, targets, comment=None, notify=True, auto_remove_comment=True):
        """Send acknowledgements for each target in targets. targets should be a
        dict with this layout:
        targets=dict({
            host1:[list, of, services],
            host2:[list, again],
            host3:[None], #None means acknowledge the host itself
        })"""

        data = urlencode(dict({
            'from':     'https://%s/%s' % (self.domain, self.path),
            'submit':   'Submit',
            'comment':  comment,
            'notify':   (notify and 'on') or 'off',
            'autoremovecomment':
                        (auto_remove_comment and 'on') or 'off',
        }))
        #this makes me feel like a goddamn genius
        data += '&' + '&'.join([(service and 'service_selection=%s' % quote_plus('%s;%s' % (host, service))) \
            or 'host_selection=%s' % quote_plus(host) \
            for host in targets for service in targets[host]])

        return self.sendPost(self.api_urls['acknowledge'], data)

    def _sendXML(self, payload):
        """Send payload (an xml Document object) to the api url via POST."""

        return minidom.parse(self._sendPost(self.api_urls['api'], payload.toxml(), dict({'Content-Type':'text/xml'})))

    def _sendGet(self, location, parameters=None, headers=None):
        """Send a GET request to the Opsview server/location?parameters
        and optional headers as a list of tuples.
        (parameters) should already be urlencoded."""

        request = urllib2.Request('https://%s/%s?%s' % (self.domain, location, parameters))
        if headers:
            map(lambda header_key: request.add_header(header_key, headers[header_key]), headers)
        request.add_header('Content-Type', self._content_type)
        try:
            self._login()
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
            self._login()
            reply = self._opener.open(request)
        except urllib2.HTTPError, reply:
            return reply
        else:
            return reply

    def getStatusAll(self, filters=None):
        if not filters:
            filters = []
        else:
            filters = [self.filters[filter] for filter in filters]
        return minidom.parse(self._sendGet(self.api_urls['status_all'], urlencode(filters)))

    def getStatusHost(self, host, filters=None):
        if not filters:
            filters = []
        else:
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

    def getStatusByHostgroup(self, hostgroup, filters=None):
        """Get status of hosts by the hostgroup they are in."""

        if not filters:
            filters = []
        else:
            filters = [self.filters[filter] for filter in filters]
        filters.append(('hostgroupid', int(hostgroup)))
        return minidom.parse(self._sendGet(self.api_urls['status_hostgroup'], urlencode(filters)))

    def getStatusHostgroup(self, hostgroup=None):
        """Get the status of a top-level hostgroup, or the status of all top-level hostgroups if no
        hostgroup is passed."""

        return minidom.parse(self._sendGet('%s/%s' % (self.api_urls['status_hostgroup'], hostgroup or '')))

    def acknowledgeService(self, host, service, comment, notify=True, auto_remove_comment=True):
        return self._acknowledge(dict({host:[service]}), comment, notify, auto_remove_comment)

    def acknowledgeHost(self, host, comment, notify=True, auto_remove_comment=True):
        return self._acknowledge(dict({host:[None]}), comment, notify, auto_remove_comment)

    def acknowledgeAll(self, comment, notify=True, auto_remove_comment=True):
        """Acknowledge all currently alerting (at max_check_attempts) services"""

        status = self._getStatusAll(['warning', 'critical', 'unhandled'])
        alerting = dict({})
        for host in status.getElementsByTagName('list'):
            alerting[host.getAttribute('name')] = []
            if int(host.getAttribute('current_check_attempt')) == int(host.getAttribute('max_check_attempts')):
                alerting[host.getAttribute('name')].append(None)
            for service in host.getElementsByName('services'):
                if int(service.getAttribute('current_check_attempt')) == int(service.getAttribute('max_check_attempts')):
                    alerting[host.getAttribute('name')].append(service.getAttribute('name'))
        return self._acknowledge(alerting, comment, notify, auto_remove_comment)

    def createHost(self, **attrs):
        xml = """<opsview>
            <host action="create">
                %s
            </host>
        </opsview>"""

        return self._sendXML(minidom.parseString(xml % (''.join(['<%s>%s</%s>' % (key, attrs[key], key) for key in attrs]))))

    def cloneHost(self, old_host_name, new_host_name):
        xml = """<opsview>
            <host action="create">
                <clone>
                    <name>%s</name>
                </clone>
                <name>%s</name>
            </host>
        </opsview>"""

        return self._sendXML(minidom.parseString(xml % (old_host_name, new_host_name)))

    def deleteHost(self, host):
        """Delete a host by name or ID number"""

        doc = """<opsview>
            <host action="delete" by_%s="%s"/>
        </opsview>"""
        method= (host.isdigit() and 'id') or 'name'

        return self._sendXML(minidom.parseString(doc % (method, host)))

    def scheduleDowntime(self, hostgroup, start_time, end_time, comment):
        doc = """<opsview>
            <hostgroup action="change" by_%s="%s">
                <downtime
                    start="%s"
                    end="%s"
                    comment="%s">
                    enable
                </downtime>
            </hostgroup>
        </opsview>"""
        method= (hostgroup.isdigit() and 'id') or 'name'

        return self._sendXML(minidom.parseString(doc % (method, hostgroup, start_time, end_time, comment)))

    def disableScheduledDowntime(self, hostgroup):
        doc = """<opsview>
            <hostgroup action="change" %s="%s">
                <downtime>disable</downtime>
            </hostgroup>
        </opsview>"""
        method= (hostgroup.isdigit() and 'id') or 'name'

        return self._sendXML(minidom.parseString(doc % (method, hostgroup)))

    def enableNotifications(self, hostgroup):
        doc = """<opsview>
            <hostgroup action="change" by_%s="%s">
                <notifications>enable</notifications>
            </hostgroup>
        </opsview>"""
        method = (hostgroup.isdigit() and 'id') or 'name'

        return self._sendXML(minidom.parseString(doc % (method, hostgroup)))

    def disableNotifications(self, hostgroup):
        doc = """<opsview>
            <hostgroup action="change" by_%s="%s">
                <notifications>disable</notifications>
            </hostgroup>
        </opsview>"""
        method = (hostgroup.isdigit() and 'id') or 'name'

        return self._sendXML(minidom.parseString(doc % (method, hostgroup)))

    def reload(self):
        """Reload the remote Opsview server's configuration."""

        doc = """<opsview>
            <system action="reload"/>
        </opsview>"""

        return self._sendXML(minidom.parseString(doc))

class OpsviewServer(object):
    def __init__(self, src_xml=None, remote=None, filters=None):
        self.hosts = []
        self.remote = remote

        assert src_xml or self.remote, OpsviewException('No source to populate object')

        if src_xml:
            self.parse(src_xml)
        else:
            self.parse(self.remote.getStatusAll(filters))

    def update(self, filters=None):
        self.parse(self.remote.getStatusAll(filters))

    def parse(self, src_xml):
        if isinstance(src_xml, str):
            src_xml = minidom.parseString(src_xml)
        elif isinstance(src_xml, file):
            src_xml = minidom.parse(src_xml)
        assert isinstance(src_xml, minidom.Node)

        #this will (probably) leak memory, need to make unlink method or something
        self.hosts = map(
            lambda host_node: OpsviewHost(self, src_xml=host_node),
            src_xml.getElementsByTagName('list')
        )

class OpsviewHost(dict):
    def __init__(self, server, src_xml=None):
        self.server = server
        self.services = []
        if src_xml:
            self.parse(src_xml)
        assert isinstance(self.server, OpsviewServer)

    def update(self, filters=None):
        self.parse(self.server.remote.getStatusHost(self['name'], filters))

    def parse(self, src_xml):
        if isinstance(src_xml, str):
            src_xml = minidom.parseString(src_xml)
        elif isinstance(src_xml, file):
            src_xml = minidom.parse(src_xml)
        assert isinstance(src_xml, minidom.Node)

        if not (hasattr(src_xml, 'tagName') and src_xml.tagName == 'list'):
            src_xml = src_xml.getElementsByTagName('list')[0]

        for i in range(src_xml.attributes.length):
            try:
                self[src_xml.attributes.item(i).name] = int(src_xml.attributes.item(i).value)
            except ValueError:
                self[src_xml.attributes.item(i).name] = src_xml.attributes.item(i).value

        self.services = map(
            lambda service_node: OpsviewService(self, src_xml=service_node),
            src_xml.getElementsByTagName('services')
        )

class OpsviewService(dict):
    def __init__(self, host, src_xml=None):
        self.host = host
        if src_xml:
            self.parse(src_xml)
        assert isinstance(self.host, OpsviewHost)

    def update(self):
        self.parse(self.host.server.remote.getStatusService(self.host['name'], self['name']))

    def parse(self, src_xml):
        if isinstance(src_xml, str):
            src_xml = minidom.parseString(src_xml)
        elif isinstance(src_xml, file):
            src_xml = minidom.parse(src_xml)
        assert isinstance(src_xml, minidom.Node)

        if not (hasattr(src_xml, 'tagName') and src_xml.tagName == 'services'):
            src_xml = src_xml.getElementsByTagName('services')[0]

        for i in range(src_xml.attributes.length):
            try:
                self[src_xml.attributes.item(i).name] = int(src_xml.attributes.item(i).value)
            except ValueError:
                self[src_xml.attributes.item(i).name] = src_xml.attributes.item(i).value

if __name__ == '__main__':
    #tests go here
    pass
