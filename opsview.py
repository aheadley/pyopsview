#!/usr/bin/env python

from urllib import urlencode, quote_plus
import urllib2
import xml.dom.minidom as minidom

class OpsviewException(Exception):
    """Basic exception."""

    def __init__(self, msg=None):
        if msg is not None:
            self.msg = 'Unknown Error'
        else:
            self.msg = msg

    def __str__(self):
        return self.msg

class OpsviewRemote(object):
    """Remote interface to Opsview server."""

    api_urls = dict({
        'acknowledge':          'status/service/acknowledge',
        'status_all':           'api/status/service',
        'status_service':       'api/status/service',
        'status_host':          'api/status/service',
        'status_byhostgroup':   'api/status/service',
        'status_hostgroup':     'api/status/hostgroup',
        'login':                'login',
        'api':                  'api',
    })
    filters = dict({
        'ok':           ('state', 0),
        'warning':      ('state', 1),
        'critical':     ('state', 2),
        'unknown':      ('state', 3),
        'unhandled':    ('filter', 'unhandled'),
    })

    def __init__(self, domain, username, password, path=None):
        self.domain   = domain
        self.username = username
        self.password = password
        if path is not None:
            self.path = path
        else:
            self.path = ''

        self._cookies = urllib2.HTTPCookieProcessor()
        self._opener = urllib2.build_opener(self._cookies)
        self._content_type = 'text/xml'

    def __str__(self):
        return 'https://%s@%s/%s' % (self.username, self.domain, self.path)

    def __repr__(self):
        return 'ServerRemote %s' % self

    def _login(self):
        if 'auth_tkt' not in [cookie.name for cookie in self._cookies.cookiejar]:
            try:
                self._opener.open(
                    urllib2.Request('https://%s/%s%s' %
                        (self.domain, self.path, OpsviewRemote.api_urls['login']),
                    urlencode(dict({
                        'login':'Log In',
                        'back':'https://%s/%s' % (self.domain, self.path),
                        'login_username':self.username,
                        'login_password':self.password,
                    })))
                )
            except urllib2.HTTPError:
                # Catch the redirect and do nothing.
                pass
        assert 'auth_tkt' in [cookie.name for cookie in self._cookies.cookiejar], \
            OpsviewException('Login failed')

    def _acknowledge(self, targets, comment=None, notify=True, auto_remove_comment=True):
        """Send acknowledgements for each target in targets.
        
        Targets should be a dict with this layout:
        targets=dict({
            host1:[list, of, services],
            host2:[list, again],
            host3:[None], #None means acknowledge the host itself
        })

        """

        data = urlencode(dict({
            'from':     'https://%s/%s' % (self.domain, self.path),
            'submit':   'Submit',
            'comment':  comment,
            'notify':   (notify and 'on') or 'off',
            'autoremovecomment':
                        (auto_remove_comment and 'on') or 'off',
        }))
        # Construct the hosts and services to acknowledge parameters.
        data += '&' + '&'.join([(service and 'service_selection=%s' %
            quote_plus('%s;%s' % (host, service))) or
            'host_selection=%s' % quote_plus(host)
            for host in targets for service in targets[host]])

        return self.sendPost(OpsviewRemote.api_urls['acknowledge'], data)

    def _send_xml(self, payload):
        """Send payload (an xml Node object) to the api url via POST."""

        return minidom.parse(self._send_post(OpsviewRemote.api_urls['api'],
            payload.toxml(), dict({'Content-Type':'text/xml'})))

    def _send_get(self, location, parameters=None, headers=None):
        request = urllib2.Request('https://%s/%s%s?%s' %
            (self.domain, self.path, location, parameters))
        if headers is not None:
            map(
                lambda header_key: request.add_header(header_key, headers[header_key]),
                headers
            )
        request.add_header('Content-Type', self._content_type)
        self._login()
        try:
            reply = self._opener.open(request)
        except urllib2.HTTPError, reply:
            return reply
        else:
            return reply

    def _send_post(self, location, data, headers=None):
        request = urllib2.Request('https://%s/%s%s' % (self.domain, self.path, location), data)
        if headers is not None:
            map(
                lambda header_key: request.add_header(header_key, headers[header_key]),
                headers
            )
        self._login()
        try:
            reply = self._opener.open(request)
        except urllib2.HTTPError, reply:
            return reply
        else:
            return reply

    def get_status_all(self, filters=None):
        """Get status of all services.

        Optionally filter the results with a list of filters from
        OpsviewRemote.filters

        """

        if filters is None:
            filters = []
        else:
            filters = [OpsviewRemote.filters[filter] for filter in filters]
        return minidom.parse(self._send_get(OpsviewRemote.api_urls['status_all'], urlencode(filters)))

    def get_status_host(self, host, filters=None):
        """Get status of a host and all its services.
        
        Optionally filter the results with a list of filters from
        OpsviewRemote.filters
        
        """

        if filters is None:
            filters = []
        else:
            filters = [OpsviewRemote.filters[filter] for filter in filters]
        filters.append(('host', host))
        return minidom.parse(self._send_get(OpsviewRemote.api_urls['status_host'], urlencode(filters)))

    def get_status_service(self, host, service):
        """Get status of a host's service."""

        host_xml = self.get_status_host(host)
        services = host_xml.getElementsByTagName('services')
        for svc_iter in services:
            if svc_iter.getAttribute('name').lower() == service.lower():
                return svc_iter
        raise OpsviewException('Service not found: %s:%s' % (host, service))

    def get_status_by_hostgroup(self, hostgroup, filters=None):
        """Get status of the hosts in a hostgroup..

        Optionally filter the results with a list of filters from
        OpsviewRemote.filters

        """

        if filters is None:
            filters = []
        else:
            filters = [OpsviewRemote.filters[filter] for filter in filters]
        filters.append(('hostgroupid', int(hostgroup)))
        return minidom.parse(self._send_get(
            OpsviewRemote.api_urls['status_hostgroup'],
            urlencode(filters)
        ))

    def get_status_hostgroup(self, hostgroup=None):
        """Get of a top-level hostgroup or all top-level hostgroups."""

        if hostgroup is None:
            hostgroup = ''

        return minidom.parse(self._send_get('%s/%s' %
            (OpsviewRemote.api_urls['status_hostgroup'], hostgroup)))

    def acknowledge_service(self, host, service, comment, notify=True, auto_remove_comment=True):
        """Acknoledge a single service."""

        return self._acknowledge(dict({host:[service]}), comment, notify, auto_remove_comment)

    def acknowledge_host(self, host, comment, notify=True, auto_remove_comment=True):
        """Acknoledge a single host."""

        return self._acknowledge(dict({host:[None]}), comment, notify, auto_remove_comment)

    def acknowledge_all(self, comment, notify=True, auto_remove_comment=True):
        """Acknowledge all currently alerting hosts and services.

        Alerting is understood here to be when current_check_attempt is equal to
        max_check_attempts.

        """

        status = self._get_status_all(['warning', 'critical', 'unhandled'])
        alerting = dict({})
        for host in status.getElementsByTagName('list'):
            alerting[host.getAttribute('name')] = []
            if int(host.getAttribute('current_check_attempt')) == \
                int(host.getAttribute('max_check_attempts')):
                alerting[host.getAttribute('name')].append(None)
            for service in host.getElementsByName('services'):
                if int(service.getAttribute('current_check_attempt')) == \
                    int(service.getAttribute('max_check_attempts')):
                    alerting[host.getAttribute('name')].append(service.getAttribute('name'))
        return self._acknowledge(alerting, comment, notify, auto_remove_comment)

    def create_host(self, **attrs):
        """Create a new host.

        The new host's attributes are passed as as arbitrary keyword arguments.
        There are no restrictions or checking done on the keywords or their
        values so it would be wise to check the return from the opsview server.

        """
        xml = """<opsview>
            <host action="create">
                %s
            </host>
        </opsview>"""

        return self._send_xml(minidom.parseString(xml %
            (''.join(['<%s>%s</%s>' % (key, attrs[key], key) for key in attrs]))))

    def clone_host(self, old_host_name, **attrs):
        """Create a new host by cloning an old one.

        Syntax is the same as create_host with the addition of the old_host_name
        argument that selects the host to clone from.

        """
        xml = """<opsview>
            <host action="create">
                <clone>
                    <name>%s</name>
                </clone>
                %s
            </host>
        </opsview>"""

        return self._send_xml(minidom.parseString(xml %
            (old_host_name, ''.join(['<%s>%s</%s>' %
                (key, attrs[key], key) for key in attrs]))))

    def delete_host(self, host):
        """Delete a host by name or ID number."""

        xml = """<opsview>
            <host action="delete" by_%s="%s"/>
        </opsview>"""

        if host.isdigit():
            method = 'id'
        else:
            method = 'name'

        return self._send_xml(minidom.parseString(xml % (method, host)))

    def schedule_downtime(self, hostgroup, start_time, end_time, comment):
        xml = """<opsview>
            <hostgroup action="change" by_%s="%s">
                <downtime
                    start="%s"
                    end="%s"
                    comment="%s">
                    enable
                </downtime>
            </hostgroup>
        </opsview>"""

        if host.isdigit():
            method = 'id'
        else:
            method = 'name'

        return self._send_xml(minidom.parseString(xml %
            (method, hostgroup, start_time, end_time, comment)))

    def disable_scheduled_downtime(self, hostgroup):
        xml = """<opsview>
            <hostgroup action="change" by_%s="%s">
                <downtime>disable</downtime>
            </hostgroup>
        </opsview>"""

        if host.isdigit():
            method = 'id'
        else:
            method = 'name'

        return self._send_xml(minidom.parseString(xml % (method, hostgroup)))

    def enable_notifications(self, hostgroup):
        xml = """<opsview>
            <hostgroup action="change" by_%s="%s">
                <notifications>enable</notifications>
            </hostgroup>
        </opsview>"""

        if host.isdigit():
            method = 'id'
        else:
            method = 'name'

        return self._send_xml(minidom.parseString(xml % (method, hostgroup)))

    def disable_notifications(self, hostgroup):
    	"""Disable notifications for a leaf hostgroup by id or name."""
    	
        xml = """<opsview>
            <hostgroup action="change" by_%s="%s">
                <notifications>disable</notifications>
            </hostgroup>
        </opsview>"""

        if host.isdigit():
            method = 'id'
        else:
            method = 'name'

        return self._send_xml(minidom.parseString(xml % (method, hostgroup)))

    def reload(self):
        """Reload the remote Opsview server's configuration."""

        xml = """<opsview>
            <system action="reload"/>
        </opsview>"""

        return self._send_xml(minidom.parseString(xml))

class OpsviewServer(object):
    """Logical server object."""

    def __init__(self, src_xml=None, remote=None, filters=None):
        self.hosts = []
        self.remote = remote

        assert src_xml is not None or self.remote is not None, \
            OpsviewException('No source to populate object')

        if src_xml is not None:
            self.parse(src_xml)
        else:
            self.parse(self.remote.get_status_all(filters))

    def update(self, filters=None):
        self.parse(self.remote.get_status_all(filters))

        return self

    def parse(self, src_xml):
        if isinstance(src_xml, basestring):
            src_xml = minidom.parseString(src_xml)
        elif isinstance(src_xml, file):
            src_xml = minidom.parse(src_xml)
        assert isinstance(src_xml, minidom.Node)

        self.hosts = map(
            lambda host_node: OpsviewHost(self, src_xml=host_node),
            src_xml.getElementsByTagName('list')
        )

        return self

class OpsviewHost(dict):
    """Logical host object."""

    def __init__(self, server, src_xml=None):
        self.server = server
        self.services = []
        if src_xml is not None:
            self.parse(src_xml)
        assert isinstance(self.server, OpsviewServer)

    def update(self, filters=None):
        self.parse(self.server.remote.get_status_host(self['name'], filters))

        return self

    def parse(self, src_xml):
        if isinstance(src_xml, basestring):
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

        return self

class OpsviewService(dict):
    """Logical service object."""

    def __init__(self, host, src_xml=None):
        self.host = host
        if src_xml is not None:
            self.parse(src_xml)
        assert isinstance(self.host, OpsviewHost)

    def update(self):
        self.parse(self.host.server.remote.get_status_service(self.host['name'], self['name']))

        return self

    def parse(self, src_xml):
        if isinstance(src_xml, basestring):
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

        return self