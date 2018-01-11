#
# Copyright Ericsson AB 2013. All rights reserved
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
"""Tests complex queries for alarms
"""

import datetime

from oslo_utils import timeutils

from aodh.storage import models
from aodh.tests.functional.api import v2 as tests_api


admin_header = {"X-Roles": "admin",
                "X-Project-Id":
                "project-id1"}
non_admin_header = {"X-Roles": "Member",
                    "X-Project-Id":
                    "project-id1"}

RULE_TYPE = 'gnocchi_aggregation_by_metrics_threshold'


class TestQueryAlarmsController(tests_api.FunctionalTest):

    def setUp(self):
        super(TestQueryAlarmsController, self).setUp()
        self.alarm_url = '/query/alarms'

        for state in ['ok', 'alarm', 'insufficient data']:
            for date in [datetime.datetime(2013, 1, 1),
                         datetime.datetime(2013, 2, 2)]:
                for id in [1, 2]:
                    alarm_id = "-".join([state, date.isoformat(), str(id)])
                    project_id = "project-id%d" % id
                    alarm = models.Alarm(name=alarm_id,
                                         type=RULE_TYPE,
                                         enabled=True,
                                         alarm_id=alarm_id,
                                         description='a',
                                         state=state,
                                         state_reason="state_reason",
                                         state_timestamp=date,
                                         timestamp=date,
                                         ok_actions=[],
                                         insufficient_data_actions=[],
                                         alarm_actions=[],
                                         repeat_actions=True,
                                         user_id="user-id%d" % id,
                                         project_id=project_id,
                                         time_constraints=[],
                                         rule=dict(comparison_operator='gt',
                                                   threshold=2.0,
                                                   aggregation_method='mean',
                                                   evaluation_periods=60,
                                                   granularity=1,
                                                   metrics=[]),
                                         severity='critical')
                    self.alarm_conn.create_alarm(alarm)

    def test_query_all(self):
        data = self.post_json(self.alarm_url,
                              headers=admin_header,
                              params={})

        self.assertEqual(12, len(data.json))

    def test_filter_with_isotime_timestamp(self):
        date_time = datetime.datetime(2013, 1, 1)
        isotime = date_time.isoformat()

        data = self.post_json(self.alarm_url,
                              headers=admin_header,
                              params={"filter":
                                      '{">": {"timestamp": "'
                                      + isotime + '"}}'})

        self.assertEqual(6, len(data.json))
        for alarm in data.json:
            result_time = timeutils.parse_isotime(alarm['timestamp'])
            result_time = result_time.replace(tzinfo=None)
            self.assertGreater(result_time, date_time)

    def test_filter_with_isotime_state_timestamp(self):
        date_time = datetime.datetime(2013, 1, 1)
        isotime = date_time.isoformat()

        data = self.post_json(self.alarm_url,
                              headers=admin_header,
                              params={"filter":
                                      '{">": {"state_timestamp": "'
                                      + isotime + '"}}'})

        self.assertEqual(6, len(data.json))
        for alarm in data.json:
            result_time = timeutils.parse_isotime(alarm['state_timestamp'])
            result_time = result_time.replace(tzinfo=None)
            self.assertGreater(result_time, date_time)

    def test_non_admin_tenant_sees_only_its_own_project(self):
        data = self.post_json(self.alarm_url,
                              params={},
                              headers=non_admin_header)
        for alarm in data.json:
            self.assertEqual("project-id1", alarm['project_id'])

    def test_non_admin_tenant_cannot_query_others_project(self):
        data = self.post_json(self.alarm_url,
                              params={"filter":
                                      '{"=": {"project_id": "project-id2"}}'},
                              expect_errors=True,
                              headers=non_admin_header)

        self.assertEqual(401, data.status_int)
        self.assertIn(b"Not Authorized to access project project-id2",
                      data.body)

    def test_non_admin_tenant_can_explicitly_filter_for_own_project(self):
        data = self.post_json(self.alarm_url,
                              params={"filter":
                                      '{"=": {"project_id": "project-id1"}}'},
                              headers=non_admin_header)

        for alarm in data.json:
            self.assertEqual("project-id1", alarm['project_id'])

    def test_admin_tenant_sees_every_project(self):
        data = self.post_json(self.alarm_url,
                              params={},
                              headers=admin_header)

        self.assertEqual(12, len(data.json))
        for alarm in data.json:
            self.assertIn(alarm['project_id'],
                          (["project-id1", "project-id2"]))

    def test_admin_tenant_can_query_any_project(self):
        data = self.post_json(self.alarm_url,
                              params={"filter":
                                      '{"=": {"project_id": "project-id2"}}'},
                              headers=admin_header)

        self.assertEqual(6, len(data.json))
        for alarm in data.json:
            self.assertIn(alarm['project_id'], set(["project-id2"]))

    def test_query_with_field_project(self):
        data = self.post_json(self.alarm_url,
                              headers=admin_header,
                              params={"filter":
                                      '{"=": {"project": "project-id2"}}'})

        self.assertEqual(6, len(data.json))
        for alarm_item in data.json:
            self.assertIn(alarm_item['project_id'], set(["project-id2"]))

    def test_query_with_field_user_in_orderby(self):
        data = self.post_json(self.alarm_url,
                              headers=admin_header,
                              params={"filter": '{"=": {"state": "alarm"}}',
                                      "orderby": '[{"user": "DESC"}]'})

        self.assertEqual(4, len(data.json))
        self.assertEqual(["user-id2", "user-id2", "user-id1", "user-id1"],
                         [s["user_id"] for s in data.json])

    def test_query_with_filter_orderby_and_limit(self):
        orderby = '[{"state_timestamp": "DESC"}]'
        data = self.post_json(self.alarm_url,
                              headers=admin_header,
                              params={"filter": '{"=": {"state": "alarm"}}',
                                      "orderby": orderby,
                                      "limit": 3})

        self.assertEqual(3, len(data.json))
        self.assertEqual(["2013-02-02T00:00:00",
                          "2013-02-02T00:00:00",
                          "2013-01-01T00:00:00"],
                         [a["state_timestamp"] for a in data.json])
        for alarm in data.json:
            self.assertEqual("alarm", alarm["state"])

    def test_query_with_orderby_severity(self):
        if self.engine != "mysql":
            self.skipTest("This is only implemented for MySQL")
        orderby = '[{"severity": "ASC"}]'
        data = self.post_json(self.alarm_url,
                              headers=admin_header,
                              params={"orderby": orderby})
        alarms = list(data.json)
        severities = [a['severity'] for a in alarms]
        severity_choices = ['low', 'moderate', 'critical']
        sorted_severities = sorted(severities, key=severity_choices.index)
        self.assertEqual(sorted_severities, severities)

        orderby = '[{"severity": "DESC"}]'
        data = self.post_json(self.alarm_url,
                              headers=admin_header,
                              params={"orderby": orderby})
        alarms = list(data.json)
        severities = [a['severity'] for a in alarms]
        sorted_severities = sorted(severities, key=severity_choices.index,
                                   reverse=True)
        self.assertEqual(sorted_severities, severities)

    def test_limit_should_be_positive(self):
        data = self.post_json(self.alarm_url,
                              headers=admin_header,
                              params={"limit": 0},
                              expect_errors=True)

        self.assertEqual(400, data.status_int)
        self.assertIn(b"Limit should be positive", data.body)


class TestQueryAlarmsHistoryController(tests_api.FunctionalTest):

    def setUp(self):
        super(TestQueryAlarmsHistoryController, self).setUp()
        self.url = '/query/alarms/history'
        for id in [1, 2]:
            for type in ["creation", "state transition"]:
                for date in [datetime.datetime(2013, 1, 1),
                             datetime.datetime(2013, 2, 2)]:
                    event_id = "-".join([str(id), type, date.isoformat()])
                    alarm_change = {"event_id": event_id,
                                    "alarm_id": "alarm-id%d" % id,
                                    "type": type,
                                    "detail": "",
                                    "user_id": "user-id%d" % id,
                                    "project_id": "project-id%d" % id,
                                    "on_behalf_of": "project-id%d" % id,
                                    "timestamp": date}

                    self.alarm_conn.record_alarm_change(alarm_change)

    def test_query_all(self):
        data = self.post_json(self.url,
                              headers=admin_header,
                              params={})

        self.assertEqual(8, len(data.json))

    def test_filter_with_isotime(self):
        date_time = datetime.datetime(2013, 1, 1)
        isotime = date_time.isoformat()

        data = self.post_json(self.url,
                              headers=admin_header,
                              params={"filter":
                                      '{">": {"timestamp":"'
                                      + isotime + '"}}'})

        self.assertEqual(4, len(data.json))
        for history in data.json:
            result_time = timeutils.parse_isotime(history['timestamp'])
            result_time = result_time.replace(tzinfo=None)
            self.assertGreater(result_time, date_time)

    def test_non_admin_tenant_sees_only_its_own_project(self):
        data = self.post_json(self.url,
                              params={},
                              headers=non_admin_header)
        for history in data.json:
            self.assertEqual("project-id1", history['on_behalf_of'])

    def test_non_admin_tenant_cannot_query_others_project(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"on_behalf_of":'
                                      + ' "project-id2"}}'},
                              expect_errors=True,
                              headers=non_admin_header)

        self.assertEqual(401, data.status_int)
        self.assertIn(b"Not Authorized to access project project-id2",
                      data.body)

    def test_non_admin_tenant_can_explicitly_filter_for_own_project(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"on_behalf_of":'
                                      + ' "project-id1"}}'},
                              headers=non_admin_header)

        for history in data.json:
            self.assertEqual("project-id1", history['on_behalf_of'])

    def test_admin_tenant_sees_every_project(self):
        data = self.post_json(self.url,
                              params={},
                              headers=admin_header)

        self.assertEqual(8, len(data.json))
        for history in data.json:
            self.assertIn(history['on_behalf_of'],
                          (["project-id1", "project-id2"]))

    def test_query_with_filter_for_project_orderby_with_user(self):
        data = self.post_json(self.url,
                              headers=admin_header,
                              params={"filter":
                                      '{"=": {"project": "project-id1"}}',
                                      "orderby": '[{"user": "DESC"}]',
                                      "limit": 3})

        self.assertEqual(3, len(data.json))
        self.assertEqual(["user-id1",
                          "user-id1",
                          "user-id1"],
                         [h["user_id"] for h in data.json])
        for history in data.json:
            self.assertEqual("project-id1", history['project_id'])

    def test_query_with_filter_orderby_and_limit(self):
        data = self.post_json(self.url,
                              headers=admin_header,
                              params={"filter": '{"=": {"type": "creation"}}',
                                      "orderby": '[{"timestamp": "DESC"}]',
                                      "limit": 3})

        self.assertEqual(3, len(data.json))
        self.assertEqual(["2013-02-02T00:00:00",
                          "2013-02-02T00:00:00",
                          "2013-01-01T00:00:00"],
                         [h["timestamp"] for h in data.json])
        for history in data.json:
            self.assertEqual("creation", history['type'])

    def test_limit_should_be_positive(self):
        data = self.post_json(self.url,
                              params={"limit": 0},
                              headers=admin_header,
                              expect_errors=True)

        self.assertEqual(400, data.status_int)
        self.assertIn(b"Limit should be positive", data.body)
