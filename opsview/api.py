#!/usr/bin/env python

import requests
import json

class RestApiException(Exception):
    pass

class RestApi(RestPathProxy):
    _request_headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    _username = None
    _auth_token = None
    _parent = None
    _name = 'rest'

    def __init__(self, base_url):
        self._base_url = base_url.rstrip('/')
        self._comm = requests.session()

    def authenticate(self, username, password):
        self._username = username
        self._auth_token = self.login.post(username=username, password=password)['token']

    def _do_request(self, path, method, data=None):
        url = self._base_url + path
        headers = self._request_headers
        if self._auth_token is not None:
            headers = headers.update({
                'X-Opsview-Username': self._username,
                'X-Opsview-Token': self._auth_token,
            })
        request_data = {'headers': headers}
        if data is not None:
            request_data.update(data=json.dumps(data))
        result = getattr(self._comm, method)(path, **request_data)
        return self._handle_result(result)

    def _handle_result(self, result):
        if result.status_code != requests.codes.ok:
            #api error
            raise RestApiException(result)
        else:
            return json.loads(result.text)

class RestPathProxy(object):
    _request_methods = ['get', 'post', 'put', 'delete']

    def __init__(self, parent, name):
        self._name = name
        self._parent = parent

    def __getattr__(self, name):
        if name in self._request_methods:
            return lambda **kwargs: self.get_root()._do_request(
                self.get_path(), name, kwargs)
        else:
            return RestPathProxy(self, name)

    def __call__(self, **kwargs):
        return self.get(**kwargs)

    def get_path(self):
        if self._parent is not None:
            return '%s/%s' % (self._parent.get_path(), self._name)
        else:
            return '/' + self._name

    def get_root(self):
        node = self
        while node._parent is not None
            node = node._parent
        return node

if __name__ == '__main__':
    import sys
    base_url = sys.argv[1]
    method = sys.argv[2]
    data = dict(param.split('=', 1) for param in sys.argv[4:] if '=' in param)
    print getattr(getattr(RestApi(base_url), sys.argv[3]), method)(**data)
