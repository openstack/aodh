#
# Copyright 2013 Red Hat, Inc
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
"""Tests for aodh.evaluator.AlarmEvaluationService.
"""
import mock
from oslo_config import fixture as fixture_config
from stevedore import extension

from aodh import evaluator
from aodh import service
from aodh.tests import base as tests_base


class TestAlarmEvaluationService(tests_base.BaseTestCase):
    def setUp(self):
        super(TestAlarmEvaluationService, self).setUp()
        conf = service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf
        self.setup_messaging(self.CONF)

        self.threshold_eval = mock.Mock()
        self.evaluators = extension.ExtensionManager.make_test_instance(
            [
                extension.Extension(
                    'threshold',
                    None,
                    None,
                    self.threshold_eval),
            ]
        )

        self.storage_conn = mock.MagicMock()
        self.svc = evaluator.AlarmEvaluationService(self.CONF)
        self.svc.tg = mock.Mock()
        self.svc.partition_coordinator = mock.MagicMock()
        p_coord = self.svc.partition_coordinator
        p_coord.extract_my_subset.side_effect = lambda _, x: x
        self.svc.evaluators = self.evaluators
        self.svc.supported_evaluators = ['threshold']

    def _do_test_start(self, test_interval=120,
                       coordination_heartbeat=1.0,
                       coordination_active=False):
        self.CONF.set_override('evaluation_interval',
                               test_interval)
        self.CONF.set_override('heartbeat',
                               coordination_heartbeat,
                               group='coordination',
                               enforce_type=True)
        with mock.patch('aodh.storage.get_connection_from_config',
                        return_value=self.storage_conn):
            p_coord_mock = self.svc.partition_coordinator
            p_coord_mock.is_active.return_value = coordination_active

            self.svc.start()
            self.svc.partition_coordinator.start.assert_called_once_with()
            self.svc.partition_coordinator.join_group.assert_called_once_with(
                self.svc.PARTITIONING_GROUP_NAME)

            initial_delay = test_interval if coordination_active else None
            expected = [
                mock.call(test_interval,
                          self.svc._evaluate_assigned_alarms,
                          initial_delay=initial_delay),
                mock.call(604800, mock.ANY),
            ]
            if coordination_active:
                hb_interval = min(coordination_heartbeat, test_interval / 4)
                hb_call = mock.call(hb_interval,
                                    self.svc.partition_coordinator.heartbeat)
                expected.insert(1, hb_call)
            actual = self.svc.tg.add_timer.call_args_list
            self.assertEqual(expected, actual)

    def test_start_singleton(self):
        self._do_test_start(coordination_active=False)

    def test_start_coordinated(self):
        self._do_test_start(coordination_active=True)

    def test_start_coordinated_high_hb_interval(self):
        self._do_test_start(coordination_active=True, test_interval=10,
                            coordination_heartbeat=5)

    def test_evaluation_cycle(self):
        alarm = mock.Mock(type='threshold', alarm_id="alarm_id1")
        self.storage_conn.get_alarms.return_value = [alarm]
        with mock.patch('aodh.storage.get_connection_from_config',
                        return_value=self.storage_conn):
            p_coord_mock = self.svc.partition_coordinator
            p_coord_mock.extract_my_subset.return_value = [alarm]

            self.svc._evaluate_assigned_alarms()

            p_coord_mock.extract_my_subset.assert_called_once_with(
                self.svc.PARTITIONING_GROUP_NAME, ["alarm_id1"])
            self.threshold_eval.evaluate.assert_called_once_with(alarm)

    def test_evaluation_cycle_with_bad_alarm(self):
        alarms = [
            mock.Mock(type='threshold', name='bad'),
            mock.Mock(type='threshold', name='good'),
        ]
        self.storage_conn.get_alarms.return_value = alarms
        self.threshold_eval.evaluate.side_effect = [Exception('Boom!'), None]
        with mock.patch('aodh.storage.get_connection_from_config',
                        return_value=self.storage_conn):
            p_coord_mock = self.svc.partition_coordinator
            p_coord_mock.extract_my_subset.return_value = alarms

            self.svc._evaluate_assigned_alarms()
            self.assertEqual([mock.call(alarms[0]), mock.call(alarms[1])],
                             self.threshold_eval.evaluate.call_args_list)

    def test_unknown_extension_skipped(self):
        alarms = [
            mock.Mock(type='not_existing_type'),
            mock.Mock(type='threshold')
        ]

        self.storage_conn.get_alarms.return_value = alarms
        with mock.patch('aodh.storage.get_connection_from_config',
                        return_value=self.storage_conn):
            self.svc.start()
            self.svc._evaluate_assigned_alarms()
            self.threshold_eval.evaluate.assert_called_once_with(alarms[1])

    def test_check_alarm_query_constraints(self):
        self.storage_conn.get_alarms.return_value = []
        with mock.patch('aodh.storage.get_connection_from_config',
                        return_value=self.storage_conn):
            self.svc.start()
            self.svc._evaluate_assigned_alarms()
            expected = [({'enabled': True, 'exclude': {'type': 'event'}},)]
            self.assertEqual(expected,
                             self.storage_conn.get_alarms.call_args_list)
