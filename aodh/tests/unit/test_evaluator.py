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
import time

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
        self.CONF.set_override('workers', 1, 'evaluator')
        self.setup_messaging(self.CONF)

        self.threshold_eval = mock.MagicMock()
        self.evaluators = extension.ExtensionManager.make_test_instance(
            [
                extension.Extension(
                    'threshold',
                    None,
                    None,
                    self.threshold_eval),
            ]
        )

        self.svc = evaluator.AlarmEvaluationService(self.CONF)
        self.svc.tg = mock.Mock()

    @mock.patch('aodh.storage.get_connection_from_config',
                mock.MagicMock())
    def _do_test_start(self, test_interval=120,
                       coordination_heartbeat=1.0,
                       coordination_active=False):
        self.CONF.set_override('evaluation_interval',
                               test_interval)
        self.CONF.set_override('heartbeat',
                               coordination_heartbeat,
                               group='coordination',
                               enforce_type=True)

        with mock.patch('aodh.coordination.PartitionCoordinator') as m_pc:
            m_pc.return_value.is_active.return_value = coordination_active

            self.addCleanup(self.svc.stop)
            self.svc.start()

        self.svc.partition_coordinator.start.assert_called_once_with()
        self.svc.partition_coordinator.join_group.assert_called_once_with(
            self.svc.PARTITIONING_GROUP_NAME)

        actual = self.svc.tg.add_timer.call_args_list
        self.assertEqual([mock.call(604800, mock.ANY)], actual)

    def test_start_singleton(self):
        self._do_test_start(coordination_active=False)

    def test_start_coordinated(self):
        self._do_test_start(coordination_active=True)

    def test_start_coordinated_high_hb_interval(self):
        self._do_test_start(coordination_active=True, test_interval=10,
                            coordination_heartbeat=5)

    @mock.patch('stevedore.extension.ExtensionManager')
    @mock.patch('aodh.storage.get_connection_from_config')
    @mock.patch('aodh.coordination.PartitionCoordinator')
    def test_evaluation_cycle(self, m_pc, m_conn, m_em):
        alarm = mock.Mock(type='threshold', alarm_id="alarm_id1")
        m_pc.return_value.extract_my_subset.return_value = ["alarm_id1"]
        m_pc.return_value.is_active.return_value = False
        m_conn.return_value.get_alarms.return_value = [alarm]
        m_em.return_value = self.evaluators
        self.threshold_eval.evaluate.side_effect = [Exception('Boom!'), None]

        self.addCleanup(self.svc.stop)
        self.svc.start()

        time.sleep(1)

        target = self.svc.partition_coordinator.extract_my_subset
        target.assert_called_once_with(self.svc.PARTITIONING_GROUP_NAME,
                                       ["alarm_id1"])
        self.threshold_eval.evaluate.assert_called_once_with(alarm)

    @mock.patch('stevedore.extension.ExtensionManager')
    @mock.patch('aodh.coordination.PartitionCoordinator')
    def test_evaluation_cycle_with_bad_alarm(self, m_pc, m_em):
        m_pc.return_value.is_active.return_value = False
        m_em.return_value = self.evaluators

        alarms = [
            mock.Mock(type='threshold', name='bad'),
            mock.Mock(type='threshold', name='good'),
        ]
        self.threshold_eval.evaluate.side_effect = [Exception('Boom!'), None]

        with mock.patch.object(self.svc, '_assigned_alarms',
                               return_value=alarms):
            self.addCleanup(self.svc.stop)
            self.svc.start()

            time.sleep(1)

        self.assertEqual([mock.call(alarms[0]), mock.call(alarms[1])],
                         self.threshold_eval.evaluate.call_args_list)

    @mock.patch('stevedore.extension.ExtensionManager')
    def test_unknown_extension_skipped(self, m_em):
        m_em.return_value = self.evaluators
        alarms = [
            mock.Mock(type='not_existing_type'),
            mock.Mock(type='threshold')
        ]

        with mock.patch.object(self.svc, '_assigned_alarms',
                               return_value=alarms):
            self.addCleanup(self.svc.stop)
            self.svc.start()

            time.sleep(1)

            self.threshold_eval.evaluate.assert_called_once_with(alarms[1])

    @mock.patch('stevedore.extension.ExtensionManager')
    @mock.patch('aodh.coordination.PartitionCoordinator')
    @mock.patch('aodh.storage.get_connection_from_config')
    def test_check_alarm_query_constraints(self, m_conn, m_pc, m_em):
        m_conn.return_value.get_alarms.return_value = []
        m_pc.return_value.extract_my_subset.return_value = []
        m_pc.return_value.is_active.return_value = False
        m_em.return_value = self.evaluators

        self.addCleanup(self.svc.start)
        self.svc.start()

        time.sleep(1)

        expected = [({'enabled': True, 'exclude': {'type': 'event'}},)]
        self.assertEqual(expected,
                         self.svc.storage_conn.get_alarms.call_args_list)
