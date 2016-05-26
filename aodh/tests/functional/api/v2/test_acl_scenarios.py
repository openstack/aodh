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

import mock
import webtest

from aodh.api import app
from aodh.tests.functional.api import v2


class TestAPIACL(v2.FunctionalTest):

    def _make_app(self):
        file_name = self.path_get('etc/aodh/api_paste.ini')
        self.CONF.set_override("paste_config", file_name, "api")
        # We need the other call to prepare_service in app.py to return the
        # same tweaked conf object.
        with mock.patch('aodh.service.prepare_service') as ps:
            ps.return_value = self.CONF
            return webtest.TestApp(app.load_app(conf=self.CONF))

    def test_non_authenticated(self):
        response = self.get_json('/alarms', expect_errors=True)
        self.assertEqual(401, response.status_int)

    def test_authenticated_wrong_role(self):
        response = self.get_json('/alarms',
                                 expect_errors=True,
                                 headers={
                                     "X-Roles": "Member",
                                     "X-Tenant-Name": "admin",
                                     "X-Project-Id":
                                     "bc23a9d531064583ace8f67dad60f6bb",
                                 })
        self.assertEqual(401, response.status_int)
