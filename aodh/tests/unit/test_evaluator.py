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
import fixtures
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
        self._fake_conn = mock.Mock()
        self._fake_conn.get_alarms.return_value = []
        self._fake_pc = mock.Mock()
        self._fake_em = extension.ExtensionManager.make_test_instance(
            [
                extension.Extension(
                    'gnocchi_aggregation_by_metrics_threshold',
                    None,
                    None,
                    self.threshold_eval),
            ]
        )

        self.useFixture(fixtures.MockPatch(
            'stevedore.extension.ExtensionManager',
            return_value=self._fake_em
        ))
        self.useFixture(fixtures.MockPatch(
            'aodh.coordination.PartitionCoordinator',
            return_value=self._fake_pc
        ))
        self.useFixture(fixtures.MockPatch(
            'aodh.storage.get_connection_from_config',
            return_value=self._fake_conn
        ))

    def _do_test_start(self, test_interval=120,
                       coordination_heartbeat=1.0,
                       coordination_active=False):

        self.CONF.set_override('evaluation_interval',
                               test_interval)
        self.CONF.set_override('heartbeat',
                               coordination_heartbeat,
                               group='coordination')

        self._fake_pc.is_active.return_value = coordination_active

        svc = evaluator.AlarmEvaluationService(0, self.CONF)
        self.addCleanup(svc.terminate)
        svc.terminate()
        svc.partition_coordinator.start.assert_called_once_with()
        svc.partition_coordinator.join_group.assert_called_once_with(
            svc.PARTITIONING_GROUP_NAME)

    def test_start_singleton(self):
        self._do_test_start(coordination_active=False)

    def test_start_coordinated(self):
        self._do_test_start(coordination_active=True)

    def test_start_coordinated_high_hb_interval(self):
        self._do_test_start(coordination_active=True, test_interval=10,
                            coordination_heartbeat=5)

    def test_evaluation_cycle(self):
        alarm = mock.Mock(type='gnocchi_aggregation_by_metrics_threshold',
                          alarm_id="alarm_id1")
        self._fake_pc.extract_my_subset.return_value = ["alarm_id1"]
        self._fake_pc.is_active.return_value = False
        self._fake_conn.get_alarms.return_value = [alarm]
        self.threshold_eval.evaluate.side_effect = [Exception('Boom!'), None]

        svc = evaluator.AlarmEvaluationService(0, self.CONF)
        self.addCleanup(svc.terminate)
        time.sleep(1)
        target = svc.partition_coordinator.extract_my_subset
        target.assert_called_once_with(svc.PARTITIONING_GROUP_NAME,
                                       ["alarm_id1"])
        self.threshold_eval.evaluate.assert_called_once_with(alarm)

    def test_evaluation_cycle_with_bad_alarm(self):

        alarms = [
            mock.Mock(type='gnocchi_aggregation_by_metrics_threshold',
                      name='bad', alarm_id='a'),
            mock.Mock(type='gnocchi_aggregation_by_metrics_threshold',
                      name='good', alarm_id='b'),
        ]
        self.threshold_eval.evaluate.side_effect = [Exception('Boom!'), None]

        self._fake_pc.is_active.return_value = False
        self._fake_pc.extract_my_subset.return_value = ['a', 'b']
        self._fake_conn.get_alarms.return_value = alarms

        svc = evaluator.AlarmEvaluationService(0, self.CONF)
        self.addCleanup(svc.terminate)
        time.sleep(1)
        self.assertEqual([mock.call(alarms[0]), mock.call(alarms[1])],
                         self.threshold_eval.evaluate.call_args_list)

    def test_unknown_extension_skipped(self):
        alarms = [
            mock.Mock(type='not_existing_type', alarm_id='a'),
            mock.Mock(type='gnocchi_aggregation_by_metrics_threshold',
                      alarm_id='b')
        ]

        self._fake_pc.is_active.return_value = False
        self._fake_pc.extract_my_subset.return_value = ['a', 'b']
        self._fake_conn.get_alarms.return_value = alarms

        svc = evaluator.AlarmEvaluationService(0, self.CONF)
        self.addCleanup(svc.terminate)
        time.sleep(1)
        self.threshold_eval.evaluate.assert_called_once_with(alarms[1])

    def test_check_alarm_query_constraints(self):
        self._fake_conn.get_alarms.return_value = []
        self._fake_pc.extract_my_subset.return_value = []
        self._fake_pc.is_active.return_value = False

        svc = evaluator.AlarmEvaluationService(0, self.CONF)
        self.addCleanup(svc.terminate)
        time.sleep(1)
        expected = [({'enabled': True, 'exclude': {'type': 'event'}},)]
        self.assertEqual(expected,
                         svc.storage_conn.get_alarms.call_args_list)
