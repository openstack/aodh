#
# Copyright 2013 eNovance <licensing@enovance.com>
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
"""Tests alarm operation."""

import copy
import datetime
import json as jsonlib
import operator
import os
from unittest import mock

import fixtures
from oslo_utils import uuidutils
import webtest

from aodh.api import app
from aodh import messaging
from aodh.storage import models
from aodh.tests import constants
from aodh.tests.functional.api import v2


RULE_KEY = 'gnocchi_aggregation_by_metrics_threshold_rule'


def default_alarms(auth_headers):
    return [models.Alarm(name='name1',
                         type='gnocchi_aggregation_by_metrics_threshold',
                         enabled=True,
                         alarm_id='a',
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
                         user_id=auth_headers['X-User-Id'],
                         project_id=auth_headers['X-Project-Id'],
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
                         ),
            models.Alarm(name='name2',
                         type='gnocchi_aggregation_by_metrics_threshold',
                         enabled=True,
                         alarm_id='b',
                         description='b',
                         state='insufficient data',
                         state_reason='Not evaluated',
                         severity='critical',
                         state_timestamp=constants.MIN_DATETIME,
                         timestamp=constants.MIN_DATETIME,
                         ok_actions=[],
                         insufficient_data_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         user_id=auth_headers['X-User-Id'],
                         project_id=auth_headers['X-Project-Id'],
                         time_constraints=[],
                         rule=dict(comparison_operator='gt',
                                   threshold=4.0,
                                   aggregation_method='mean',
                                   evaluation_periods=60,
                                   granularity=1,
                                   metrics=[
                                       '41869681-5776-46d6-91ed-cccc43b6e4e3',
                                       'a1fb80f4-c242-4f57-87c6-68f47521059e'
                                   ])
                         ),
            models.Alarm(name='name3',
                         type='gnocchi_aggregation_by_metrics_threshold',
                         enabled=True,
                         alarm_id='c',
                         description='c',
                         state='insufficient data',
                         state_reason='Not evaluated',
                         severity='moderate',
                         state_timestamp=constants.MIN_DATETIME,
                         timestamp=constants.MIN_DATETIME,
                         ok_actions=[],
                         insufficient_data_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         user_id=auth_headers['X-User-Id'],
                         project_id=auth_headers['X-Project-Id'],
                         time_constraints=[],
                         rule=dict(comparison_operator='gt',
                                   threshold=3.0,
                                   aggregation_method='mean',
                                   evaluation_periods=60,
                                   granularity=1,
                                   metrics=[
                                       '95f3c171-5605-4021-87ed-eede77101268',
                                       'bf588a78-56c7-4ba4-be46-d71e5002e030',
                                   ])
                         )]


class TestAlarmsBase(v2.FunctionalTest):

    def setUp(self):
        super(TestAlarmsBase, self).setUp()
        self.project_id = uuidutils.generate_uuid()
        self.user_id = uuidutils.generate_uuid()
        self.auth_headers = {'X-User-Id': self.user_id,
                             'X-Project-Id': self.project_id}

        c = mock.Mock()
        c.capabilities.list.return_value = {'aggregation_methods': [
            'count', 'mean', 'max', 'min', 'first', 'last', 'std']}
        self.useFixture(fixtures.MockPatch(
            'aodh.api.controllers.v2.alarm_rules.gnocchi.client.Client',
            return_value=c
        ))

    def _verify_alarm(self, json, alarm, expected_name=None):
        if expected_name and alarm.name != expected_name:
            self.fail("Alarm not found")
        for key in json:
            if key.endswith('_rule'):
                storage_key = 'rule'
            else:
                storage_key = key
            self.assertEqual(json[key], getattr(alarm, storage_key))

    def _get_alarm(self, id, auth_headers=None):
        headers = auth_headers or self.auth_headers
        url_path = "/alarms"
        if headers.get('X-Roles') == 'admin':
            url_path = '/alarms?q.field=all_projects&q.op=eq&q.value=true'

        data = self.get_json(url_path, headers=headers)

        match = [a for a in data if a['alarm_id'] == id]
        self.assertEqual(1, len(match), 'alarm %s not found' % id)
        return match[0]

    def _update_alarm(self, id, updated_data, auth_headers=None):
        data = self._get_alarm(id, auth_headers)
        data.update(updated_data)
        self.put_json('/alarms/%s' % id,
                      params=data,
                      headers=auth_headers or self.auth_headers)

    def _delete_alarm(self, id, auth_headers=None):
        self.delete('/alarms/%s' % id,
                    headers=auth_headers or self.auth_headers,
                    status=204)


class TestListEmptyAlarms(TestAlarmsBase):

    def test_empty(self):
        data = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual([], data)


class TestAlarms(TestAlarmsBase):

    def setUp(self):
        super(TestAlarms, self).setUp()
        for alarm in default_alarms(self.auth_headers):
            self.alarm_conn.create_alarm(alarm)

    def test_list_alarms(self):
        data = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual(3, len(data))
        self.assertEqual(set(['name1', 'name2', 'name3']),
                         set(r['name'] for r in data))
        self.assertEqual([['41869681-5776-46d6-91ed-cccc43b6e4e3',
                           'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                          ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                           'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                          ['95f3c171-5605-4021-87ed-eede77101268',
                           'bf588a78-56c7-4ba4-be46-d71e5002e030']],
                         [r[RULE_KEY]['metrics']
                          for r in sorted(data,
                                          key=operator.itemgetter('name'))])

    def test_alarms_query_with_timestamp(self):
        date_time = datetime.datetime(2012, 7, 2, 10, 41)
        isotime = date_time.isoformat()
        resp = self.get_json('/alarms',
                             headers=self.auth_headers,
                             q=[{'field': 'timestamp',
                                 'op': 'gt',
                                 'value': isotime}],
                             expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_alarms_query_with_state(self):
        alarm = models.Alarm(name='disabled',
                             type='gnocchi_aggregation_by_metrics_threshold',
                             enabled=False,
                             alarm_id='c',
                             description='c',
                             state='ok',
                             state_reason='Not evaluated',
                             state_timestamp=constants.MIN_DATETIME,
                             timestamp=constants.MIN_DATETIME,
                             ok_actions=[],
                             insufficient_data_actions=[],
                             alarm_actions=[],
                             repeat_actions=False,
                             user_id=self.auth_headers['X-User-Id'],
                             project_id=self.auth_headers['X-Project-Id'],
                             time_constraints=[],
                             rule=dict(
                                 comparison_operator='gt',
                                 threshold=3.0,
                                 aggregation_method='mean',
                                 evaluation_periods=60,
                                 granularity=1,
                                 metrics=[
                                     '41869681-5776-46d6-91ed-cccc43b6e4e3',
                                     'a1fb80f4-c242-4f57-87c6-68f47521059e',
                                 ]),
                             severity='critical')
        self.alarm_conn.update_alarm(alarm)
        resp = self.get_json('/alarms',
                             headers=self.auth_headers,
                             q=[{'field': 'state',
                                 'op': 'eq',
                                 'value': 'ok'}],
                             )
        self.assertEqual(1, len(resp))
        self.assertEqual('ok', resp[0]['state'])

    def test_list_alarms_by_type(self):
        alarms = self.get_json('/alarms',
                               headers=self.auth_headers,
                               q=[{'field': 'type',
                                   'op': 'eq',
                                   'value':
                                   'gnocchi_aggregation_by_metrics_threshold'
                                   }])
        self.assertEqual(3, len(alarms))
        self.assertEqual(set(['gnocchi_aggregation_by_metrics_threshold']),
                         set(alarm['type'] for alarm in alarms))

    def test_list_alarms_all_projects_by_admin(self):
        auth_headers = copy.copy(self.auth_headers)
        auth_headers['X-Roles'] = 'admin'

        alarms = self.get_json(
            '/alarms',
            headers=auth_headers,
            q=[{'field': 'all_projects', 'op': 'eq', 'value': 'true'}]
        )

        self.assertEqual(3, len(alarms))

    def test_list_alarms_all_projects_forbidden(self):
        response = self.get_json(
            '/alarms',
            headers=self.auth_headers,
            q=[{'field': 'all_projects', 'op': 'eq', 'value': 'true'}],
            expect_errors=True,
            status=401
        )

        faultstring = 'RBAC Authorization Failed'
        self.assertIn(faultstring,
                      response.json['error_message']['faultstring'])

    def test_list_alarms_other_project(self):
        auth_headers = {'X-User-Id': uuidutils.generate_uuid(),
                        'X-Project-Id': uuidutils.generate_uuid()}
        data = self.get_json('/alarms', headers=auth_headers)

        self.assertEqual(0, len(data))

    def test_get_not_existing_alarm(self):
        resp = self.get_json('/alarms/alarm-id-3',
                             headers=self.auth_headers,
                             expect_errors=True)
        self.assertEqual(404, resp.status_code)
        self.assertIn('Alarm alarm-id-3 not found',
                      resp.json['error_message']['faultstring'])

    def test_get_alarm(self):
        alarms = self.get_json('/alarms',
                               headers=self.auth_headers,
                               q=[{'field': 'name',
                                   'value': 'name1',
                                   }])
        self.assertEqual('name1', alarms[0]['name'])
        self.assertEqual(['41869681-5776-46d6-91ed-cccc43b6e4e3',
                          'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                         alarms[0][RULE_KEY]['metrics'])

        one = self.get_json('/alarms/%s' % alarms[0]['alarm_id'],
                            headers=self.auth_headers)
        self.assertEqual('name1', one['name'])
        self.assertEqual(['41869681-5776-46d6-91ed-cccc43b6e4e3',
                          'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                         one[RULE_KEY]['metrics'])
        self.assertEqual(alarms[0]['alarm_id'], one['alarm_id'])
        self.assertEqual(alarms[0]['repeat_actions'], one['repeat_actions'])
        self.assertEqual(alarms[0]['time_constraints'],
                         one['time_constraints'])

    def test_get_alarm_disabled(self):
        alarm = models.Alarm(name='disabled',
                             type='gnocchi_aggregation_by_metrics_threshold',
                             enabled=False,
                             alarm_id='c',
                             description='c',
                             state='insufficient data',
                             state_reason='Not evaluated',
                             state_timestamp=constants.MIN_DATETIME,
                             timestamp=constants.MIN_DATETIME,
                             ok_actions=[],
                             insufficient_data_actions=[],
                             alarm_actions=[],
                             repeat_actions=False,
                             user_id=self.auth_headers['X-User-Id'],
                             project_id=self.auth_headers['X-Project-Id'],
                             time_constraints=[],
                             rule=dict(
                                 comparison_operator='gt',
                                 threshold=3.0,
                                 aggregation_method='mean',
                                 evaluation_periods=60,
                                 granularity=1,
                                 metrics=[
                                     '41869681-5776-46d6-91ed-cccc43b6e4e3',
                                     'a1fb80f4-c242-4f57-87c6-68f47521059e',
                                 ]
                             ),
                             severity='critical')
        self.alarm_conn.update_alarm(alarm)

        alarms = self.get_json('/alarms',
                               headers=self.auth_headers,
                               q=[{'field': 'enabled',
                                   'value': 'False'}])
        self.assertEqual(1, len(alarms))
        self.assertEqual('disabled', alarms[0]['name'])

        one = self.get_json('/alarms/%s' % alarms[0]['alarm_id'],
                            headers=self.auth_headers)
        self.assertEqual('disabled', one['name'])

    def test_get_alarm_project_filter_wrong_op_normal_user(self):
        project = self.auth_headers['X-Project-Id']

        def _test(field, op):
            response = self.get_json('/alarms',
                                     q=[{'field': field,
                                         'op': op,
                                         'value': project}],
                                     expect_errors=True,
                                     status=400,
                                     headers=self.auth_headers)

            faultstring = 'Invalid input for field/attribute op'
            self.assertIn(faultstring,
                          response.json['error_message']['faultstring'])

        _test('project_id', 'ne')

    def test_get_alarm_project_filter_normal_user(self):
        project = self.auth_headers['X-Project-Id']

        def _test(field):
            alarms = self.get_json('/alarms',
                                   headers=self.auth_headers,
                                   q=[{'field': field,
                                       'op': 'eq',
                                       'value': project}])
            self.assertEqual(3, len(alarms))

        _test('project_id')

    def test_get_alarm_other_project_normal_user(self):
        def _test(field):
            response = self.get_json('/alarms',
                                     q=[{'field': field,
                                         'op': 'eq',
                                         'value': 'other-project'}],
                                     expect_errors=True,
                                     status=401,
                                     headers=self.auth_headers)
            faultstring = 'Not Authorized to access'
            self.assertIn(faultstring,
                          response.json['error_message']['faultstring'])

        _test('project_id')

    def test_get_alarm_forbiden(self):
        pf = os.path.abspath('aodh/tests/functional/api/v2/policy.yaml-test')
        self.CONF.set_override('policy_file', pf, group='oslo_policy')
        self.CONF.set_override('auth_mode', None, group='api')
        self.app = webtest.TestApp(app.load_app(self.CONF))

        response = self.get_json('/alarms',
                                 expect_errors=True,
                                 status=403,
                                 headers=self.auth_headers)
        faultstring = 'RBAC Authorization Failed'
        self.assertEqual(403, response.status_code)
        self.assertEqual(faultstring,
                         response.json['error_message']['faultstring'])

    def test_post_alarm_wsme_workaround(self):
        jsons = {
            'type': {
                'name': 'missing type',
                RULE_KEY: {
                    'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                                'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                    'aggregation_method': 'mean',
                    'threshold': 2.0,
                }
            },
            'name': {
                'type': 'gnocchi_aggregation_by_metrics_threshold',
                RULE_KEY: {
                    'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                                'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                    'aggregation_method': 'mean',
                    'threshold': 2.0,
                }
            },
            'threshold_rule/metrics': {
                'name': 'missing metrics',
                'type': 'gnocchi_aggregation_by_metrics_threshold',
                RULE_KEY: {
                    'aggregation_method': 'mean',
                    'threshold': 2.0,
                }
            },
            'threshold_rule/threshold': {
                'name': 'missing threshold',
                'type': 'gnocchi_aggregation_by_metrics_threshold',
                RULE_KEY: {
                    'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                                'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                    'aggregation_method': 'mean',
                }
            },
        }
        for field, json in jsons.items():
            resp = self.post_json('/alarms', params=json, expect_errors=True,
                                  status=400, headers=self.auth_headers)
            self.assertEqual("Invalid input for field/attribute %s."
                             " Value: \'None\'. Mandatory field missing."
                             % field.split('/', 1)[-1],
                             resp.json['error_message']['faultstring'])
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_post_invalid_alarm_time_constraint_start(self):
        json = {
            'name': 'added_alarm_invalid_constraint_duration',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'time_constraints': [
                {
                    'name': 'testcons',
                    'start': '11:00am',
                    'duration': 10
                }
            ],
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                "aggregation_method": "mean",
                'threshold': 300.0
            }
        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_post_duplicate_time_constraint_name(self):
        json = {
            'name': 'added_alarm_duplicate_constraint_name',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'time_constraints': [
                {
                    'name': 'testcons',
                    'start': '* 11 * * *',
                    'duration': 10
                },
                {
                    'name': 'testcons',
                    'start': '* * * * *',
                    'duration': 20
                }
            ],
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                "aggregation_method": "mean",
                'threshold': 300.0
            }
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        self.assertEqual(
            "Time constraint names must be unique for a given alarm.",
            resp.json['error_message']['faultstring'])
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_post_alarm_null_time_constraint(self):
        json = {
            'name': 'added_alarm_invalid_constraint_duration',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'time_constraints': None,
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'aggregation_method': 'mean',
                'threshold': 300.0
            }
        }
        self.post_json('/alarms', params=json, status=201,
                       headers=self.auth_headers)

    def test_post_invalid_alarm_time_constraint_duration(self):
        json = {
            'name': 'added_alarm_invalid_constraint_duration',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'time_constraints': [
                {
                    'name': 'testcons',
                    'start': '* 11 * * *',
                    'duration': -1,
                }
            ],
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'threshold': 300.0
            }
        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_post_invalid_alarm_time_constraint_timezone(self):
        json = {
            'name': 'added_alarm_invalid_constraint_timezone',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'time_constraints': [
                {
                    'name': 'testcons',
                    'start': '* 11 * * *',
                    'duration': 10,
                    'timezone': 'aaaa'
                }
            ],
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'threshold': 300.0
            }
        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_post_invalid_alarm_granularity(self):
        json = {
            'name': 'added_alarm_invalid_granularity',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'gt',
                'threshold': 2.0,
                'aggregation_method': 'mean',
                'granularity': -1,
            }

        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_post_null_rule(self):
        json = {
            'name': 'added_alarm_invalid_threshold_rule',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: None,
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        self.assertEqual(
            "gnocchi_aggregation_by_metrics_threshold_rule "
            "must be set for gnocchi_aggregation_by_metrics_threshold "
            "type alarm",
            resp.json['error_message']['faultstring'])

    def test_post_invalid_alarm_input_state(self):
        json = {
            'name': 'alarm1',
            'state': 'bad_state',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'gt',
                'threshold': 50.0
            }
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        expected_err_msg = ("Invalid input for field/attribute state."
                            " Value: 'bad_state'.")
        self.assertIn(expected_err_msg,
                      resp.json['error_message']['faultstring'])
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_post_invalid_alarm_input_severity(self):
        json = {
            'name': 'alarm1',
            'state': 'ok',
            'severity': 'bad_value',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'gt',
                'threshold': 50.0
            }
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        expected_err_msg = ("Invalid input for field/attribute severity."
                            " Value: 'bad_value'.")
        self.assertIn(expected_err_msg,
                      resp.json['error_message']['faultstring'])
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_post_invalid_alarm_input_type(self):
        json = {
            'name': 'alarm3',
            'state': 'ok',
            'type': 'bad_type',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'gt',
                'threshold': 50.0
            }
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        expected_err_msg = ("Invalid input for field/attribute"
                            " type."
                            " Value: 'bad_type'.")
        self.assertIn(expected_err_msg,
                      resp.json['error_message']['faultstring'])
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_post_invalid_alarm_input_enabled_str(self):
        json = {
            'name': 'alarm5',
            'enabled': 'bad_enabled',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'gt',
                'threshold': 50.0
            }
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        expected_err_msg = "Value not an unambiguous boolean: bad_enabled"
        self.assertIn(expected_err_msg,
                      resp.json['error_message']['faultstring'])
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_post_invalid_alarm_input_enabled_int(self):
        json = {
            'name': 'alarm6',
            'enabled': 0,
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'gt',
                'aggregation_method': 'mean',
                'threshold': 50.0
            }
        }
        resp = self.post_json('/alarms', params=json,
                              headers=self.auth_headers)
        self.assertFalse(resp.json['enabled'])
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(4, len(alarms))

    def _do_post_alarm_invalid_action(self, ok_actions=None,
                                      alarm_actions=None,
                                      insufficient_data_actions=None,
                                      error_message=None):

        ok_actions = ok_actions or []
        alarm_actions = alarm_actions or []
        insufficient_data_actions = insufficient_data_actions or []
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'ok_actions': ok_actions,
            'alarm_actions': alarm_actions,
            'insufficient_data_actions': insufficient_data_actions,
            'repeat_actions': True,
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'granularity': '180',
            }
        }
        resp = self.post_json('/alarms', params=json, status=400,
                              headers=self.auth_headers)
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))
        self.assertEqual(error_message,
                         resp.json['error_message']['faultstring'])

    def test_post_invalid_alarm_ok_actions(self):
        self._do_post_alarm_invalid_action(
            ok_actions=['spam://something/ok'],
            error_message='Unsupported action spam://something/ok')

    def test_post_invalid_alarm_alarm_actions(self):
        self._do_post_alarm_invalid_action(
            alarm_actions=['spam://something/alarm'],
            error_message='Unsupported action spam://something/alarm')

    def test_post_invalid_alarm_insufficient_data_actions(self):
        self._do_post_alarm_invalid_action(
            insufficient_data_actions=['spam://something/insufficient'],
            error_message='Unsupported action spam://something/insufficient')

    @staticmethod
    def _fake_urlsplit(*args, **kwargs):
        raise Exception("Evil urlsplit!")

    def test_post_invalid_alarm_actions_format(self):
        with mock.patch('oslo_utils.netutils.urlsplit',
                        self._fake_urlsplit):
            self._do_post_alarm_invalid_action(
                alarm_actions=['http://[::1'],
                error_message='Unable to parse action http://[::1')

    def test_post_alarm_defaults(self):
        to_check = {
            'enabled': True,
            'name': 'added_alarm_defaults',
            'ok_actions': [],
            'alarm_actions': [],
            'insufficient_data_actions': [],
            'repeat_actions': False,
        }

        json = {
            'name': 'added_alarm_defaults',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'aggregation_method': 'mean',
                'threshold': 300.0
            }
        }
        self.post_json('/alarms', params=json, status=201,
                       headers=self.auth_headers)
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(4, len(alarms))
        for alarm in alarms:
            if alarm.name == 'added_alarm_defaults':
                for key in to_check:
                    self.assertEqual(to_check[key],
                                     getattr(alarm, key))
                break
        else:
            self.fail("Alarm not found")

    def test_post_alarm_with_same_name(self):
        json = {
            'enabled': False,
            'name': 'dup_alarm_name',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'granularity': '180',
            }
        }

        resp1 = self.post_json('/alarms', params=json, status=201,
                               headers=self.auth_headers)
        resp2 = self.post_json('/alarms', params=json, status=201,
                               headers=self.auth_headers)
        self.assertEqual(resp1.json['name'], resp2.json['name'])
        self.assertNotEqual(resp1.json['alarm_id'], resp2.json['alarm_id'])
        alarms = self.get_json('/alarms',
                               headers=self.auth_headers,
                               q=[{'field': 'name',
                                   'value': 'dup_alarm_name'}])
        self.assertEqual(2, len(alarms))

    def test_post_alarm_noauth(self):
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'severity': 'low',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'granularity': '180',
            }
        }
        self.post_json('/alarms', params=json, status=201)
        alarms = list(self.alarm_conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))
        # to check to BoundedInt type conversion
        json[RULE_KEY]['evaluation_periods'] = 3
        json[RULE_KEY]['granularity'] = 180
        if alarms[0].name == 'added_alarm':
            for key in json:
                if key.endswith('_rule'):
                    storage_key = 'rule'
                else:
                    storage_key = key
                self.assertEqual(getattr(alarms[0], storage_key),
                                 json[key])
        else:
            self.fail("Alarm not found")

    @staticmethod
    def _alarm_representation_owned_by(identifiers):
        json = {
            'name': 'added_alarm',
            'enabled': False,
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'ok_actions': ['http://something/ok'],
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'granularity': 180,
            }
        }
        for aspect, id in identifiers.items():
            json['%s_id' % aspect] = id
        return json

    def _do_test_post_alarm_as_nonadmin_on_behalf_of_another(self,
                                                             identifiers):
        """Test posting an alarm.

        Test that posting an alarm as non-admin on behalf of another
        user/project fails with an explicit 401 instead of reverting
        to the requestor's identity.
        """
        json = self._alarm_representation_owned_by(identifiers)
        headers = {}
        headers.update(self.auth_headers)
        headers['X-Roles'] = 'demo'
        resp = self.post_json('/alarms', params=json, status=401,
                              headers=headers)
        aspect = 'user' if 'user' in identifiers else 'project'
        params = dict(aspect=aspect, id=identifiers[aspect])
        self.assertEqual("Not Authorized to access %(aspect)s %(id)s" % params,
                         resp.json['error_message']['faultstring'])

    def test_post_alarm_as_nonadmin_on_behalf_of_another_user(self):
        identifiers = dict(user='auseridthatisnotmine')
        self._do_test_post_alarm_as_nonadmin_on_behalf_of_another(identifiers)

    def test_post_alarm_as_nonadmin_on_behalf_of_another_project(self):
        identifiers = dict(project='aprojectidthatisnotmine')
        self._do_test_post_alarm_as_nonadmin_on_behalf_of_another(identifiers)

    def test_post_alarm_as_nonadmin_on_behalf_of_another_creds(self):
        identifiers = dict(user='auseridthatisnotmine',
                           project='aprojectidthatisnotmine')
        self._do_test_post_alarm_as_nonadmin_on_behalf_of_another(identifiers)

    def _do_test_post_alarm_as_nonadmin_on_behalf_of_self(self, identifiers):
        """Test posting an alarm.

        Test posting an alarm as non-admin on behalf of own user/project
        creates alarm associated with the requestor's identity.
        """
        json = self._alarm_representation_owned_by(identifiers)
        headers = {}
        headers.update(self.auth_headers)
        headers['X-Roles'] = 'demo'
        self.post_json('/alarms', params=json, status=201, headers=headers)
        alarms = list(self.alarm_conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))
        self.assertEqual(alarms[0].user_id,
                         self.auth_headers['X-User-Id'])
        self.assertEqual(alarms[0].project_id,
                         self.auth_headers['X-Project-Id'])

    def test_post_alarm_as_nonadmin_on_behalf_of_own_user(self):
        identifiers = dict(user=self.auth_headers['X-User-Id'])
        self._do_test_post_alarm_as_nonadmin_on_behalf_of_self(identifiers)

    def test_post_alarm_as_nonadmin_on_behalf_of_own_project(self):
        identifiers = dict(project=self.auth_headers['X-Project-Id'])
        self._do_test_post_alarm_as_nonadmin_on_behalf_of_self(identifiers)

    def test_post_alarm_as_nonadmin_on_behalf_of_own_creds(self):
        identifiers = dict(user=self.auth_headers['X-User-Id'],
                           project=self.auth_headers['X-Project-Id'])
        self._do_test_post_alarm_as_nonadmin_on_behalf_of_self(identifiers)

    def test_post_alarm_with_mismatch_between_type_and_rule(self):
        """Test the creation of an combination alarm with threshold rule."""
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'gnocchi_resources_threshold',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'granularity': '180',
            }
        }
        resp = self.post_json('/alarms', params=json,
                              expect_errors=True, status=400,
                              headers=self.auth_headers)
        self.assertEqual(
            "gnocchi_resources_threshold_rule must "
            "be set for gnocchi_resources_threshold type alarm",
            resp.json['error_message']['faultstring'])

    def test_post_alarm_with_duplicate_actions(self):
        body = {
            'name': 'dup-alarm-actions',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'granularity': '180',
            },
            'alarm_actions': ['http://no.where', 'http://no.where']
        }
        resp = self.post_json('/alarms', params=body,
                              headers=self.auth_headers)
        self.assertEqual(201, resp.status_code)
        alarms = list(self.alarm_conn.get_alarms(name='dup-alarm-actions'))
        self.assertEqual(1, len(alarms))
        self.assertEqual(['http://no.where'], alarms[0].alarm_actions)

    def test_post_alarm_with_too_many_actions(self):
        self.CONF.set_override('alarm_max_actions', 1, group='api')
        body = {
            'name': 'alarm-with-many-actions',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'granularity': '180',
            },
            'alarm_actions': ['http://no.where', 'http://no.where2']
        }
        resp = self.post_json('/alarms', params=body, expect_errors=True,
                              headers=self.auth_headers)
        self.assertEqual(400, resp.status_code)
        self.assertEqual("alarm_actions count exceeds maximum value 1",
                         resp.json['error_message']['faultstring'])

    def test_post_alarm_normal_user_set_log_actions(self):
        body = {
            'name': 'log_alarm_actions',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'granularity': '180',
            },
            'alarm_actions': ['log://']
        }
        resp = self.post_json('/alarms', params=body, expect_errors=True,
                              headers=self.auth_headers)
        self.assertEqual(401, resp.status_code)
        expected_msg = ("You are not authorized to create action: log://")
        self.assertEqual(expected_msg,
                         resp.json['error_message']['faultstring'])

    def test_post_alarm_normal_user_set_test_actions(self):
        body = {
            'name': 'test_alarm_actions',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'granularity': '180',
            },
            'alarm_actions': ['test://']
        }
        resp = self.post_json('/alarms', params=body, expect_errors=True,
                              headers=self.auth_headers)
        self.assertEqual(401, resp.status_code)
        expected_msg = ("You are not authorized to create action: test://")
        self.assertEqual(expected_msg,
                         resp.json['error_message']['faultstring'])

    def test_post_alarm_admin_user_set_log_test_actions(self):
        body = {
            'name': 'admin_alarm_actions',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'granularity': '180',
            },
            'alarm_actions': ['test://', 'log://']
        }
        headers = self.auth_headers
        headers['X-Roles'] = 'admin'
        self.post_json('/alarms', params=body, status=201,
                       headers=headers)
        alarms = list(self.alarm_conn.get_alarms(name='admin_alarm_actions'))
        self.assertEqual(1, len(alarms))
        self.assertEqual(['test://', 'log://'],
                         alarms[0].alarm_actions)

    def test_exercise_state_reason(self):
        body = {
            'name': 'nostate',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'granularity': '180',
            },
        }
        headers = self.auth_headers
        headers['X-Roles'] = 'admin'

        self.post_json('/alarms', params=body, status=201,
                       headers=headers)
        alarms = list(self.alarm_conn.get_alarms(name='nostate'))
        self.assertEqual(1, len(alarms))
        alarm_id = alarms[0].alarm_id

        alarm = self._get_alarm(alarm_id)
        self.assertEqual("insufficient data", alarm['state'])
        self.assertEqual("Not evaluated yet", alarm['state_reason'])

        # Ensure state reason is updated
        alarm = self._get_alarm('a')
        alarm['state'] = 'ok'
        self.put_json('/alarms/%s' % alarm_id,
                      params=alarm,
                      headers=self.auth_headers)
        alarm = self._get_alarm(alarm_id)
        self.assertEqual("ok", alarm['state'])
        self.assertEqual("Manually set via API", alarm['state_reason'])

        # Ensure state reason read only
        alarm = self._get_alarm('a')
        alarm['state'] = 'alarm'
        alarm['state_reason'] = 'oh no!'
        self.put_json('/alarms/%s' % alarm_id,
                      params=alarm,
                      headers=self.auth_headers)

        alarm = self._get_alarm(alarm_id)
        self.assertEqual("alarm", alarm['state'])
        self.assertEqual("Manually set via API", alarm['state_reason'])

    def test_post_alarm_without_actions(self):
        body = {
            'name': 'alarm_actions_none',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'granularity': '180',
            },
            'alarm_actions': None
        }
        headers = self.auth_headers
        headers['X-Roles'] = 'admin'
        self.post_json('/alarms', params=body, status=201,
                       headers=headers)
        alarms = list(self.alarm_conn.get_alarms(name='alarm_actions_none'))
        self.assertEqual(1, len(alarms))

        # FIXME(sileht): This should really returns [] not None
        # but SQL just stores the json dict as is...
        # migration script for sql will be a mess because we have
        # to parse all JSON :(
        # I guess we assume that wsme convert the None input to []
        # because of the array type, but it won't...
        self.assertIsNone(alarms[0].alarm_actions)

    def test_post_alarm_trust(self):
        json = {
            'name': 'added_alarm_defaults',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'ok_actions': ['trust+http://my.server:1234/foo'],
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'aggregation_method': 'mean',
                'threshold': 300.0
            }
        }
        auth = mock.Mock()
        trust_client = mock.Mock()
        with mock.patch('aodh.keystone_client.get_client') as client:
            mock_session = mock.Mock()
            mock_session.get_user_id.return_value = 'my_user'
            client.return_value = mock.Mock(session=mock_session)
            with mock.patch('keystoneclient.v3.client.Client') as sub_client:
                sub_client.return_value = trust_client
                trust_client.trusts.create.return_value = mock.Mock(id='5678')
                self.post_json('/alarms', params=json, status=201,
                               headers=self.auth_headers,
                               extra_environ={'keystone.token_auth': auth})
                trust_client.trusts.create.assert_called_once_with(
                    trustor_user=self.auth_headers['X-User-Id'],
                    trustee_user='my_user',
                    project=self.auth_headers['X-Project-Id'],
                    impersonation=True,
                    role_names=[])
        alarms = list(self.alarm_conn.get_alarms())
        for alarm in alarms:
            if alarm.name == 'added_alarm_defaults':
                self.assertEqual(
                    ['trust+http://5678:delete@my.server:1234/foo'],
                    alarm.ok_actions)
                break
        else:
            self.fail("Alarm not found")

        data = self._get_alarm(alarm.alarm_id)
        self.assertEqual(
            ['trust+http://my.server:1234/foo'], data['ok_actions'])

        with mock.patch('aodh.keystone_client.get_client') as client:
            client.return_value = mock.Mock(
                auth_ref=mock.Mock(user_id='my_user'))
            with mock.patch('keystoneclient.v3.client.Client') as sub_client:
                sub_client.return_value = trust_client
                self.delete('/alarms/%s' % alarm.alarm_id,
                            headers=self.auth_headers,
                            status=204,
                            extra_environ={'keystone.token_auth': auth})
                trust_client.trusts.delete.assert_called_once_with('5678')

    def test_put_alarm(self):
        json = {
            'enabled': False,
            'name': 'name_put',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'severity': 'critical',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'granularity': 180,
            }
        }
        data = self.get_json('/alarms',
                             headers=self.auth_headers,
                             q=[{'field': 'name',
                                 'value': 'name1',
                                 }])
        self.assertEqual(1, len(data))
        alarm_id = data[0]['alarm_id']

        self.put_json('/alarms/%s' % alarm_id,
                      params=json,
                      headers=self.auth_headers)
        alarm = list(self.alarm_conn.get_alarms(alarm_id=alarm_id,
                                                enabled=False))[0]
        self._verify_alarm(json, alarm)

    def test_put_alarm_as_admin(self):
        json = {
            'user_id': 'myuserid',
            'project_id': 'myprojectid',
            'enabled': False,
            'name': 'name_put',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'severity': 'critical',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'granularity': 180,
            }
        }
        headers = {}
        headers.update(self.auth_headers)
        headers['X-Roles'] = 'admin'

        data = self.get_json('/alarms',
                             headers=headers,
                             q=[{'field': 'name',
                                 'value': 'name1',
                                 }])
        self.assertEqual(1, len(data))
        alarm_id = data[0]['alarm_id']

        self.put_json('/alarms/%s' % alarm_id,
                      params=json,
                      headers=headers)
        alarm = list(self.alarm_conn.get_alarms(alarm_id=alarm_id,
                                                enabled=False))[0]
        self.assertEqual('myuserid', alarm.user_id)
        self.assertEqual('myprojectid', alarm.project_id)
        self._verify_alarm(json, alarm)

    def test_put_alarm_wrong_field(self):
        json = {
            'this_can_not_be_correct': 'ha',
            'enabled': False,
            'name': 'name1',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'severity': 'critical',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'granularity': 180,
            }
        }
        data = self.get_json('/alarms',
                             headers=self.auth_headers,
                             q=[{'field': 'name',
                                 'value': 'name1',
                                 }])
        self.assertEqual(1, len(data))
        alarm_id = data[0]['alarm_id']

        resp = self.put_json('/alarms/%s' % alarm_id,
                             expect_errors=True,
                             params=json,
                             headers=self.auth_headers)
        self.assertEqual(400, resp.status_code)

    def test_put_alarm_with_existing_name(self):
        """Test that update a threshold alarm with an existing name."""
        json = {
            'enabled': False,
            'name': 'name1',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'severity': 'critical',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'granularity': 180,
            }
        }
        data = self.get_json('/alarms',
                             headers=self.auth_headers,
                             q=[{'field': 'name',
                                 'value': 'name2',
                                 }])
        self.assertEqual(1, len(data))
        alarm_id = data[0]['alarm_id']

        resp = self.put_json('/alarms/%s' % alarm_id,
                             params=json,
                             headers=self.auth_headers)
        self.assertEqual(200, resp.status_code)

    def test_put_invalid_alarm_actions(self):
        json = {
            'enabled': False,
            'name': 'name1',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'severity': 'critical',
            'ok_actions': ['spam://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'granularity': 180,
            }
        }
        data = self.get_json('/alarms',
                             headers=self.auth_headers,
                             q=[{'field': 'name',
                                 'value': 'name2',
                                 }])
        self.assertEqual(1, len(data))
        alarm_id = data[0]['alarm_id']

        resp = self.put_json('/alarms/%s' % alarm_id,
                             expect_errors=True, status=400,
                             params=json,
                             headers=self.auth_headers)
        self.assertEqual(
            'Unsupported action spam://something/ok',
            resp.json['error_message']['faultstring'])

    def test_put_alarm_trust(self):
        data = self._get_alarm('a')
        data.update({'ok_actions': ['trust+http://something/ok']})
        trust_client = mock.Mock()
        with mock.patch('aodh.keystone_client.get_client') as client:
            client.return_value = mock.Mock(
                auth_ref=mock.Mock(user_id='my_user'))
            with mock.patch('keystoneclient.v3.client.Client') as sub_client:
                sub_client.return_value = trust_client
                trust_client.trusts.create.return_value = mock.Mock(id='5678')
                self.put_json('/alarms/%s' % data['alarm_id'],
                              params=data,
                              headers=self.auth_headers)

        for alarm in list(self.alarm_conn.get_alarms()):
            if alarm.alarm_id == data['alarm_id']:
                self.assertEqual(
                    ['trust+http://5678:delete@something/ok'],
                    alarm.ok_actions)
                break
        data = self._get_alarm('a')
        self.assertEqual(
            ['trust+http://something/ok'], data['ok_actions'])

        data.update({'ok_actions': ['http://no-trust-something/ok']})

        with mock.patch('aodh.keystone_client.get_client') as client:
            client.return_value = mock.Mock(
                auth_ref=mock.Mock(user_id='my_user'))
            with mock.patch('keystoneclient.v3.client.Client') as sub_client:
                sub_client.return_value = trust_client
                self.put_json('/alarms/%s' % data['alarm_id'],
                              params=data,
                              headers=self.auth_headers)
                trust_client.trusts.delete.assert_called_once_with('5678')

        data = self._get_alarm('a')
        self.assertEqual(
            ['http://no-trust-something/ok'], data['ok_actions'])

    def test_delete_alarm(self):
        data = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual(3, len(data))

        resp = self.delete('/alarms/%s' % data[0]['alarm_id'],
                           headers=self.auth_headers,
                           status=204)
        self.assertEqual(b'', resp.body)
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(2, len(alarms))

    def test_get_state_alarm(self):
        data = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual(3, len(data))

        resp = self.get_json('/alarms/%s/state' % data[0]['alarm_id'],
                             headers=self.auth_headers)
        self.assertEqual(resp, data[0]['state'])

    def test_set_state_alarm(self):
        data = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual(3, len(data))

        resp = self.put_json('/alarms/%s/state' % data[0]['alarm_id'],
                             headers=self.auth_headers,
                             params='alarm')
        alarms = list(self.alarm_conn.get_alarms(alarm_id=data[0]['alarm_id']))
        self.assertEqual(1, len(alarms))
        self.assertEqual('alarm', alarms[0].state)
        self.assertEqual('Manually set via API',
                         alarms[0].state_reason)
        self.assertEqual('alarm', resp.json)

    def test_set_invalid_state_alarm(self):
        data = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual(3, len(data))

        self.put_json('/alarms/%s/state' % data[0]['alarm_id'],
                      headers=self.auth_headers,
                      params='not valid',
                      status=400)

    def test_alarms_sends_notification(self):
        # Hit the AlarmsController ...
        json = {
            'name': 'sent_notification',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'severity': 'low',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'gt',
                'threshold': 2.0,
                'aggregation_method': 'mean',
            }

        }
        with mock.patch.object(messaging, 'get_notifier') as get_notifier:
            notifier = get_notifier.return_value
            self.post_json('/alarms', params=json, headers=self.auth_headers)
            get_notifier.assert_called_once_with(mock.ANY,
                                                 publisher_id='aodh.api')
        calls = notifier.info.call_args_list
        self.assertEqual(1, len(calls))
        args, _ = calls[0]
        context, event_type, payload = args
        self.assertEqual('alarm.creation', event_type)
        self.assertEqual('sent_notification', payload['detail']['name'])
        self.assertEqual(['41869681-5776-46d6-91ed-cccc43b6e4e3',
                          'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                         payload['detail']['rule']['metrics'])
        self.assertTrue(set(['alarm_id', 'detail', 'event_id', 'on_behalf_of',
                             'project_id', 'timestamp', 'type',
                             'user_id']).issubset(payload.keys()))

    def test_alarm_sends_notification(self):
        with mock.patch.object(messaging, 'get_notifier') as get_notifier:
            notifier = get_notifier.return_value
            self._update_alarm('a', dict(name='new_name'))
            get_notifier.assert_called_once_with(mock.ANY,
                                                 publisher_id='aodh.api')
        calls = notifier.info.call_args_list
        self.assertEqual(1, len(calls))
        args, _ = calls[0]
        context, event_type, payload = args
        self.assertEqual('alarm.rule_change', event_type)
        self.assertEqual('new_name', payload['detail']['name'])
        self.assertTrue(set(['alarm_id', 'detail', 'event_id', 'on_behalf_of',
                             'project_id', 'timestamp', 'type',
                             'user_id']).issubset(payload.keys()))

    def test_delete_alarm_sends_notification(self):
        with mock.patch.object(messaging, 'get_notifier') as get_notifier:
            notifier = get_notifier.return_value
            self._delete_alarm(default_alarms(self.auth_headers)[1].alarm_id)
            get_notifier.assert_called_once_with(mock.ANY,
                                                 publisher_id='aodh.api')
        calls = notifier.info.call_args_list
        self.assertEqual(1, len(calls))
        args, _ = calls[0]
        context, event_type, payload = args
        self.assertEqual('alarm.deletion', event_type)
        self.assertEqual('insufficient data', payload['detail']['state'])
        self.assertTrue(set(['alarm_id', 'detail', 'event_id', 'on_behalf_of',
                             'project_id', 'timestamp', 'type', 'severity',
                             'user_id']).issubset(payload.keys()))


class TestAlarmsHistory(TestAlarmsBase):

    def setUp(self):
        super(TestAlarmsHistory, self).setUp()
        alarm = models.Alarm(
            name='name1',
            type='gnocchi_aggregation_by_metrics_threshold',
            enabled=True,
            alarm_id='a',
            description='a',
            state='insufficient data',
            state_reason='insufficient data',
            severity='critical',
            state_timestamp=constants.MIN_DATETIME,
            timestamp=constants.MIN_DATETIME,
            ok_actions=[],
            insufficient_data_actions=[],
            alarm_actions=[],
            repeat_actions=True,
            user_id=self.auth_headers['X-User-Id'],
            project_id=self.auth_headers['X-Project-Id'],
            time_constraints=[dict(name='testcons',
                                   start='0 11 * * *',
                                   duration=300)],
            rule=dict(comparison_operator='gt',
                      threshold=2.0,
                      aggregation_method='mean',
                      evaluation_periods=60,
                      granularity=1,
                      metrics=['41869681-5776-46d6-91ed-cccc43b6e4e3',
                               'a1fb80f4-c242-4f57-87c6-68f47521059e']))
        self.alarm_conn.create_alarm(alarm)

    def _get_alarm_history(self, alarm_id, auth_headers=None, query=None,
                           expect_errors=False, status=200):
        url = '/alarms/%s/history' % alarm_id
        if query:
            url += '?q.op=%(op)s&q.value=%(value)s&q.field=%(field)s' % query
        resp = self.get_json(url,
                             headers=auth_headers or self.auth_headers,
                             expect_errors=expect_errors)
        if expect_errors:
            self.assertEqual(status, resp.status_code)
        return resp

    def _assert_is_subset(self, expected, actual):
        for k, v in expected.items():
            current = actual.get(k)
            if k == 'detail' and isinstance(v, dict):
                current = jsonlib.loads(current)
            self.assertEqual(v, current, 'mismatched field: %s' % k)
        self.assertIsNotNone(actual['event_id'])

    def _assert_in_json(self, expected, actual):
        actual = jsonlib.dumps(jsonlib.loads(actual), sort_keys=True)
        for k, v in expected.items():
            fragment = jsonlib.dumps({k: v}, sort_keys=True)[1:-1]
            self.assertIn(fragment, actual,
                          '%s not in %s' % (fragment, actual))

    def test_record_alarm_history_config(self):
        self.CONF.set_override('record_history', False)
        history = self._get_alarm_history('a')
        self.assertEqual([], history)
        self._update_alarm('a', dict(name='renamed'))
        history = self._get_alarm_history('a')
        self.assertEqual([], history)
        self.CONF.set_override('record_history', True)
        self._update_alarm('a', dict(name='foobar'))
        history = self._get_alarm_history('a')
        self.assertEqual(1, len(history))

    def test_record_alarm_history_severity(self):
        alarm = self._get_alarm('a')
        history = self._get_alarm_history('a')
        self.assertEqual([], history)
        self.assertEqual('critical', alarm['severity'])

        self._update_alarm('a', dict(severity='low'))
        new_alarm = self._get_alarm('a')
        history = self._get_alarm_history('a')
        self.assertEqual(1, len(history))
        self.assertEqual(jsonlib.dumps({'severity': 'low'}),
                         history[0]['detail'])
        self.assertEqual('low', new_alarm['severity'])

    def test_record_alarm_history_statistic(self):
        alarm = self._get_alarm('a')
        history = self._get_alarm_history('a')
        self.assertEqual([], history)
        self.assertEqual('mean', alarm[RULE_KEY]['aggregation_method'])

        rule = alarm[RULE_KEY].copy()
        rule['aggregation_method'] = 'min'
        data = dict(gnocchi_aggregation_by_metrics_threshold_rule=rule)
        self._update_alarm('a', data)
        new_alarm = self._get_alarm('a')
        history = self._get_alarm_history('a')
        self.assertEqual(1, len(history))
        self.assertEqual("min", jsonlib.loads(history[0]['detail'])
                         ['rule']["aggregation_method"])
        self.assertEqual('min', new_alarm[RULE_KEY]['aggregation_method'])

    def test_redundant_update_alarm_property_no_history_change(self):
        alarm = self._get_alarm('a')
        history = self._get_alarm_history('a')
        self.assertEqual([], history)
        self.assertEqual('critical', alarm['severity'])

        self._update_alarm('a', dict(severity='low'))
        new_alarm = self._get_alarm('a')
        history = self._get_alarm_history('a')
        self.assertEqual(1, len(history))
        self.assertEqual(jsonlib.dumps({'severity': 'low'}),
                         history[0]['detail'])
        self.assertEqual('low', new_alarm['severity'])

        self._update_alarm('a', dict(severity='low'))
        updated_history = self._get_alarm_history('a')
        self.assertEqual(1, len(updated_history))
        self.assertEqual(jsonlib.dumps({'severity': 'low'}),
                         updated_history[0]['detail'])
        self.assertEqual(history, updated_history)

    def test_get_recorded_alarm_history_on_create(self):
        new_alarm = {
            'name': 'new_alarm',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'max',
                'threshold': 42.0,
                'granularity': 60,
                'evaluation_periods': 1,
            }
        }
        self.post_json('/alarms', params=new_alarm, status=201,
                       headers=self.auth_headers)

        alarms = self.get_json('/alarms',
                               headers=self.auth_headers,
                               q=[{'field': 'name',
                                   'value': 'new_alarm',
                                   }])
        self.assertEqual(1, len(alarms))
        alarm = alarms[0]

        history = self._get_alarm_history(alarm['alarm_id'])
        self.assertEqual(1, len(history))
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    on_behalf_of=alarm['project_id'],
                                    project_id=alarm['project_id'],
                                    type='creation',
                                    user_id=alarm['user_id']),
                               history[0])
        new_alarm['rule'] = new_alarm[RULE_KEY]
        del new_alarm[RULE_KEY]
        self._assert_in_json(new_alarm, history[0]['detail'])

    def _do_test_get_recorded_alarm_history_on_update(self,
                                                      data,
                                                      type,
                                                      detail,
                                                      auth=None):
        alarm = self._get_alarm('a')
        history = self._get_alarm_history('a')
        self.assertEqual([], history)
        self._update_alarm('a', data, auth)
        history = self._get_alarm_history('a')
        self.assertEqual(1, len(history))
        project_id = auth['X-Project-Id'] if auth else alarm['project_id']
        user_id = auth['X-User-Id'] if auth else alarm['user_id']
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    detail=detail,
                                    on_behalf_of=alarm['project_id'],
                                    project_id=project_id,
                                    type=type,
                                    user_id=user_id),
                               history[0])

    def test_get_recorded_alarm_history_rule_change(self):
        data = dict(name='renamed')
        detail = '{"name": "renamed"}'
        self._do_test_get_recorded_alarm_history_on_update(data,
                                                           'rule change',
                                                           detail)

    def test_get_recorded_alarm_history_state_transition_on_behalf_of(self):
        # credentials for new non-admin user, on who's behalf the alarm
        # is created
        member_user = uuidutils.generate_uuid()
        member_project = uuidutils.generate_uuid()
        member_auth = {'X-Roles': 'member',
                       'X-User-Id': member_user,
                       'X-Project-Id': member_project}
        new_alarm = {
            'name': 'new_alarm',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'state': 'ok',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'max',
                'threshold': 42.0,
                'evaluation_periods': 1,
                'granularity': 60
            }
        }
        self.post_json('/alarms', params=new_alarm, status=201,
                       headers=member_auth)
        alarm = self.get_json('/alarms', headers=member_auth)[0]

        # effect a state transition as a new administrative user
        admin_user = uuidutils.generate_uuid()
        admin_project = uuidutils.generate_uuid()
        admin_auth = {'X-Roles': 'admin',
                      'X-User-Id': admin_user,
                      'X-Project-Id': admin_project}
        data = dict(state='alarm')
        self._update_alarm(alarm['alarm_id'], data, auth_headers=admin_auth)

        new_alarm['rule'] = new_alarm[RULE_KEY]
        del new_alarm[RULE_KEY]

        # ensure that both the creation event and state transition
        # are visible to the non-admin alarm owner and admin user alike
        for auth in [member_auth, admin_auth]:
            history = self._get_alarm_history(alarm['alarm_id'],
                                              auth_headers=auth)
            self.assertEqual(2, len(history), 'hist: %s' % history)
            self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                        detail={"state": "alarm",
                                                "state_reason":
                                                "Manually set via API"},
                                        on_behalf_of=alarm['project_id'],
                                        project_id=admin_project,
                                        type='rule change',
                                        user_id=admin_user),
                                   history[0])
            self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                        on_behalf_of=alarm['project_id'],
                                        project_id=member_project,
                                        type='creation',
                                        user_id=member_user),
                                   history[1])
            self._assert_in_json(new_alarm, history[1]['detail'])

            # ensure on_behalf_of cannot be constrained in an API call
            query = dict(field='on_behalf_of',
                         op='eq',
                         value=alarm['project_id'])
            self._get_alarm_history(alarm['alarm_id'], auth_headers=auth,
                                    query=query, expect_errors=True,
                                    status=400)

    def test_get_recorded_alarm_history_segregation(self):
        data = dict(name='renamed')
        detail = '{"name": "renamed"}'
        self._do_test_get_recorded_alarm_history_on_update(data,
                                                           'rule change',
                                                           detail)
        auth = {'X-Roles': 'member',
                'X-User-Id': uuidutils.generate_uuid(),
                'X-Project-Id': uuidutils.generate_uuid()}
        self._get_alarm_history('a', auth_headers=auth,
                                expect_errors=True, status=404)

    def test_delete_alarm_history_after_deletion(self):
        self._update_alarm('a', dict(name='renamed'))
        history = self._get_alarm_history('a')
        self.assertEqual(1, len(history))
        self.delete('/alarms/%s' % 'a',
                    headers=self.auth_headers,
                    status=204)
        self._get_alarm_history('a', expect_errors=True, status=404)

    def test_get_alarm_history_ordered_by_recentness(self):
        for i in range(10):
            self._update_alarm('a', dict(name='%s' % i))
        history = self._get_alarm_history('a')
        self.assertEqual(10, len(history), 'hist: %s' % history)
        self._assert_is_subset(dict(alarm_id='a',
                                    type='rule change'),
                               history[0])
        for i in range(1, 11):
            detail = '{"name": "%s"}' % (10 - i)
            self._assert_is_subset(dict(alarm_id='a',
                                        detail=detail,
                                        type='rule change'),
                                   history[i - 1])

    def test_get_alarm_history_constrained_by_timestamp(self):
        alarm = self._get_alarm('a')
        self._update_alarm('a', dict(name='renamed'))
        after = datetime.datetime.utcnow().isoformat()
        query = dict(field='timestamp', op='gt', value=after)
        history = self._get_alarm_history('a', query=query)
        self.assertEqual(0, len(history))
        query['op'] = 'le'
        history = self._get_alarm_history('a', query=query)
        self.assertEqual(1, len(history))
        detail = '{"name": "renamed"}'
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    detail=detail,
                                    on_behalf_of=alarm['project_id'],
                                    project_id=alarm['project_id'],
                                    type='rule change',
                                    user_id=alarm['user_id']),
                               history[0])

    def test_get_alarm_history_constrained_by_type(self):
        alarm = self._get_alarm('a')
        self._update_alarm('a', dict(name='renamed2'))
        query = dict(field='type', op='eq', value='rule change')
        history = self._get_alarm_history('a', query=query)
        self.assertEqual(1, len(history))
        detail = '{"name": "renamed2"}'
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    detail=detail,
                                    on_behalf_of=alarm['project_id'],
                                    project_id=alarm['project_id'],
                                    type='rule change',
                                    user_id=alarm['user_id']),
                               history[0])

    def test_get_alarm_history_constrained_by_alarm_id_failed(self):
        query = dict(field='alarm_id', op='eq', value='a')
        resp = self._get_alarm_history('a', query=query,
                                       expect_errors=True, status=400)
        msg = ('Unknown argument: "alarm_id": unrecognized'
               " field in query: [<Query {key!r} eq"
               " {value!r} Unset>], valid keys: ['project', "
               "'search_offset', 'severity', 'timestamp',"
               " 'type', 'user']")
        msg = msg.format(key='alarm_id', value='a')
        self.assertEqual(msg,
                         resp.json['error_message']['faultstring'])

    def test_get_alarm_history_constrained_by_not_supported_rule(self):
        query = dict(field='abcd', op='eq', value='abcd')
        resp = self._get_alarm_history('a', query=query,
                                       expect_errors=True, status=400)
        msg = ('Unknown argument: "abcd": unrecognized'
               " field in query: [<Query {key!r} eq"
               " {value!r} Unset>], valid keys: ['project', "
               "'search_offset', 'severity', 'timestamp',"
               " 'type', 'user']")
        msg = msg.format(key='abcd', value='abcd')
        self.assertEqual(msg,
                         resp.json['error_message']['faultstring'])

    def test_get_alarm_history_constrained_by_severity(self):
        self._update_alarm('a', dict(severity='low'))
        query = dict(field='severity', op='eq', value='low')
        history = self._get_alarm_history('a', query=query)
        self.assertEqual(1, len(history))
        self.assertEqual(jsonlib.dumps({'severity': 'low'}),
                         history[0]['detail'])

    def test_get_nonexistent_alarm_history(self):
        self._get_alarm_history('foobar', expect_errors=True, status=404)


class TestAlarmsQuotas(TestAlarmsBase):
    def setUp(self):
        super(TestAlarmsQuotas, self).setUp()
        self.alarm = {
            'name': 'alarm',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'user_id': self.user_id,
            'project_id': self.project_id,
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'max',
                'threshold': 42.0,
                'granularity': 60,
                'evaluation_periods': 1,
            }
        }

    def _create_alarm(self, alarm=None):
        if not alarm:
            alarm = self.alarm

        resp = self.post_json('/alarms', params=alarm,
                              headers=self.auth_headers,
                              status=201)

        return resp

    def _test_alarm_quota(self):
        """Failed on the second creation."""
        resp = self._create_alarm()

        alarms = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual(1, len(alarms))

        alarm = copy.copy(self.alarm)
        alarm['name'] = 'another_user_alarm'
        resp = self.post_json('/alarms', params=alarm,
                              expect_errors=True,
                              headers=self.auth_headers,
                              status=403)
        faultstring = 'Alarm quota exceeded for user'
        self.assertIn(faultstring,
                      resp.json['error_message']['faultstring'])

        alarms = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual(1, len(alarms))

    def test_alarms_quotas(self):
        self.CONF.set_override('user_alarm_quota', 1, 'api')
        self.CONF.set_override('project_alarm_quota', 1, 'api')
        self._test_alarm_quota()

    def test_project_alarms_quotas(self):
        self.CONF.set_override('project_alarm_quota', 1, 'api')
        self._test_alarm_quota()

    def test_user_alarms_quotas(self):
        self.CONF.set_override('user_alarm_quota', 1, 'api')
        self._test_alarm_quota()

    def test_larger_limit_project_alarms_quotas(self):
        self.CONF.set_override('user_alarm_quota', 1, 'api')
        self.CONF.set_override('project_alarm_quota', 2, 'api')
        self._test_alarm_quota()

    def test_larger_limit_user_alarms_quotas(self):
        self.CONF.set_override('user_alarm_quota', 2, 'api')
        self.CONF.set_override('project_alarm_quota', 1, 'api')
        self._test_alarm_quota()

    def test_larger_limit_user_alarm_quotas_multitenant_user(self):
        self.CONF.set_override('user_alarm_quota', 2, 'api')
        self.CONF.set_override('project_alarm_quota', 1, 'api')

        def _test(field, value):
            query = [{
                'field': field,
                'op': 'eq',
                'value': value
            }]
            alarms = self.get_json('/alarms', q=query,
                                   headers=self.auth_headers)
            self.assertEqual(1, len(alarms))

        alarm = {
            'name': 'alarm',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'user_id': self.auth_headers['X-User-Id'],
            'project_id': self.auth_headers['X-Project-Id'],
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'le',
                'aggregation_method': 'max',
                'threshold': 42.0,
                'granularity': 60,
                'evaluation_periods': 1,
            }
        }

        resp = self.post_json('/alarms', params=alarm,
                              headers=self.auth_headers)

        self.assertEqual(201, resp.status_code)
        _test('project_id', self.auth_headers['X-Project-Id'])

        self.auth_headers['X-Project-Id'] = uuidutils.generate_uuid()
        alarm['name'] = 'another_user_alarm'
        alarm['project_id'] = self.auth_headers['X-Project-Id']
        resp = self.post_json('/alarms', params=alarm,
                              headers=self.auth_headers)

        self.assertEqual(201, resp.status_code)
        _test('project_id', self.auth_headers['X-Project-Id'])

        self.auth_headers["X-roles"] = "admin"
        alarms = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual(1, len(alarms))

    def test_overquota_by_quota_api(self):
        auth_headers = copy.copy(self.auth_headers)
        auth_headers['X-Roles'] = 'admin'

        # Update project quota.
        self.post_json(
            '/quotas',
            {
                "project_id": self.project_id,
                "quotas": [
                    {
                        "resource": "alarms",
                        "limit": 1
                    }
                ]
            },
            headers=auth_headers,
            status=201
        )

        self._test_alarm_quota()

        # Update project quota back
        self.post_json(
            '/quotas',
            {
                "project_id": self.project_id,
                "quotas": [
                    {
                        "resource": "alarms",
                        "limit": -1
                    }
                ]
            },
            headers=auth_headers,
            status=201
        )

    def test_overquota_by_user_quota_config(self):
        self.CONF.set_override('user_alarm_quota', 1, 'api')
        auth_headers = copy.copy(self.auth_headers)
        auth_headers['X-Roles'] = 'admin'

        # Update project quota.
        self.post_json(
            '/quotas',
            {
                "project_id": self.project_id,
                "quotas": [
                    {
                        "resource": "alarms",
                        "limit": 2
                    }
                ]
            },
            headers=auth_headers,
            status=201
        )

        self._test_alarm_quota()

        # Update project quota back
        self.post_json(
            '/quotas',
            {
                "project_id": self.project_id,
                "quotas": [
                    {
                        "resource": "alarms",
                        "limit": -1
                    }
                ]
            },
            headers=auth_headers,
            status=201
        )


class TestAlarmsRuleThreshold(TestAlarmsBase):

    def test_post_invalid_alarm_statistic(self):
        json = {
            'name': 'added_alarm',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'gt',
                'threshold': 2.0,
                'aggregation_method': 'magic',
            }
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        expected_err_msg = ("aggregation_method should be in ['count', "
                            "'mean', 'max', 'min', 'first', 'last', 'std'] "
                            "not magic")
        self.assertIn(expected_err_msg,
                      resp.json['error_message']['faultstring'])
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(0, len(alarms))

    def test_post_invalid_alarm_input_comparison_operator(self):
        json = {
            'name': 'alarm2',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'comparison_operator': 'bad_co',
                'threshold': 50.0
            }
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        expected_err_msg = ("Invalid input for field/attribute"
                            " comparison_operator."
                            " Value: 'bad_co'.")
        self.assertIn(expected_err_msg,
                      resp.json['error_message']['faultstring'])
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(0, len(alarms))

    def test_post_threshold_rule_defaults(self):
        to_check = {
            'name': 'added_alarm_defaults',
            'state': 'insufficient data',
            'description': ('gnocchi_aggregation_by_metrics_threshold '
                            'alarm rule'),
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'threshold': 300.0,
                'comparison_operator': 'eq',
                'aggregation_method': 'mean',
                'evaluation_periods': 1,
                'granularity': 60,
            }

        }
        json = {
            'name': 'added_alarm_defaults',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            RULE_KEY: {
                'metrics': ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                            'a1fb80f4-c242-4f57-87c6-68f47521059e'],
                'aggregation_method': 'mean',
                'threshold': 300.0
            }
        }
        self.post_json('/alarms', params=json, status=201,
                       headers=self.auth_headers)
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(1, len(alarms))
        for alarm in alarms:
            if alarm.name == 'added_alarm_defaults':
                for key in to_check:
                    if key.endswith('_rule'):
                        storage_key = 'rule'
                    else:
                        storage_key = key
                    self.assertEqual(to_check[key],
                                     getattr(alarm, storage_key))
                break
        else:
            self.fail("Alarm not found")


class TestAlarmsRuleGnocchi(TestAlarmsBase):

    def setUp(self):
        super(TestAlarmsRuleGnocchi, self).setUp()
        for alarm in [
            models.Alarm(name='name1',
                         type='gnocchi_resources_threshold',
                         enabled=True,
                         alarm_id='e',
                         description='e',
                         state='insufficient data',
                         state_reason='Not evaluated',
                         severity='critical',
                         state_timestamp=constants.MIN_DATETIME,
                         timestamp=constants.MIN_DATETIME,
                         ok_actions=[],
                         insufficient_data_actions=[],
                         alarm_actions=[],
                         repeat_actions=True,
                         user_id=self.auth_headers['X-User-Id'],
                         project_id=self.auth_headers['X-Project-Id'],
                         time_constraints=[],
                         rule=dict(comparison_operator='gt',
                                   threshold=2.0,
                                   aggregation_method='mean',
                                   granularity=60,
                                   evaluation_periods=1,
                                   metric='meter.test',
                                   resource_type='instance',
                                   resource_id=(
                                       '6841c175-d7c4-4bc2-bc7a-1c7832271b8f'),
                                   )
                         ),
            models.Alarm(name='name2',
                         type='gnocchi_aggregation_by_metrics_threshold',
                         enabled=True,
                         alarm_id='f',
                         description='f',
                         state='insufficient data',
                         state_reason='Not evaluated',
                         severity='critical',
                         state_timestamp=constants.MIN_DATETIME,
                         timestamp=constants.MIN_DATETIME,
                         ok_actions=[],
                         insufficient_data_actions=[],
                         alarm_actions=[],
                         repeat_actions=True,
                         user_id=self.auth_headers['X-User-Id'],
                         project_id=self.auth_headers['X-Project-Id'],
                         time_constraints=[],
                         rule=dict(comparison_operator='gt',
                                   threshold=2.0,
                                   aggregation_method='mean',
                                   evaluation_periods=1,
                                   granularity=60,
                                   metrics=[
                                       '41869681-5776-46d6-91ed-cccc43b6e4e3',
                                       'a1fb80f4-c242-4f57-87c6-68f47521059e']
                                   ),
                         ),
            models.Alarm(name='name3',
                         type='gnocchi_aggregation_by_resources_threshold',
                         enabled=True,
                         alarm_id='g',
                         description='f',
                         state='insufficient data',
                         state_reason='Not evaluated',
                         severity='critical',
                         state_timestamp=constants.MIN_DATETIME,
                         timestamp=constants.MIN_DATETIME,
                         ok_actions=[],
                         insufficient_data_actions=[],
                         alarm_actions=[],
                         repeat_actions=True,
                         user_id=self.auth_headers['X-User-Id'],
                         project_id=self.auth_headers['X-Project-Id'],
                         time_constraints=[],
                         rule=dict(comparison_operator='gt',
                                   threshold=2.0,
                                   aggregation_method='mean',
                                   granularity=60,
                                   evaluation_periods=1,
                                   metric='meter.test',
                                   resource_type='instance',
                                   query='{"=": {"server_group": '
                                   '"my_autoscaling_group"}}')
                         ),
        ]:

            self.alarm_conn.create_alarm(alarm)

    def test_list_alarms(self):
        data = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual(3, len(data))
        self.assertEqual(set(['name1', 'name2', 'name3']),
                         set(r['name'] for r in data))
        self.assertEqual(set(['meter.test']),
                         set(r['gnocchi_resources_threshold_rule']['metric']
                             for r in data
                             if 'gnocchi_resources_threshold_rule' in r))

    def test_post_gnocchi_metrics_alarm_cached(self):
        # NOTE(gordc):  cache is a decorator and therefore, gets mocked across
        # entire scenario. ideally we should test both scenario but tough.
        # assume cache will return aggregation_method == ['count'] always.
        json = {
            'enabled': False,
            'name': 'name_post',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'severity': 'critical',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            RULE_KEY: {
                'metrics': ['b3d9d8ab-05e8-439f-89ad-5e978dd2a5eb',
                            '009d4faf-c275-46f0-8f2d-670b15bac2b0'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'granularity': 180,
            }
        }

        with mock.patch('aodh.api.controllers.v2.alarm_rules.'
                        'gnocchi.client') as clientlib:
            c = clientlib.Client.return_value
            c.capabilities.list.return_value = {
                'aggregation_methods': ['count']}
            self.post_json('/alarms', params=json, headers=self.auth_headers)

        with mock.patch('aodh.api.controllers.v2.alarm_rules.'
                        'gnocchi.client') as clientlib:
            self.post_json('/alarms', params=json, headers=self.auth_headers)
            self.assertFalse(clientlib.called)

    def test_post_gnocchi_resources_alarm(self):
        json = {
            'enabled': False,
            'name': 'name_post',
            'state': 'ok',
            'type': 'gnocchi_resources_threshold',
            'severity': 'critical',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'gnocchi_resources_threshold_rule': {
                'metric': 'ameter',
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'granularity': 180,
                'resource_type': 'instance',
                'resource_id': '209ef69c-c10c-4efb-90ff-46f4b2d90d2e',
            }
        }

        with mock.patch('aodh.api.controllers.v2.alarm_rules.'
                        'gnocchi.client') as clientlib:
            c = clientlib.Client.return_value
            c.capabilities.list.return_value = {
                'aggregation_methods': ['count']}
            self.post_json('/alarms', params=json, headers=self.auth_headers)

        alarms = list(self.alarm_conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))
        self._verify_alarm(json, alarms[0])

    def test_post_gnocchi_metrics_alarm(self):
        json = {
            'enabled': False,
            'name': 'name_post',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_metrics_threshold',
            'severity': 'critical',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            RULE_KEY: {
                'metrics': ['b3d9d8ab-05e8-439f-89ad-5e978dd2a5eb',
                            '009d4faf-c275-46f0-8f2d-670b15bac2b0'],
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'granularity': 180,
            }
        }

        with mock.patch('aodh.api.controllers.v2.alarm_rules.'
                        'gnocchi.client') as clientlib:
            c = clientlib.Client.return_value
            c.capabilities.list.return_value = {
                'aggregation_methods': ['count']}

            self.post_json('/alarms', params=json, headers=self.auth_headers)

        alarms = list(self.alarm_conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))
        self._verify_alarm(json, alarms[0])

    @mock.patch('aodh.keystone_client.get_client')
    def test_post_gnocchi_aggregation_alarm_project_constraint(self,
                                                               get_client):
        json = {
            'enabled': False,
            'name': 'project_constraint',
            'state': 'ok',
            'type': 'gnocchi_aggregation_by_resources_threshold',
            'severity': 'critical',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'gnocchi_aggregation_by_resources_threshold_rule': {
                'metric': 'ameter',
                'comparison_operator': 'le',
                'aggregation_method': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'granularity': 180,
                'resource_type': 'instance',
                'query': '{"=": {"server_group": "my_autoscaling_group"}}',
            }
        }

        expected_query = {"and": [
            {"or": [
                {"=": {"created_by_project_id":
                       self.auth_headers['X-Project-Id']}},
                {"and": [
                    {"=": {"created_by_project_id": "<my-uuid>"}},
                    {"=": {"project_id": self.auth_headers['X-Project-Id']}}
                ]},
            ]},
            {"=": {"server_group": "my_autoscaling_group"}},
        ]}

        ks_client = mock.Mock()
        ks_client.domains.list.return_value = [mock.Mock(
            id='<my-uuid>',
            name='Default')]
        ks_client.projects.find.return_value = mock.Mock(id='<my-uuid>')
        get_client.return_value = ks_client

        with mock.patch('aodh.api.controllers.v2.alarm_rules.'
                        'gnocchi.client') as clientlib:
            c = clientlib.Client.return_value
            c.capabilities.list.return_value = {
                'aggregation_methods': ['count']}
            self.post_json('/alarms', params=json, headers=self.auth_headers)

            self.assertEqual([mock.call(
                operations=[
                    'aggregate', 'count',
                    ['metric', 'ameter', 'count']
                ],
                needed_overlap=0,
                start="-1 day",
                stop="now",
                search=expected_query,
                resource_type="instance")],
                c.aggregates.fetch.mock_calls),

        alarms = list(self.alarm_conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))

        json['gnocchi_aggregation_by_resources_threshold_rule']['query'] = (
            jsonlib.dumps(expected_query))
        self._verify_alarm(json, alarms[0])


class TestAlarmsRuleLoadBalancer(TestAlarmsBase):
    def test_post(self):
        json = {
            'name': 'added_alarm_defaults',
            'type': 'loadbalancer_member_health',
            'loadbalancer_member_health_rule': {
                "pool_id": "2177ccd8-b09c-417a-89a0-e8d2419be612",
                "stack_id": "1b974012-ebcb-4888-8ae2-47714d4d2c4d",
                "autoscaling_group_id": "681c9266-61d2-4c9a-ad18-526807f6adc0"
            }
        }
        self.post_json('/alarms', params=json, status=201,
                       headers=self.auth_headers)

        alarms = list(self.alarm_conn.get_alarms())

        self.assertEqual(1, len(alarms))
        self._verify_alarm(json, alarms[0])


class TestAlarmsEvent(TestAlarmsBase):

    def test_list_alarms(self):
        alarm = models.Alarm(name='event.alarm.1',
                             type='event',
                             enabled=True,
                             alarm_id='h',
                             description='h',
                             state='insufficient data',
                             state_reason='insufficient data',
                             severity='moderate',
                             state_timestamp=constants.MIN_DATETIME,
                             timestamp=constants.MIN_DATETIME,
                             ok_actions=[],
                             insufficient_data_actions=[],
                             alarm_actions=[],
                             repeat_actions=False,
                             user_id=self.auth_headers['X-User-Id'],
                             project_id=self.auth_headers['X-Project-Id'],
                             time_constraints=[],
                             rule=dict(event_type='event.test',
                                       query=[]),
                             )
        self.alarm_conn.create_alarm(alarm)

        data = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual(1, len(data))
        self.assertEqual(set(['event.alarm.1']),
                         set(r['name'] for r in data))
        self.assertEqual(set(['event.test']),
                         set(r['event_rule']['event_type']
                             for r in data if 'event_rule' in r))

    def test_post_event_alarm_defaults(self):
        to_check = {
            'enabled': True,
            'name': 'added_alarm_defaults',
            'state': 'insufficient data',
            'description': 'Alarm when * event occurred.',
            'type': 'event',
            'ok_actions': [],
            'alarm_actions': [],
            'insufficient_data_actions': [],
            'repeat_actions': False,
            'rule': {
                'event_type': '*',
                'query': [],
            }
        }

        json = {
            'name': 'added_alarm_defaults',
            'type': 'event',
            'event_rule': {
                'event_type': '*',
                'query': []
            }
        }
        self.post_json('/alarms', params=json, status=201,
                       headers=self.auth_headers)
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(1, len(alarms))
        for alarm in alarms:
            if alarm.name == 'added_alarm_defaults':
                for key in to_check:
                    self.assertEqual(to_check[key], getattr(alarm, key))
                break
        else:
            self.fail("Alarm not found")


class TestAlarmsCompositeRule(TestAlarmsBase):

    def setUp(self):
        super(TestAlarmsCompositeRule, self).setUp()
        self.sub_rule1 = {
            "type": "gnocchi_aggregation_by_metrics_threshold",
            "metrics": ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                        'a1fb80f4-c242-4f57-87c6-68f47521059e'],
            "evaluation_periods": 5,
            "threshold": 0.8,
            "aggregation_method": "mean",
            "granularity": 60,
            "comparison_operator": "gt"
        }
        self.sub_rule2 = {
            "type": "gnocchi_aggregation_by_metrics_threshold",
            "metrics": ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                        'a1fb80f4-c242-4f57-87c6-68f47521059e'],
            "evaluation_periods": 4,
            "threshold": 200,
            "aggregation_method": "max",
            "granularity": 60,
            "comparison_operator": "gt"
        }
        self.sub_rule3 = {
            "type": "gnocchi_aggregation_by_metrics_threshold",
            "metrics": ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                        'a1fb80f4-c242-4f57-87c6-68f47521059e'],
            "evaluation_periods": 3,
            "threshold": 1000,
            "aggregation_method": "mean",
            "granularity": 60,
            "comparison_operator": "gt"
        }

        self.rule = {
            "or": [self.sub_rule1,
                   {
                       "and": [self.sub_rule2, self.sub_rule3]
                   }]}

    def test_list_alarms(self):
        alarm = models.Alarm(name='composite_alarm',
                             type='composite',
                             enabled=True,
                             alarm_id='composite',
                             description='composite',
                             state='insufficient data',
                             state_reason='insufficient data',
                             severity='moderate',
                             state_timestamp=constants.MIN_DATETIME,
                             timestamp=constants.MIN_DATETIME,
                             ok_actions=[],
                             insufficient_data_actions=[],
                             alarm_actions=[],
                             repeat_actions=False,
                             user_id=self.auth_headers['X-User-Id'],
                             project_id=self.auth_headers['X-Project-Id'],
                             time_constraints=[],
                             rule=self.rule,
                             )
        self.alarm_conn.create_alarm(alarm)

        data = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual(1, len(data))
        self.assertEqual(set(['composite_alarm']),
                         set(r['name'] for r in data))
        self.assertEqual(self.rule, data[0]['composite_rule'])

    def test_post_with_composite_rule(self):
        json = {
            "type": "composite",
            "name": "composite_alarm",
            "composite_rule": self.rule,
            "repeat_actions": False
        }
        self.post_json('/alarms', params=json, status=201,
                       headers=self.auth_headers)
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(1, len(alarms))
        self.assertEqual(self.rule, alarms[0].rule)

    def test_post_with_sub_rule_with_wrong_type(self):
        self.sub_rule1['type'] = 'non-type'
        json = {
            "type": "composite",
            "name": "composite_alarm",
            "composite_rule": self.rule,
            "repeat_actions": False
        }
        response = self.post_json('/alarms', params=json, status=400,
                                  expect_errors=True,
                                  headers=self.auth_headers)

        err = "Unsupported sub-rule type"
        faultstring = response.json['error_message']['faultstring']
        self.assertIn(err, faultstring)

    def test_post_with_sub_rule_with_only_required_params(self):
        sub_rulea = {
            "metrics": ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                        'a1fb80f4-c242-4f57-87c6-68f47521059e'],
            "threshold": 0.8,
            "aggregation_method": "mean",
            "type": "gnocchi_aggregation_by_metrics_threshold"}
        sub_ruleb = {
            "metrics": ['41869681-5776-46d6-91ed-cccc43b6e4e3',
                        'a1fb80f4-c242-4f57-87c6-68f47521059e'],
            "threshold": 200,
            "aggregation_method": "mean",
            "type": "gnocchi_aggregation_by_metrics_threshold"}
        json = {
            "type": "composite",
            "name": "composite_alarm",
            "composite_rule": {"and": [sub_rulea, sub_ruleb]},
            "repeat_actions": False
        }
        self.post_json('/alarms', params=json, status=201,
                       headers=self.auth_headers)
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(1, len(alarms))

    def test_post_with_sub_rule_with_invalid_params(self):
        self.sub_rule1['threshold'] = False
        json = {
            "type": "composite",
            "name": "composite_alarm",
            "composite_rule": self.rule,
            "repeat_actions": False
        }
        response = self.post_json('/alarms', params=json, status=400,
                                  expect_errors=True,
                                  headers=self.auth_headers)
        faultstring = ("Invalid input for field/attribute threshold. "
                       "Value: 'False'. Wrong type. Expected '%s', got '%s'"
                       % (type(1.0), type(True)))
        self.assertEqual(faultstring,
                         response.json['error_message']['faultstring'])


class TestPaginationQuery(TestAlarmsBase):
    def setUp(self):
        super(TestPaginationQuery, self).setUp()
        for alarm in default_alarms(self.auth_headers):
            self.alarm_conn.create_alarm(alarm)

    def test_pagination_query_single_sort(self):
        data = self.get_json('/alarms?sort=name:desc',
                             headers=self.auth_headers)
        names = [a['name'] for a in data]
        self.assertEqual(['name3', 'name2', 'name1'], names)
        data = self.get_json('/alarms?sort=name:asc',
                             headers=self.auth_headers)
        names = [a['name'] for a in data]
        self.assertEqual(['name1', 'name2', 'name3'], names)

    def test_sort_by_severity_with_its_value(self):
        if self.engine != "mysql":
            self.skipTest("This is only implemented for MySQL")
        data = self.get_json('/alarms?sort=severity:asc',
                             headers=self.auth_headers)
        severities = [a['severity'] for a in data]
        self.assertEqual(['moderate', 'critical', 'critical'],
                         severities)
        data = self.get_json('/alarms?sort=severity:desc',
                             headers=self.auth_headers)
        severities = [a['severity'] for a in data]
        self.assertEqual(['critical', 'critical', 'moderate'],
                         severities)

    def test_pagination_query_limit(self):
        data = self.get_json('/alarms?limit=2', headers=self.auth_headers)
        self.assertEqual(2, len(data))

    def test_pagination_query_limit_sort(self):
        data = self.get_json('/alarms?sort=name:asc&limit=2',
                             headers=self.auth_headers)
        self.assertEqual(2, len(data))

    def test_pagination_query_marker(self):
        data = self.get_json('/alarms?sort=name:desc',
                             headers=self.auth_headers)
        self.assertEqual(3, len(data))
        alarm_ids = [a['alarm_id'] for a in data]
        names = [a['name'] for a in data]
        self.assertEqual(['name3', 'name2', 'name1'], names)
        marker_url = ('/alarms?sort=name:desc&marker=%s' % alarm_ids[1])
        data = self.get_json(marker_url, headers=self.auth_headers)
        self.assertEqual(1, len(data))
        new_alarm_ids = [a['alarm_id'] for a in data]
        self.assertEqual(alarm_ids[2:], new_alarm_ids)
        new_names = [a['name'] for a in data]
        self.assertEqual(['name1'], new_names)

    def test_pagination_query_multiple_sorts(self):
        new_alarms = default_alarms(self.auth_headers)
        for a_id in zip(new_alarms, ['e', 'f', 'g', 'h']):
            a_id[0].alarm_id = a_id[1]
            self.alarm_conn.create_alarm(a_id[0])
        data = self.get_json('/alarms', headers=self.auth_headers)
        self.assertEqual(6, len(data))
        sort_url = '/alarms?sort=name:desc&sort=alarm_id:asc'
        data = self.get_json(sort_url, headers=self.auth_headers)
        name_ids = [(a['name'], a['alarm_id']) for a in data]
        expected = [('name3', 'c'),
                    ('name3', 'g'), ('name2', 'b'), ('name2', 'f'),
                    ('name1', 'a'), ('name1', 'e')]
        self.assertEqual(expected, name_ids)

    def test_pagination_query_invalid_sort_key(self):
        resp = self.get_json('/alarms?sort=invalid_key:desc',
                             headers=self.auth_headers,
                             expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual("Invalid input for field/attribute sort. Value: "
                         "'invalid_key:desc'. the sort parameter should be"
                         " a pair of sort key and sort dir combined with "
                         "':', or only sort key specified and sort dir will "
                         "be default 'asc', the supported sort keys are: "
                         "('alarm_id', 'enabled', 'name', 'type', 'severity',"
                         " 'timestamp', 'user_id', 'project_id', 'state', "
                         "'repeat_actions', 'state_timestamp')",
                         resp.json['error_message']['faultstring'])

    def test_pagination_query_only_sort_key_specified(self):
        data = self.get_json('/alarms?sort=name',
                             headers=self.auth_headers)
        names = [a['name'] for a in data]
        self.assertEqual(['name1', 'name2', 'name3'], names)

    def test_pagination_query_history_data(self):
        for i in range(10):
            self._update_alarm('a', dict(name='%s' % i))
        url = '/alarms/a/history?sort=event_id:desc&sort=timestamp:desc'
        data = self.get_json(url, headers=self.auth_headers)
        sorted_data = sorted(data,
                             key=lambda d: (d['event_id'], d['timestamp']),
                             reverse=True)
        self.assertEqual(sorted_data, data)
