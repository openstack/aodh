#
# Copyright 2024 Red Hat, Inc
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

import copy
import os
import webtest

from aodh.api import app
from aodh.storage import models
from aodh.tests import constants
from aodh.tests.functional.api import v2


def getTestAlarm(alarm_id, project_id, user_id):
    return models.Alarm(name='name1',
                        type='gnocchi_aggregation_by_metrics_threshold',
                        enabled=True,
                        alarm_id=alarm_id,
                        description='a',
                        state='insufficient data',
                        state_reason='Not evaluated',
                        severity='critical',
                        state_timestamp=constants.MIN_DATETIME,
                        timestamp=constants.MIN_DATETIME,
                        ok_actions=[],
                        insufficient_data_actions=[],
                        alarm_actions=[],
                        repeat_actions=True,
                        user_id=user_id,
                        project_id=project_id,
                        time_constraints=[dict(name='testcons',
                                               start='0 11 * * *',
                                               duration=300)],
                        rule=dict(comparison_operator='gt',
                                  threshold=2.0,
                                  aggregation_method='mean',
                                  evaluation_periods=60,
                                  granularity=1,
                                  metrics=[
                                      '41869681-5776-46d6-91ed-cccc43b6e4e3',
                                      'a1fb80f4-c242-4f57-87c6-68f47521059e'
                                  ])
                        )


class TestMetrics(v2.FunctionalTest):
    def setUp(self):
        super(TestMetrics, self).setUp()
        self.project_id = "some_project_id"
        self.project_id2 = "some_project_id2"
        self.alarm_id = "some_alarm_id"
        self.alarm_id2 = "some_alarm_id2"
        self.user_id = "some_user_id"
        self.role = "reader"
        self.auth_headers = {'X-User-Id': self.user_id,
                             'X-Project-Id': self.project_id,
                             'X-Roles': self.role}
        self.alarm_conn.create_alarm(getTestAlarm(
            self.alarm_id,
            self.project_id,
            self.user_id)
        )
        self.alarm_conn.create_alarm(getTestAlarm(
            self.alarm_id2,
            self.project_id2,
            self.user_id)
        )
        self.alarm_conn.increment_alarm_counter(
            self.alarm_id,
            self.project_id,
            "ok"
        )
        self.alarm_conn.increment_alarm_counter(
            self.alarm_id,
            self.project_id,
            "insufficient_data"
        )
        self.alarm_conn.increment_alarm_counter(
            self.alarm_id,
            self.project_id,
            "insufficient_data"
        )
        self.alarm_conn.increment_alarm_counter(
            self.alarm_id2,
            self.project_id2,
            "alarm"
        )

    def test_get_all_metrics_inside_project(self):
        expected = {
            "evaluation_results":
            [{
                "alarm_id": self.alarm_id,
                "project_id": self.project_id,
                "state_counters": {
                    "ok": 1,
                    "insufficient data": 2,
                    "alarm": 0
                }
            }]
        }
        metrics = self.get_json(
            '/metrics',
            headers=self.auth_headers,
        )
        self.assertEqual(expected, metrics)

    def test_get_all_metrics_forbidden(self):
        pf = os.path.abspath('aodh/tests/functional/api/v2/policy.yaml-test')
        self.CONF.set_override('policy_file', pf, group='oslo_policy')
        self.CONF.set_override('auth_mode', None, group='api')
        self.app = webtest.TestApp(app.load_app(self.CONF))

        response = self.get_json('/metrics',
                                 expect_errors=True,
                                 status=403,
                                 headers=self.auth_headers)
        faultstring = 'RBAC Authorization Failed'
        self.assertEqual(403, response.status_code)
        self.assertEqual(faultstring,
                         response.json['error_message']['faultstring'])

    def test_get_all_metrics_all_projects(self):
        auth_headers = copy.copy(self.auth_headers)
        auth_headers['X-Roles'] = 'admin'
        expected = {
            "evaluation_results": [{
                "alarm_id": self.alarm_id,
                "project_id": self.project_id,
                "state_counters": {
                    "ok": 1,
                    "insufficient data": 2,
                    "alarm": 0
                }
            }, {
                "alarm_id": self.alarm_id2,
                "project_id": self.project_id2,
                "state_counters": {
                    "ok": 0,
                    "insufficient data": 0,
                    "alarm": 1
                }
            }]
        }
        metrics = self.get_json(
            '/metrics?all_projects=true',
            headers=auth_headers,
        )
        self.assertEqual(expected, metrics)

    def test_get_all_metrics_all_projects_forbidden(self):
        pf = os.path.abspath('aodh/tests/functional/api/v2/policy.yaml-test')
        self.CONF.set_override('policy_file', pf, group='oslo_policy')
        self.CONF.set_override('auth_mode', None, group='api')
        self.app = webtest.TestApp(app.load_app(self.CONF))

        response = self.get_json('/metrics?all_projects=true',
                                 expect_errors=True,
                                 status=403,
                                 headers=self.auth_headers)
        faultstring = 'RBAC Authorization Failed'
        self.assertEqual(403, response.status_code)
        self.assertEqual(faultstring,
                         response.json['error_message']['faultstring'])
