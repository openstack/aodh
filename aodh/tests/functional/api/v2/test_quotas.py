# Copyright 2020 Catalyst Cloud LTD.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
import copy

from oslo_utils import uuidutils

from aodh.tests.functional.api import v2


class TestQuotas(v2.FunctionalTest):
    @classmethod
    def setUpClass(cls):
        super(TestQuotas, cls).setUpClass()

        cls.project = uuidutils.generate_uuid()
        cls.user = uuidutils.generate_uuid()
        cls.auth_headers = {'X-User-Id': cls.user, 'X-Project-Id': cls.project}
        cls.other_project = uuidutils.generate_uuid()

    def test_get_quotas_by_user(self):
        resp = self.get_json('/quotas', headers=self.auth_headers, status=200)

        self.assertEqual(self.project, resp.get('project_id'))
        self.assertGreater(len(resp.get('quotas', [])), 0)

    def test_get_project_quotas_by_user(self):
        resp = self.get_json('/quotas?project_id=%s' % self.project,
                             headers=self.auth_headers, status=200)

        self.assertEqual(self.project, resp.get('project_id'))
        self.assertGreater(len(resp.get('quotas', [])), 0)

    def test_get_other_project_quotas_by_user_failed(self):
        self.get_json(
            '/quotas?project_id=%s' % self.other_project,
            headers=self.auth_headers,
            expect_errors=True,
            status=401
        )

    def test_get_project_quotas_by_admin(self):
        auth_headers = copy.copy(self.auth_headers)
        auth_headers['X-Roles'] = 'admin'

        resp = self.get_json('/quotas?project_id=%s' % self.other_project,
                             headers=auth_headers,
                             status=200)

        self.assertEqual(self.other_project, resp.get('project_id'))
        self.assertGreater(len(resp.get('quotas', [])), 0)

    def test_post_quotas_by_admin(self):
        auth_headers = copy.copy(self.auth_headers)
        auth_headers['X-Roles'] = 'admin'

        resp = self.post_json(
            '/quotas',
            {
                "project_id": self.other_project,
                "quotas": [
                    {
                        "resource": "alarms",
                        "limit": 30
                    }
                ]
            },
            headers=auth_headers,
            status=201
        )
        resp_json = resp.json

        self.assertEqual(self.other_project, resp_json.get('project_id'))
        self.assert_single_item(resp_json.get('quotas', []), resource='alarms',
                                limit=30)

    def test_post_quotas_by_user_failed(self):
        self.post_json(
            '/quotas',
            {
                "project_id": self.other_project,
                "quotas": [
                    {
                        "resource": "alarms",
                        "limit": 20
                    }
                ]
            },
            headers=self.auth_headers,
            expect_errors=True,
            status=403
        )

    def test_post_quotas_no_limit_failed(self):
        auth_headers = copy.copy(self.auth_headers)
        auth_headers['X-Roles'] = 'admin'

        resp = self.post_json(
            '/quotas',
            {
                "project_id": self.project,
                "quotas": [
                    {
                        "resource": "alarms"
                    }
                ]
            },
            headers=auth_headers,
            expect_errors=True,
            status=400
        )

        self.assertIn('Mandatory field missing',
                      resp.json['error_message']['faultstring'])

    def test_post_quotas_no_resource_failed(self):
        auth_headers = copy.copy(self.auth_headers)
        auth_headers['X-Roles'] = 'admin'

        resp = self.post_json(
            '/quotas',
            {
                "project_id": self.project,
                "quotas": [
                    {
                        "limit": 1
                    }
                ]
            },
            headers=auth_headers,
            expect_errors=True,
            status=400
        )

        self.assertIn('Mandatory field missing',
                      resp.json['error_message']['faultstring'])

    def test_post_quotas_wrong_limit_failed(self):
        auth_headers = copy.copy(self.auth_headers)
        auth_headers['X-Roles'] = 'admin'

        resp = self.post_json(
            '/quotas',
            {
                "project_id": self.project,
                "quotas": [
                    {
                        "resource": "alarms",
                        "limit": -5
                    }
                ]
            },
            headers=auth_headers,
            expect_errors=True,
            status=400
        )

        self.assertIn('Value should be greater or equal to -1',
                      resp.json['error_message']['faultstring'])

    def test_post_quotas_unsupported_resource_failed(self):
        auth_headers = copy.copy(self.auth_headers)
        auth_headers['X-Roles'] = 'admin'

        resp = self.post_json(
            '/quotas',
            {
                "project_id": self.project,
                "quotas": [
                    {
                        "resource": "other_resource",
                        "limit": 1
                    }
                ]
            },
            headers=auth_headers,
            expect_errors=True,
            status=400
        )

        self.assertIn('Value should be one of',
                      resp.json['error_message']['faultstring'])

    def test_delete_project_quota_by_admin(self):
        auth_headers = copy.copy(self.auth_headers)
        auth_headers['X-Roles'] = 'admin'

        self.post_json(
            '/quotas',
            {
                "project_id": self.other_project,
                "quotas": [
                    {
                        "resource": "alarms",
                        "limit": 30
                    }
                ]
            },
            headers=auth_headers,
            status=201
        )

        resp = self.get_json('/quotas?project_id=%s' % self.other_project,
                             headers=auth_headers,
                             status=200)
        self.assert_single_item(resp['quotas'], resource='alarms',
                                limit=30)

        self.delete('/quotas/%s' % self.other_project, headers=auth_headers,
                    status=204)

        resp = self.get_json('/quotas?project_id=%s' % self.other_project,
                             headers=auth_headers,
                             status=200)
        self.assert_multiple_items(resp['quotas'], 0, resource='alarms',
                                   limit=30)

    def test_delete_project_quota_by_user_failed(self):
        self.delete('/quotas/%s' % self.other_project,
                    headers=self.auth_headers,
                    expect_errors=True,
                    status=403)
