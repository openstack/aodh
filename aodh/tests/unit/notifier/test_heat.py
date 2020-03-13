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

from unittest import mock

from oslo_utils import netutils

from aodh.notifier import heat as heat_notifier
from aodh.tests.unit.notifier import base


class TestTrustHeatAlarmNotifier(base.TestNotifierBase):
    @mock.patch("aodh.keystone_client.get_heat_client_from_trust")
    def test_notify(self, mock_heatclient):
        action = netutils.urlsplit("trust+autohealer://fake_trust_id:delete@")
        alarm_id = "fake_alarm_id"
        alarm_name = "fake_alarm_name"
        severity = "low"
        previous = "ok"
        current = "alarm"
        reason = "no good reason"
        reason_data = {
            "stack_id": "fake_stack_id",
            "asg_id": "fake_asg_id",
            "unhealthy_members": [
                {"id": "3bd8bc5a-7632-11e9-84cd-00224d6b7bc1"}
            ]
        }

        class FakeResource(object):
            def __init__(self, resource_name):
                self.parent_resource = resource_name

        mock_client = mock_heatclient.return_value
        mock_client.resources.list.return_value = [
            FakeResource("fake_resource_name")
        ]

        notifier = heat_notifier.TrustHeatAlarmNotifier(self.conf)
        notifier.notify(action, alarm_id, alarm_name, severity, previous,
                        current, reason, reason_data)

        mock_heatclient.assert_called_once_with(self.conf, "fake_trust_id")
        mock_client.resources.mark_unhealthy.assert_called_once_with(
            "fake_asg_id",
            "fake_resource_name",
            True,
            "unhealthy load balancer member"
        )
        mock_client.stacks.update.assert_called_once_with(
            "fake_stack_id", existing=True
        )

    @mock.patch("aodh.keystone_client.get_heat_client_from_trust")
    def test_notify_stack_id_missing(self, mock_heatclient):
        action = netutils.urlsplit("trust+autohealer://fake_trust_id:delete@")
        alarm_id = "fake_alarm_id"
        alarm_name = "fake_alarm_name"
        severity = "low"
        previous = "ok"
        current = "alarm"
        reason = "no good reason"
        reason_data = {
            "asg_id": "fake_asg_id",
            "unhealthy_members": [
                {"tags": ["3bd8bc5a-7632-11e9-84cd-00224d6b7bc1"]}
            ]
        }

        notifier = heat_notifier.TrustHeatAlarmNotifier(self.conf)
        notifier.notify(action, alarm_id, alarm_name, severity, previous,
                        current, reason, reason_data)

        self.assertFalse(mock_heatclient.called)
