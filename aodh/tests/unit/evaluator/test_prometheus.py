#
# Copyright 2025 Red Hat, Inc
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

import fixtures
from unittest import mock

from oslo_utils import uuidutils

from aodh.evaluator import prometheus
from aodh.storage import models
from aodh.tests import constants
from aodh.tests.unit.evaluator import base


class TestPrometheusEvaluator(base.TestEvaluatorBase):
    EVALUATOR = prometheus.PrometheusEvaluator

    def setUp(self):
        self.client = self.useFixture(fixtures.MockPatch(
            'aodh.evaluator.prometheus.client'
        )).mock.Client.return_value
        self.prepared_alarms = [
            models.Alarm(name='instance_running_hot',
                         description='instance_running_hot',
                         type='prometheus',
                         enabled=True,
                         user_id='foobar',
                         project_id='123',
                         alarm_id=uuidutils.generate_uuid(),
                         state='insufficient data',
                         state_reason='insufficient data',
                         state_timestamp=constants.MIN_DATETIME,
                         timestamp=constants.MIN_DATETIME,
                         insufficient_data_actions=[],
                         ok_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         time_constraints=[],
                         severity='low',
                         rule=dict(
                             comparison_operator='gt',
                             threshold=80.0,
                             evaluation_periods=5,
                             query='ceilometer_cpu')
                         ),
            models.Alarm(name='group_running_idle',
                         description='group_running_idle',
                         type='prometheus',
                         enabled=True,
                         user_id='foobar',
                         project_id='123',
                         state='insufficient data',
                         state_reason='insufficient data',
                         state_timestamp=constants.MIN_DATETIME,
                         timestamp=constants.MIN_DATETIME,
                         insufficient_data_actions=[],
                         ok_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         alarm_id=uuidutils.generate_uuid(),
                         time_constraints=[],
                         rule=dict(
                             comparison_operator='le',
                             threshold=10.0,
                             evaluation_periods=4,
                             query='ceilometer_memory'),
                         ),

        ]
        super().setUp()

    def prepare_alarms(self):
        self.alarms = self.prepared_alarms[0:1]

    def test_project_scoping_old_alarm(self):
        # Alarm created before scope_to_project was introduced
        self.client.query.query.side_effect = None
        with (
                mock.patch('aodh.evaluator.prometheus.'
                           'obsc_rbac.PromQLRbac.modify_query',
                           ) as mock_modify_query,
                mock.patch('aodh.evaluator.prometheus.'
                           'obsc_rbac.PromQLRbac.__init__',
                           return_value=None) as mock_rbac_init):
            self._evaluate_all_alarms()
        mock_rbac_init.assert_not_called()
        mock_modify_query.assert_not_called()

    def test_project_scoping_not_scoped(self):
        # Alarm likely created by admin. This shouldn't get scoped
        # to a single project.
        self.client.query.query.side_effect = None
        self.alarms[0].rule['scope_to_project'] = None
        with (
                mock.patch('aodh.evaluator.prometheus.'
                           'obsc_rbac.PromQLRbac.modify_query',
                           ) as mock_modify_query,
                mock.patch('aodh.evaluator.prometheus.'
                           'obsc_rbac.PromQLRbac.__init__',
                           return_value=None) as mock_rbac_init):
            self._evaluate_all_alarms()
        mock_rbac_init.assert_not_called()
        mock_modify_query.assert_not_called()

    def test_project_scoping_scoped(self):
        # Alarm which needs to be scoped to a single project
        project_id = 123
        project_label = 'custom_label'
        self.conf.set_override('prometheus_project_label_name', project_label)
        self.alarms[0].rule['scope_to_project'] = project_id
        self.client.query.query.side_effect = None

        with (
                mock.patch('aodh.evaluator.prometheus.'
                           'obsc_rbac.PromQLRbac.modify_query',
                           return_value='') as mock_modify_query,
                mock.patch('aodh.evaluator.prometheus.'
                           'obsc_rbac.PromQLRbac.__init__',
                           return_value=None) as mock_rbac_init):
            self._evaluate_all_alarms()

        mock_rbac_init.assert_called_once()
        self.assertEqual(
            project_id, mock_rbac_init.call_args.args[1])
        self.assertEqual(
            project_label,
            mock_rbac_init.call_args.kwargs['project_label'])

        mock_modify_query.assert_called_once_with(
            'ceilometer_cpu')
