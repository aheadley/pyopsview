#!/usr/bin/env python

from urllib import urlencode, quote_plus
import urllib2
import xml.dom.minidom as minidom
import json


def _dict_to_xml(target):
    element_list = [
        '<%s>%s</%s>' % (
            key,
            (isinstance(target[key], dict) and _dict_to_xml(target[key])) or
                target[key],
            key
        ) for key in target
    ]
    return ''.join(element_list)

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

    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self._cookies = urllib2.HTTPCookieProcessor()
        self._opener = urllib2.build_opener(self._cookies)
        self._content_type = 'text/xml'

    def __str__(self):
        return self.base_url

    def __repr__(self):
        return 'ServerRemote %s' % self

    def login(self):
        """Login to the Opsview server.

        This is implicitly called on every get/post to the Opsview server to
        make sure we're always authed. Of course, we don't always send an actual
        login request, the method will check if we have an "auth_tkt" cookie
        first and return if we do since it means we're still logged in.

        """
        
        if 'auth_tkt' not in [cookie.name for cookie in self._cookies.cookiejar]:
            try:
                self._opener.open(
                    urllib2.Request(self.base_url + OpsviewRemote.api_urls['login'],
                    urlencode(dict({
                        'login':'Log In',
                        'back':self.base_url,
                        'login_username':self.username,
                        'login_password':self.password,
                    })))
                )
            except urllib2.HTTPError:
                # Catch the redirect and do nothing.
                pass
        if 'auth_tkt' not in [cookie.name for cookie in self._cookies.cookiejar]:
            raise OpsviewException('Login failed')

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
            'from':     self.base_url,
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
        """Send payload (a xml Node object) to the api url via POST."""

        return minidom.parse(self._send_post(OpsviewRemote.api_urls['api'],
            payload.toxml(), dict({'Content-Type':'text/xml'})))

    def _send_get(self, location, parameters=None, headers=None):
        request = urllib2.Request('%s?%s' % (self.base_url + location, parameters))
        if headers is not None:
            map(
                lambda header_key: request.add_header(header_key, headers[header_key]),
                headers
            )
        request.add_header('Content-Type', self._content_type)
        self.login()
        try:
            reply = self._opener.open(request)
        except urllib2.HTTPError, reply:
            return reply
        else:
            return reply

    def _send_post(self, location, data, headers=None):
        request = urllib2.Request(self.base_url + location, data)
        if headers is not None:
            map(
                lambda header_key: request.add_header(header_key, headers[header_key]),
                headers
            )
        self.login()
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
        raise OpsviewException('Service not found: %s.%s' % (host, service))

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
            (_dict_to_xml(attrs))))

    def clone_host(self, src_host_name, **attrs):
        """Create a new host by cloning an old one.

        Syntax is the same as create_host with the addition of the src_host_name
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
            (src_host_name, _dict_to_xml(attrs))))

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

    def schedule_downtime(self, hostgroup, start, end, comment):
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

class OpsviewNode(dict):
    """Basic Opsview node.

    All nodes require access to an OpsviewRemote, a node can get it's remote by
    at init either by passing an actual remote instance or just the login args
    to create one (base_url, username, and password). If either of those don't
    work out, the node will search upwards through the tree to find a node that
    does have a remote and will use the first one it finds. If it fails to find
    one after all that it will throw an OpsviewException.

    """
    def __init__(self, parent=None, remote=None, src=None, **remote_login):
        self.parent = parent
        self.children = None
        self.remote = remote

        if isinstance(remote, OpsviewRemote):
            self.remote = remote
        elif all(map(lambda x: x in remote_login, ['base_url', 'username', 'password'])):
            self.remote = OpsviewRemote(**remote_login)
        else:
            remote_search = self.parent
            while self.remote is None and remote_search is not None:
                self.remote = remote_search.remote
                remote_search = remote_search.parent
        if self.remote is None:
            raise OpsviewException('%s couldn\'t find a remote to use' %
                self)
        if src is not None:
            try:
                self.parse_xml(src)
            except AssertionError:
                try:
                    self.parse_json(src)
                except AssertionError:
                    raise OpsviewException('No handler for src format')

    def __str__(self):
        try:
            return '%s(%s)' % (self.__class__.__name__, self['name'])
        except KeyError:
            return '%s()' % (self.__class__.__name__)

    def update(self, filters=None):
        raise NotImplementedError()

    def parse_xml(self, src):
        if isinstance(src, basestring):
            src = minidom.parseString(src)
        elif isinstance(src, file):
            src = minidom.parse(src)
        assert isinstance(src, minidom.Node)

        if not (hasattr(src, 'tagName') and
            src.tagName == self.__class__.status_xml_element_name):
            src = src.getElementsByTagName(self.__class__.status_xml_element_name)[0]
        for i in range(src.attributes.length):
            try:
                self[src.attributes.item(i).name] = int(src.attributes.item(i).value)
            except ValueError:
                self[src.attributes.item(i).name] = src.attributes.item(i).value
        if self.__class__.child_type is not None:
            self.children = map(
                lambda node: self.__class__.child_type(parent=self, src=node, remote=self.remote),
                src.getElementsByTagName(self.__class__.child_type.status_xml_element_name)
            )

    def parse_json(self, src):
        if isinstance(src, basestring):
            src = json.loads(src)
        elif isinstance(src, file):
            src = json.load(src)
        assert isinstance(src, dict)

        if self.__class__.status_json_element_name in src:
            src = src[self.__class__.status_json_element_name]
        for item in filter(lambda item: isinstance(src[item], basestring), src):
            try:
                self[item] = int(src[item])
            except ValueError:
                self[item] = src[item]
        if self.__class__.child_type is not None:
            self.children = map(
                lambda node: self.__class__.child_type(parent=self, src=node, remote=self.remote),
                src[self.__class__.child_type.status_xml_element_name]
            )

    def to_xml(self):
        return _dict_to_xml(dict({self.__class__.status_xml_element_name:self}))

    def to_json(self):
        return json.dumps(self)

class OpsviewService(OpsviewNode):
    """Logical Opsview service node."""

    status_xml_element_name = 'services'
    status_json_element_name = 'services'
    child_type = None

    def update(self):
        self.parse_xml(self.remote.get_status_service(
            self.parent['name'],
            self['name']
        ))
        return self

class OpsviewHost(OpsviewNode):
    """Logical Opsview host node."""

    status_xml_element_name = 'list'
    status_json_element_name = 'list'
    child_type = OpsviewService

    def update(self, filters=None):
        self.parse_xml(self.remote.get_status_host(self['name'], filters))
        return self

class OpsviewServer(OpsviewNode):
    """Logical Opsview server node."""

    status_xml_element_name = 'data'
    status_json_element_name = 'service'
    child_type = OpsviewHost

    def update(self, filters=None):
        self.parse_xml(self.remote.get_status_all(filters))
        return self