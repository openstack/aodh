#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2015 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""Test ACL."""

import datetime
import hashlib
import json

import mock
from oslo_utils import timeutils
import webtest

from aodh.api import app
from aodh.tests.api import v2
from aodh.tests import db as tests_db

VALID_TOKEN = '4562138218392831'
VALID_TOKEN2 = '4562138218392832'


class FakeMemcache(object):

    TOKEN_HASH = hashlib.sha256(VALID_TOKEN.encode('utf-8')).hexdigest()
    TOKEN2_HASH = hashlib.sha256(VALID_TOKEN2.encode('utf-8')).hexdigest()

    def get(self, key):
        if (key == "tokens/%s" % VALID_TOKEN or
                key == "tokens/%s" % self.TOKEN_HASH):
            dt = timeutils.utcnow() + datetime.timedelta(minutes=5)
            return json.dumps(({'access': {
                'token': {'id': VALID_TOKEN,
                          'expires': timeutils.isotime(dt)},
                'user': {
                    'id': 'user_id1',
                    'name': 'user_name1',
                    'tenantId': '123i2910',
                    'tenantName': 'mytenant',
                    'roles': [
                        {'name': 'admin'},
                    ]},
            }}, timeutils.isotime(dt)))
        if (key == "tokens/%s" % VALID_TOKEN2 or
                key == "tokens/%s" % self.TOKEN2_HASH):
            dt = timeutils.utcnow() + datetime.timedelta(minutes=5)
            return json.dumps(({'access': {
                'token': {'id': VALID_TOKEN2,
                          'expires': timeutils.isotime(dt)},
                'user': {
                    'id': 'user_id2',
                    'name': 'user-good',
                    'tenantId': 'project-good',
                    'tenantName': 'goodies',
                    'roles': [
                        {'name': 'Member'},
                    ]},
            }}, timeutils.isotime(dt)))

    @staticmethod
    def set(key, value, **kwargs):
        pass


class TestAPIACL(v2.FunctionalTest,
                 tests_db.MixinTestsWithBackendScenarios):

    def setUp(self):
        super(TestAPIACL, self).setUp()
        self.environ = {'fake.cache': FakeMemcache()}

    def get_json(self, path, expect_errors=False, headers=None,
                 q=None, **params):
        return super(TestAPIACL, self).get_json(path,
                                                expect_errors=expect_errors,
                                                headers=headers,
                                                q=q or [],
                                                extra_environ=self.environ,
                                                **params)

    def _make_app(self):
        self.CONF.set_override("cache", "fake.cache", 'keystone_authtoken')
        file_name = self.path_get('etc/aodh/api_paste.ini')
        self.CONF.set_override("api_paste_config", file_name)
        # We need the other call to prepare_service in app.py to return the
        # same tweaked conf object.
        with mock.patch('aodh.service.prepare_service') as ps:
            ps.return_value = self.CONF
            return webtest.TestApp(app.load_app(conf=self.CONF))

    def test_non_authenticated(self):
        response = self.get_json('/meters', expect_errors=True)
        self.assertEqual(401, response.status_int)

    def test_authenticated_wrong_role(self):
        response = self.get_json('/meters',
                                 expect_errors=True,
                                 headers={
                                     "X-Roles": "Member",
                                     "X-Tenant-Name": "admin",
                                     "X-Project-Id":
                                     "bc23a9d531064583ace8f67dad60f6bb",
                                 })
        self.assertEqual(401, response.status_int)
