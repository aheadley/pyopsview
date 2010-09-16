#!/usr/bin/env python

from urllib import urlencode, quote_plus
import urllib2
import xml.dom.minidom as minidom
from xml.parsers.expat import ExpatError
try:
    import json
except ImportError:
    # The json module was added in Python 2.6
    json = None
	
if not hasattr(__builtins__, 'all'):
    # all was added in Python 2.5
    def all(target):
        for item in target:
            if not item:
                return False
        return True
if not hasattr(__builtins__, 'any'):
    # any was added in Python 2.5
    def any(target):
        for item in target:
            if item:
                return True
        return False

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
        if msg is None:
            self.msg = 'Unknown Error'
        else:
            self.msg = msg
    def __str__(self):
        return 'Error: %s' % self.msg
    def __repr__(self):
        return str(self)
class OpsviewParseException(OpsviewException):
    parse_text_length_limit = 45
    def __init__(self, msg, text):
        super(OpsviewParseException, self).__init__(msg)
        self.parse_text = text
    def __str__(self):
        if len(self.parse_text) > self.__class__.msg_length_limit:
            text = self.parse_text[:45] + '...'
        else:
            text = self.parse_text
        return 'Error parsing "%s": %s' % (text, self.msg)
class OpsviewLogicException(OpsviewException):
    def __str__(self):
        return 'Logic Error: %s' % self.msg
class OpsviewHTTPException(OpsviewException):
    def __str__(self):
        return 'HTTP Error: %s' % self.msg
class OpsviewAttributeException(OpsviewException):
    def __str__(self):
        return 'Invalid or unknown attribute: %s' % self.msg
class OpsviewValueException(OpsviewException):
    def __init__(self, value_name, value):
        self.value_name = value_name
        self.value = value
    def __str__(self):
        return 'Invalid value: "%s" as %s' % (self.value, self.value_name)

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
        return '%s(%s)' % (self.__class__.__name__, self.base_url)

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
            except urllib2.HTTPError, error:
                raise OpsviewHTTPException(error)
        if 'auth_tkt' not in [cookie.name for cookie in self._cookies.cookiejar]:
            raise OpsviewHTTPException('Login failed')

    def _acknowledge(self, targets, comment='', notify=True, auto_remove_comment=True):
        """Send acknowledgements for each target in targets.
        
        Targets should be a dict with this layout:
        targets=dict({
            host1:[list, of, services],
            host2:[another, list, None], #None means acknowledge the host itself
        })

        """
        
        if notify:
            notify = 'on'
        else:
            notify = 'off'
        if auto_remove_comment:
            auto_remove_comment = 'on'
        else:
            auto_remove_comment = 'off'

        data = urlencode(dict({
            'from':     self.base_url,
            'submit':   'Submit',
            'comment':  comment,
            'notify':   notify,
            'autoremovecomment':
                        auto_remove_comment,
        }))
        # Construct the hosts and services to acknowledge parameters.
        data += '&' + '&'.join([(service and 'service_selection=%s' %
            quote_plus('%s;%s' % (host, service))) or
            'host_selection=%s' % quote_plus(host)
            for host in targets for service in targets[host]])

        return self._send_post(OpsviewRemote.api_urls['acknowledge'], data)

    def _send_xml(self, payload):
        """Send payload (a xml Node object) to the api url via POST."""

        try:
            if isinstance(payload, basestring):
                payload = minidom.parseString(payload)
            elif isinstance(payload, file):
                payload = minidom.parse(payload)
            assert isinstance(payload, minidom.Node)
        except (AssertionError, ExpatError):
            raise OpsviewHTTPException('Invalid XML payload')
        response = send_post(OpsviewRemote.api_urls['api'],
                payload.toxml(), dict({'Content-Type':'text/xml'}))
        try:
            response = minidom.parse(response)
        except ExpatError:
            raise OpsviewHTTPException('Recieved non-XML response from Opsview server')
        return response

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
        except urllib2.HTTPError, error:
            raise OpsviewHTTPException(error)
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
        except urllib2.HTTPError, error:
            raise OpsviewHTTPException(error)
        return reply

    def get_status_all(self, filters=None):
        """Get status of all services.

        Optionally filter the results with a list of filters from
        OpsviewRemote.filters

        """

        try:
            filters = [OpsviewRemote.filters[filter] for filter in filters]
        except TypeError:
            filters = []
        try:
            return minidom.parse(self._send_get(
                OpsviewRemote.api_urls['status_all'],
                urlencode(filters)
            ))
        except ExpatError:
            raise OpsviewHTTPException('Recieved invalid status XML')

    def get_status_host(self, host, filters=None):
        """Get status of a host and all its services.
        
        Optionally filter the results with a list of filters from
        OpsviewRemote.filters
        
        """

        try:
            filters = [OpsviewRemote.filters[filter] for filter in filters]
        except TypeError:
            filters = []
        filters.append(('host', host))
        try:
            return minidom.parse(self._send_get(
                OpsviewRemote.api_urls['status_host'],
                urlencode(filters)
            ))
        except ExpatError:
            raise OpsviewHTTPException('Recieved invalid status XML')

    def get_status_service(self, host, service):
        """Get status of a host's service."""

        host_xml = self.get_status_host(host)
        services = host_xml.getElementsByTagName('services')
        for node in services:
            if node.getAttribute('name').lower() == service.lower():
                return node
        # This behavior is inconsistent with get_status_host and should be fixed.
        raise OpsviewAttributeException('service')

    def get_status_by_hostgroup(self, hostgroup, filters=None):
        """Get status of the hosts in a hostgroup..

        Optionally filter the results with a list of filters from
        OpsviewRemote.filters

        """

        try:
            filters = [OpsviewRemote.filters[filter] for filter in filters]
        except TypeError:
            filters = []
        filters.append(('hostgroupid', int(hostgroup)))
        return minidom.parse(self._send_get(
            OpsviewRemote.api_urls['status_host'],
            urlencode(filters)
        ))

    def get_status_hostgroup(self, hostgroup=None):
        """Get of a top-level hostgroup or all top-level hostgroups."""

        if hostgroup is None:
            hostgroup = ''

        try:
            return minidom.parse(self._send_get('%s/%s' %
                (OpsviewRemote.api_urls['status_hostgroup'], hostgroup)))
        except ExpatError:
            raise OpsviewHTTPException('Recieved invalid status XML')

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

        status = self.get_status_all(['warning', 'critical', 'unhandled'])
        alerting = dict({})
        # These two loops can probably stand to be cleaned up a bit.
        for host in status.getElementsByTagName('list'):
            alerting[host.getAttribute('name')] = []
            if int(host.getAttribute('current_check_attempt')) == \
                int(host.getAttribute('max_check_attempts')):
                alerting[host.getAttribute('name')].append(None)
            for service in host.getElementsByTagName('services'):
                if int(service.getAttribute('current_check_attempt')) == \
                    int(service.getAttribute('max_check_attempts')):
                    alerting[host.getAttribute('name')].append(service.getAttribute('name'))
        return self._acknowledge(alerting, comment, notify, auto_remove_comment)

    def create_host(self, **attrs):
        """Create a new host.

        The new host's attributes are passed as as arbitrary keyword arguments.
        The only values checked for are 'name' and 'ip' as they are required by
        Opsview.

        """

        required_attrs = ['name', 'ip']
        if not all(map(lambda attr: attr in attrs, required_attrs)):
            raise OpsviewAttributeException(
                ', '.join(filter(lambda attr: attr not in attrs, required_attrs)))
        xml = """<opsview>
            <host action="create">
                %s
            </host>
        </opsview>"""

        return self._send_xml(xml % _dict_to_xml(attrs))

    def clone_host(self, src_host_name, **attrs):
        """Create a new host by cloning an old one.

        Syntax is the same as create_host with the addition of the src_host_name
        argument that selects the host to clone from.

        """

        required_attrs = ['name', 'ip']
        if not all(map(lambda attr: attr in attrs, required_attrs)):
            raise OpsviewAttributeException(
                ', '.join(filter(lambda attr: attr not in attrs, required_attrs)))
        xml = """<opsview>
            <host action="create">
                <clone>
                    <name>%s</name>
                </clone>
                %s
            </host>
        </opsview>"""

        return self._send_xml(xml % (src_host_name, _dict_to_xml(attrs)))

    def delete_host(self, host):
        """Delete a host by name or ID number."""

        xml = """<opsview>
            <host action="delete" by_%s="%s"/>
        </opsview>"""

        if host.isdigit():
            method = 'id'
        else:
            method = 'name'

        return self._send_xml(xml % (method, host))

    def schedule_downtime(self, hostgroup, start, end, comment):
        """Schedule downtime for a leaf hostgroup by id or name."""

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

        if hostgroup.isdigit():
            method = 'id'
        else:
            method = 'name'

        return self._send_xml(xml %
            (method, hostgroup, start, end, comment))

    def disable_scheduled_downtime(self, hostgroup):
        """Cancel downtime for a leaf hostgroup by id or name."""

        xml = """<opsview>
            <hostgroup action="change" by_%s="%s">
                <downtime>disable</downtime>
            </hostgroup>
        </opsview>"""

        if hostgroup.isdigit():
            method = 'id'
        else:
            method = 'name'

        return self._send_xml(xml % (method, hostgroup))

    def enable_notifications(self, hostgroup):
    	"""Enable notifications for a leaf hostgroup by id or name."""

        xml = """<opsview>
            <hostgroup action="change" by_%s="%s">
                <notifications>enable</notifications>
            </hostgroup>
        </opsview>"""

        if hostgroup.isdigit():
            method = 'id'
        else:
            method = 'name'

        return self._send_xml(xml % (method, hostgroup))

    def disable_notifications(self, hostgroup):
    	"""Disable notifications for a leaf hostgroup by id or name."""
    	
        xml = """<opsview>
            <hostgroup action="change" by_%s="%s">
                <notifications>disable</notifications>
            </hostgroup>
        </opsview>"""

        if hostgroup.isdigit():
            method = 'id'
        else:
            method = 'name'

        return self._send_xml(xml % (method, hostgroup))

    def reload(self):
        """Reload the remote Opsview server's configuration."""

        xml = """<opsview>
            <system action="reload"/>
        </opsview>"""

        return self._send_xml(xml)

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
        elif all(map(lambda attr: attr in remote_login, ['base_url', 'username', 'password'])):
            self.remote = OpsviewRemote(**remote_login)
        else:
            remote_search = self.parent
            while self.remote is None and remote_search is not None:
                self.remote = remote_search.remote
                remote_search = remote_search.parent
        if self.remote is None:
            raise OpsviewLogicException('Unable to find OpsviewRemote for %s' %
                self)
        if src is not None:
            self.parse(src)

    def __str__(self):
        try:
            return self['name']
        except KeyError:
            return self.__class__.__name__

    def __repr__(self):
        try:
            return '%s(%s)' % (self.__class__.__name__, self['name'])
        except KeyError:
            return '%s()' % self.__class__.__name__

    def append_child(self, child_src):
        try:
            self.children.append(
                self.__class__.child_type(
                    parent=self,
                    src=child_src,
                    remote=self.remote))
        except TypeError:
            # self.__class__.child_type is None
            raise OpsviewLogicException('%s cannot have children' %
                self.__class__.__name__)

    def update(self, filters=None):
        raise NotImplementedError()

    def parse(self, src):
        try:
            self.parse_xml(src)
        except OpsviewParseException:
            try:
                self.parse_json(src)
            except OpsviewParseException:
                raise OpsviewParseException('No handler for source format', src)

    def parse_xml(self, src):
        try:
            if isinstance(src, basestring):
                src = minidom.parseString(src)
            elif isinstance(src, file):
                src = minidom.parse(src)
            assert isinstance(src, minidom.Node)
        except (ExpatError, AssertionError):
            raise OpsviewParseException('Failed to parse XML source', src)
        

        if not (hasattr(src, 'tagName') and
            src.tagName == self.__class__.status_xml_element_name):
            src = src.getElementsByTagName(self.__class__.status_xml_element_name)[0]
        for i in range(src.attributes.length):
            try:
                self[src.attributes.item(i).name] = int(src.attributes.item(i).value)
            except ValueError:
                self[src.attributes.item(i).name] = src.attributes.item(i).value

        self.children = []
            # This may cause a memory leak if Python doesn't properly garbage
            #  collect the released objects.
        try:
            map(
                self.append_child,
                src.getElementsByTagName(
                    self.__class__.child_type.status_xml_element_name)
            )
        except (OpsviewLogicException, AttributeError):
            if self.__class__.child_type is not None:
                raise OpsviewParseException('Invalid source structure', '')


    if json is not None:
        def parse_json(self, src):
            try:
                if isinstance(src, basestring):
                    src = json.loads(src)
                elif isinstance(src, file):
                    src = json.load(src)
                assert isinstance(src, dict)
            except (ValueError, AssertionError):
                raise OpsviewParseException('Failed to parse JSON source', src)

            if self.__class__.status_json_element_name in src:
                src = src[self.__class__.status_json_element_name]
            for item in filter(lambda item: isinstance(src[item], basestring), src):
                try:
                    self[item] = int(src[item])
                except ValueError:
                    self[item] = src[item]
            self.children = []
            try:
                map(
                    self.append_child,
                    src[self.__class__.child_type.status_json_element_name]
                )
            except (OpsviewLogicException, AttributeError):
                if self.__class__.child_type is not None:
                    raise OpsviewParseException('Invalid source structure', src)

    def to_xml(self):
        return _dict_to_xml(dict({self.__class__.status_xml_element_name:self}))
    
    if json is not None:
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

class OpsviewHostgroup(OpsviewServer):
    """Logical Opsview Hostgroup node."""

    def __init__(self, parent=None, remote=None, src=None, id=None, **remote_login):
        try:
            self.id = int(id)
            assert self.id >= 0
        except (ValueError, AssertionError):
            raise OpsviewValueException('id', id)
        super(OpsviewHostgroup, self).__init__(parent, remote, src, **remote_login)

    def update(self, filters=None):
        self.parse_xml(
            self.remote.get_status_by_hostgroup(self.id, filters))
        return self