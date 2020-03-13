# Copyright 2019 Catalyst Cloud Ltd.
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

import datetime
from unittest import mock

from oslo_utils import timeutils
from oslo_utils import uuidutils

from aodh import evaluator
from aodh.evaluator import loadbalancer
from aodh.storage import models
from aodh.tests import constants
from aodh.tests.unit.evaluator import base


@mock.patch('octaviaclient.api.v2.octavia.OctaviaAPI')
@mock.patch('aodh.keystone_client.get_session')
class TestLoadBalancerMemberHealthEvaluator(base.TestEvaluatorBase):
    EVALUATOR = loadbalancer.LoadBalancerMemberHealthEvaluator

    def test_evaluate(self, mock_session, mock_octavia):
        alarm = models.Alarm(
            name='lb_member_alarm',
            description='lb_member_alarm',
            type=loadbalancer.ALARM_TYPE,
            enabled=True,
            user_id=uuidutils.generate_uuid(),
            project_id=uuidutils.generate_uuid(dashed=False),
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
                pool_id=uuidutils.generate_uuid(),
                stack_id=uuidutils.generate_uuid(),
                autoscaling_group_id=uuidutils.generate_uuid(),
            )
        )

        mock_client = mock.MagicMock()
        mock_octavia.return_value = mock_client
        created_at = timeutils.utcnow() - datetime.timedelta(days=1)
        mock_client.member_list.return_value = {
            'members': [
                {
                    'created_at': created_at.isoformat(),
                    'admin_state_up': True,
                    'operating_status': 'ERROR',
                }
            ]
        }

        self.evaluator.evaluate(alarm)

        self.assertEqual(evaluator.ALARM, alarm.state)

    def test_evaluate_octavia_error(self, mock_session, mock_octavia):
        class Response(object):
            def __init__(self, status_code, content):
                self.status_code = status_code
                self.content = content

        alarm = models.Alarm(
            name='lb_member_alarm',
            description='lb_member_alarm',
            type=loadbalancer.ALARM_TYPE,
            enabled=True,
            user_id=uuidutils.generate_uuid(),
            project_id=uuidutils.generate_uuid(dashed=False),
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
                pool_id=uuidutils.generate_uuid(),
                stack_id=uuidutils.generate_uuid(),
                autoscaling_group_id=uuidutils.generate_uuid(),
            )
        )

        mock_client = mock.MagicMock()
        mock_octavia.return_value = mock_client
        msg = 'Pool NotFound'
        mock_client.member_list.return_value = Response(404, msg)

        self.evaluator.evaluate(alarm)

        self.assertEqual(evaluator.UNKNOWN, alarm.state)
        self.assertEqual(msg, alarm.state_reason)

    def test_evaluate_alarm_to_ok(self, mock_session, mock_octavia):
        alarm = models.Alarm(
            name='lb_member_alarm',
            description='lb_member_alarm',
            type=loadbalancer.ALARM_TYPE,
            enabled=True,
            user_id=uuidutils.generate_uuid(),
            project_id=uuidutils.generate_uuid(dashed=False),
            alarm_id=uuidutils.generate_uuid(),
            state=evaluator.ALARM,
            state_reason='alarm',
            state_timestamp=constants.MIN_DATETIME,
            timestamp=constants.MIN_DATETIME,
            insufficient_data_actions=[],
            ok_actions=[],
            alarm_actions=[],
            repeat_actions=False,
            time_constraints=[],
            severity='low',
            rule=dict(
                pool_id=uuidutils.generate_uuid(),
                stack_id=uuidutils.generate_uuid(),
                autoscaling_group_id=uuidutils.generate_uuid(),
            )
        )

        mock_client = mock.MagicMock()
        mock_octavia.return_value = mock_client
        created_at = timeutils.utcnow() - datetime.timedelta(days=1)
        mock_client.member_list.return_value = {
            'members': [
                {
                    'created_at': created_at.isoformat(),
                    'admin_state_up': True,
                    'operating_status': 'ACTIVE',
                }
            ]
        }

        self.evaluator.evaluate(alarm)

        self.assertEqual(evaluator.OK, alarm.state)
