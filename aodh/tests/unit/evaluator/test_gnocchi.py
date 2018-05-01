#
# Copyright 2015 eNovance
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
import datetime
import fixtures
import json
import unittest

from gnocchiclient import exceptions
import mock
from oslo_utils import timeutils
from oslo_utils import uuidutils
import pytz
import six
from six import moves

from aodh.evaluator import gnocchi
from aodh import messaging
from aodh.storage import models
from aodh.tests import constants
from aodh.tests.unit.evaluator import base


class TestGnocchiEvaluatorBase(base.TestEvaluatorBase):
    def setUp(self):
        self.client = self.useFixture(fixtures.MockPatch(
            'aodh.evaluator.gnocchi.client'
        )).mock.Client.return_value
        self.prepared_alarms = [
            models.Alarm(name='instance_running_hot',
                         description='instance_running_hot',
                         type='gnocchi_resources_threshold',
                         enabled=True,
                         user_id='foobar',
                         project_id='snafu',
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
                             aggregation_method='mean',
                             granularity=60,
                             metric='cpu_util',
                             resource_type='instance',
                             resource_id='my_instance')
                         ),
            models.Alarm(name='group_running_idle',
                         description='group_running_idle',
                         type='gnocchi_aggregation_by_metrics_threshold',
                         enabled=True,
                         user_id='foobar',
                         project_id='snafu',
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
                             aggregation_method='max',
                             granularity=300,
                             metrics=['0bb1604d-1193-4c0a-b4b8-74b170e35e83',
                                      '9ddc209f-42f8-41e1-b8f1-8804f59c4053']),
                         ),
            models.Alarm(name='instance_not_running',
                         description='instance_running_hot',
                         type='gnocchi_aggregation_by_resources_threshold',
                         enabled=True,
                         user_id='foobar',
                         project_id='snafu',
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
                         rule=dict(
                             comparison_operator='gt',
                             threshold=80.0,
                             evaluation_periods=6,
                             aggregation_method='mean',
                             granularity=50,
                             metric='cpu_util',
                             resource_type='instance',
                             query='{"=": {"server_group": '
                                   '"my_autoscaling_group"}}')
                         ),

        ]
        super(TestGnocchiEvaluatorBase, self).setUp()

    @staticmethod
    def _get_stats(granularity, values):
        now = timeutils.utcnow_ts()
        return [[six.text_type(now - len(values) * granularity),
                 granularity, value] for value in values]

    @staticmethod
    def _reason_data(disposition, count, most_recent):
        return {'type': 'threshold', 'disposition': disposition,
                'count': count, 'most_recent': most_recent}

    def _set_all_rules(self, field, value):
        for alarm in self.alarms:
            alarm.rule[field] = value

    def _test_retry_transient(self):
        self._evaluate_all_alarms()
        self._assert_all_alarms('insufficient data')
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')

    def _test_simple_insufficient(self):
        self._set_all_alarms('ok')
        self._evaluate_all_alarms()
        self._assert_all_alarms('insufficient data')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        expected = [mock.call(
            alarm,
            'ok',
            ('No datapoint for granularity %s'
             % alarm.rule['granularity']),
            self._reason_data('unknown',
                              alarm.rule['evaluation_periods'],
                              None))
            for alarm in self.alarms]
        self.assertEqual(expected, self.notifier.notify.call_args_list)


class TestGnocchiResourceThresholdEvaluate(TestGnocchiEvaluatorBase):
    EVALUATOR = gnocchi.GnocchiResourceThresholdEvaluator

    def prepare_alarms(self):
        self.alarms = self.prepared_alarms[0:1]

    def test_retry_transient_api_failure(self):
        means = self._get_stats(60, [self.alarms[0].rule['threshold'] - v
                                     for v in moves.xrange(5)])
        self.client.metric.get_measures.side_effect = [
            exceptions.ClientException(501, "error2"), means]
        self._test_retry_transient()

    def test_simple_insufficient(self):
        self.client.metric.get_measures.return_value = []
        self._test_simple_insufficient()

    @mock.patch.object(timeutils, 'utcnow')
    def test_simple_alarm_trip(self, utcnow):
        utcnow.return_value = datetime.datetime(2015, 1, 26, 12, 57, 0, 0)
        self._set_all_alarms('ok')
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(1, 6)])
        self.client.metric.get_measures.side_effect = [avgs]
        self._evaluate_all_alarms()
        start_alarm = "2015-01-26T12:51:00"
        end = "2015-01-26T12:57:00"

        self.assertEqual(
            [mock.call.get_measures(aggregation='mean', metric='cpu_util',
                                    granularity=60,
                                    resource_id='my_instance',
                                    start=start_alarm, stop=end)],
            self.client.metric.mock_calls)

        reason = ('Transition to alarm due to 5 samples outside threshold,'
                  ' most recent: %s' % avgs[-1][2])
        reason_data = self._reason_data('outside', 5, avgs[-1][2])
        expected = mock.call(self.alarms[0], 'ok', reason, reason_data)
        self.assertEqual(expected, self.notifier.notify.call_args)

    def test_simple_alarm_clear(self):
        self._set_all_alarms('alarm')
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] - v
                                    for v in moves.xrange(5)])

        self.client.metric.get_measures.side_effect = [avgs]

        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)

        reason = ('Transition to ok due to 5 samples inside'
                  ' threshold, most recent: %s' % avgs[-1][2])

        reason_data = self._reason_data('inside', 5, avgs[-1][2])
        expected = mock.call(self.alarms[0], 'alarm', reason, reason_data)
        self.assertEqual(expected, self.notifier.notify.call_args)

    def _construct_payloads(self):
        payloads = []
        reasons = ["Transition to alarm due to 5 samples outside threshold, "
                   "most recent: 85.0",
                   "Transition to alarm due to 4 samples outside threshold, "
                   "most recent: 7.0"]
        for alarm in self.alarms:
            num = self.alarms.index(alarm)
            type = models.AlarmChange.STATE_TRANSITION
            detail = json.dumps({'state': alarm.state,
                                 'transition_reason': reasons[num]})
            on_behalf_of = alarm.project_id
            severity = alarm.severity
            payload = dict(
                event_id='fake_event_id_%s' % num,
                alarm_id=alarm.alarm_id,
                type=type,
                detail=detail,
                user_id='fake_user_id',
                project_id='fake_project_id',
                on_behalf_of=on_behalf_of,
                timestamp=datetime.datetime(2015, 7, 26, 3, 33, 21, 876795),
                severity=severity)
            payloads.append(payload)
        return payloads

    @mock.patch.object(uuidutils, 'generate_uuid')
    @mock.patch.object(timeutils, 'utcnow')
    @mock.patch.object(messaging, 'get_notifier')
    def test_alarm_change_record(self, get_notifier, utcnow, mock_uuid):
        # the context.RequestContext() method need to generate uuid,
        # so we need to provide 'fake_uuid_0' and 'fake_uuid_1' for that.
        mock_uuid.side_effect = ['fake_event_id_0', 'fake_event_id_1']
        change_notifier = mock.MagicMock()
        get_notifier.return_value = change_notifier
        utcnow.return_value = datetime.datetime(2015, 7, 26, 3, 33, 21, 876795)

        self._set_all_alarms('ok')
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(1, 6)])

        self.client.metric.get_measures.side_effect = [avgs]

        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)

        payloads = self._construct_payloads()
        expected_payloads = [mock.call(p) for p in payloads]
        change_records = \
            self.storage_conn.record_alarm_change.call_args_list
        self.assertEqual(expected_payloads, change_records)
        notify_calls = change_notifier.info.call_args_list
        notification = "alarm.state_transition"
        expected_payloads = [mock.call(mock.ANY, notification, p)
                             for p in payloads]
        self.assertEqual(expected_payloads, notify_calls)

    def test_equivocal_from_known_state_ok(self):
        self._set_all_alarms('ok')
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(5)])
        self.client.metric.get_measures.side_effect = [avgs]

        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        self.assertEqual([],
                         self.storage_conn.update_alarm.call_args_list)
        self.assertEqual([], self.notifier.notify.call_args_list)

    def test_state_change_and_repeat_actions(self):
        self._set_all_alarms('ok')
        self.alarms[0].repeat_actions = True
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(1, 6)])

        self.client.metric.get_measures.side_effect = [avgs]

        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)

        reason = ('Transition to alarm due to 5 samples outside '
                  'threshold, most recent: %s' % avgs[-1][2])
        reason_data = self._reason_data('outside', 5, avgs[-1][2])
        expected = mock.call(self.alarms[0], 'ok', reason, reason_data)
        self.assertEqual(expected, self.notifier.notify.call_args)

    def test_equivocal_from_unknown(self):
        self._set_all_alarms('insufficient data')
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(1, 6)])

        self.client.metric.get_measures.side_effect = [avgs]

        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)

        reason = ('Transition to alarm due to 5 samples outside'
                  ' threshold, most recent: %s' % avgs[-1][2])
        reason_data = self._reason_data('outside', 5, avgs[-1][2])
        expected = mock.call(self.alarms[0], 'insufficient data',
                             reason, reason_data)
        self.assertEqual(expected, self.notifier.notify.call_args)

    @unittest.skipIf(six.PY3,
                     "the aodh base class is not python 3 ready")
    @mock.patch.object(timeutils, 'utcnow')
    def test_no_state_change_outside_time_constraint(self, mock_utcnow):
        self._set_all_alarms('ok')
        self.alarms[0].time_constraints = [
            {'name': 'test',
             'description': 'test',
             'start': '0 11 * * *',  # daily at 11:00
             'duration': 10800,  # 3 hours
             'timezone': 'Europe/Ljubljana'}
        ]
        dt = datetime.datetime(2014, 1, 1, 15, 0, 0,
                               tzinfo=pytz.timezone('Europe/Ljubljana'))
        mock_utcnow.return_value = dt.astimezone(pytz.UTC)
        self.client.metric.get_measures.return_value = []
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual([], update_calls,
                         "Alarm should not change state if the current "
                         " time is outside its time constraint.")
        self.assertEqual([], self.notifier.notify.call_args_list)

    @unittest.skipIf(six.PY3,
                     "the aodh base class is not python 3 ready")
    @mock.patch.object(timeutils, 'utcnow')
    def test_state_change_inside_time_constraint(self, mock_utcnow):
        self._set_all_alarms('ok')
        self.alarms[0].time_constraints = [
            {'name': 'test',
             'description': 'test',
             'start': '0 11 * * *',  # daily at 11:00
             'duration': 10800,  # 3 hours
             'timezone': 'Europe/Ljubljana'}
        ]
        dt = datetime.datetime(2014, 1, 1, 12, 0, 0,
                               tzinfo=pytz.timezone('Europe/Ljubljana'))
        mock_utcnow.return_value = dt.astimezone(pytz.UTC)
        self.client.metric.get_measures.return_value = []
        self._evaluate_all_alarms()
        self._assert_all_alarms('insufficient data')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls,
                         "Alarm should change state if the current "
                         "time is inside its time constraint.")
        expected = [mock.call(
            alarm,
            'ok',
            'No datapoint for granularity 60',
            self._reason_data('unknown',
                              alarm.rule['evaluation_periods'],
                              None))
                    for alarm in self.alarms]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    @mock.patch.object(timeutils, 'utcnow')
    def test_lag_configuration(self, mock_utcnow):
        mock_utcnow.return_value = datetime.datetime(2012, 7, 2, 10, 45)
        self.client.metric.get_measures.return_value = []

        self._set_all_alarms('ok')
        self._evaluate_all_alarms()
        self._set_all_alarms('ok')
        self.conf.set_override("additional_ingestion_lag", 42)
        self._evaluate_all_alarms()

        self.assertEqual([
            mock.call(aggregation='mean', granularity=60, metric='cpu_util',
                      resource_id='my_instance',
                      start='2012-07-02T10:39:00', stop='2012-07-02T10:45:00'),
            mock.call(aggregation='mean', granularity=60, metric='cpu_util',
                      resource_id='my_instance',
                      start='2012-07-02T10:38:18', stop='2012-07-02T10:45:00')
        ], self.client.metric.get_measures.mock_calls)

    @mock.patch.object(timeutils, 'utcnow')
    def test_evaluation_keep_alarm_attributes_constant(self, utcnow):
        utcnow.return_value = datetime.datetime(2015, 7, 26, 3, 33, 21, 876795)
        self._set_all_alarms('ok')
        original_alarms = copy.deepcopy(self.alarms)
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(1, 6)])
        self.client.metric.get_measures.side_effect = [avgs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')
        primitive_alarms = [a.as_dict() for a in self.alarms]
        for alarm in original_alarms:
            alarm.state = 'alarm'
            alarm.state_reason = mock.ANY
        primitive_original_alarms = [a.as_dict() for a in original_alarms]
        self.assertEqual(primitive_original_alarms, primitive_alarms)


class TestGnocchiAggregationMetricsThresholdEvaluate(TestGnocchiEvaluatorBase):
    EVALUATOR = gnocchi.GnocchiAggregationMetricsThresholdEvaluator

    def prepare_alarms(self):
        self.alarms = self.prepared_alarms[1:2]

    def test_retry_transient_api_failure(self):
        maxs = self._get_stats(300, [self.alarms[0].rule['threshold'] + v
                                     for v in moves.xrange(4)])
        self.client.metric.aggregation.side_effect = [Exception('boom'), maxs]
        self._test_retry_transient()

    def test_simple_insufficient(self):
        self.client.metric.aggregation.return_value = []
        self._test_simple_insufficient()

    @mock.patch.object(timeutils, 'utcnow')
    def test_simple_alarm_trip(self, utcnow):
        utcnow.return_value = datetime.datetime(2015, 1, 26, 12, 57, 0, 0)
        self._set_all_alarms('ok')

        maxs = self._get_stats(300, [self.alarms[0].rule['threshold'] - v
                                     for v in moves.xrange(4)])
        self.client.metric.aggregation.side_effect = [maxs]
        self._evaluate_all_alarms()
        start_alarm = "2015-01-26T12:32:00"
        end = "2015-01-26T12:57:00"

        self.assertEqual(
            [mock.call.aggregation(aggregation='max',
                                   metrics=[
                                       '0bb1604d-1193-4c0a-b4b8-74b170e35e83',
                                       '9ddc209f-42f8-41e1-b8f1-8804f59c4053'],
                                   granularity=300,
                                   needed_overlap=0,
                                   start=start_alarm, stop=end)],
            self.client.metric.mock_calls)
        self._assert_all_alarms('alarm')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        reason = ('Transition to alarm due to 4 samples outside '
                  'threshold, most recent: %s' % maxs[-1][2])

        reason_data = self._reason_data('outside', 4, maxs[-1][2])
        expected = mock.call(self.alarms[0], 'ok', reason, reason_data)
        self.assertEqual(expected, self.notifier.notify.call_args)

    def test_simple_alarm_clear(self):
        self._set_all_alarms('alarm')
        maxs = self._get_stats(300, [self.alarms[0].rule['threshold'] + v
                                     for v in moves.xrange(1, 5)])
        self.client.metric.aggregation.side_effect = [maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        reason = ('Transition to ok due to 4 samples inside '
                  'threshold, most recent: %s' % maxs[-1][2])
        reason_data = self._reason_data('inside', 4, maxs[-1][2])
        expected = mock.call(self.alarms[0], 'alarm', reason, reason_data)

        self.assertEqual(expected, self.notifier.notify.call_args)

    def test_equivocal_from_known_state_ok(self):
        self._set_all_alarms('ok')
        maxs = self._get_stats(300, [self.alarms[0].rule['threshold'] - v
                                     for v in moves.xrange(-1, 3)])
        self.client.metric.aggregation.side_effect = [maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        self.assertEqual(
            [],
            self.storage_conn.update_alarm.call_args_list)
        self.assertEqual([], self.notifier.notify.call_args_list)

    def test_equivocal_ok_to_alarm(self):
        self._set_all_alarms('ok')
        # NOTE(sileht): we add one useless point (81.0) that will break
        # the test if the evaluator doesn't remove it.
        maxs = self._get_stats(300, [self.alarms[0].rule['threshold'] - v
                                     for v in moves.xrange(-1, 5)])
        self.client.metric.aggregation.side_effect = [maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')

    def test_equivocal_from_known_state_and_repeat_actions(self):
        self._set_all_alarms('ok')
        self.alarms[0].repeat_actions = True
        maxs = self._get_stats(300, [self.alarms[0].rule['threshold'] - v
                                     for v in moves.xrange(-1, 3)])
        self.client.metric.aggregation.side_effect = [maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        self.assertEqual([], self.storage_conn.update_alarm.call_args_list)
        reason = ('Remaining as ok due to 1 samples inside'
                  ' threshold, most recent: 8.0')
        reason_datas = self._reason_data('inside', 1, 8.0)
        expected = [mock.call(self.alarms[0], 'ok', reason, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_unequivocal_from_known_state_and_repeat_actions(self):
        self._set_all_alarms('alarm')
        self.alarms[0].repeat_actions = True

        maxs = self._get_stats(300, [self.alarms[0].rule['threshold'] - v
                                     for v in moves.xrange(4)])
        self.client.metric.aggregation.side_effect = [maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')
        self.assertEqual([], self.storage_conn.update_alarm.call_args_list)
        reason = ('Remaining as alarm due to 4 samples outside'
                  ' threshold, most recent: 7.0')
        reason_datas = self._reason_data('outside', 4, 7.0)
        expected = [mock.call(self.alarms[0], 'alarm',
                              reason, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)


class TestGnocchiAggregationResourcesThresholdEvaluate(
        TestGnocchiEvaluatorBase):
    EVALUATOR = gnocchi.GnocchiAggregationResourcesThresholdEvaluator

    def prepare_alarms(self):
        self.alarms = self.prepared_alarms[2:3]

    def test_retry_transient_api_failure(self):
        avgs2 = self._get_stats(50, [self.alarms[0].rule['threshold'] - v
                                     for v in moves.xrange(6)])
        self.client.metric.aggregation.side_effect = [
            exceptions.ClientException(500, "error"), avgs2]
        self._test_retry_transient()

    def test_simple_insufficient(self):
        self.client.metric.aggregation.return_value = []
        self._test_simple_insufficient()

    @mock.patch.object(timeutils, 'utcnow')
    def test_simple_alarm_trip(self, utcnow):
        utcnow.return_value = datetime.datetime(2015, 1, 26, 12, 57, 0, 0)
        self._set_all_alarms('ok')
        avgs = self._get_stats(50, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(1, 7)])

        self.client.metric.aggregation.side_effect = [avgs]
        self._evaluate_all_alarms()
        start_alarm = "2015-01-26T12:51:10"
        end = "2015-01-26T12:57:00"
        self.assertEqual(
            [mock.call.aggregation(aggregation='mean', metrics='cpu_util',
                                   granularity=50,
                                   needed_overlap=0,
                                   query={"=": {"server_group":
                                          "my_autoscaling_group"}},
                                   resource_type='instance',
                                   start=start_alarm, stop=end)],
            self.client.metric.mock_calls)
        self._assert_all_alarms('alarm')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        reason = ('Transition to alarm due to 6 samples outside '
                  'threshold, most recent: %s' % avgs[-1][2])
        reason_data = self._reason_data('outside', 6, avgs[-1][2])
        expected = mock.call(self.alarms[0], 'ok', reason, reason_data)
        self.assertEqual(expected, self.notifier.notify.call_args)

    def test_simple_alarm_clear(self):
        self._set_all_alarms('alarm')
        avgs = self._get_stats(50, [self.alarms[0].rule['threshold'] - v
                                    for v in moves.xrange(6)])
        self.client.metric.aggregation.side_effect = [avgs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        reason = ('Transition to ok due to 6 samples inside '
                  'threshold, most recent: %s' % avgs[-1][2])
        reason_data = self._reason_data('inside', 6, avgs[-1][2])
        expected = mock.call(self.alarms[0], 'alarm', reason, reason_data)
        self.assertEqual(expected, self.notifier.notify.call_args)

    def test_equivocal_from_known_state_ok(self):
        self._set_all_alarms('ok')
        avgs = self._get_stats(50, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(6)])
        self.client.metric.aggregation.side_effect = [avgs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        self.assertEqual(
            [],
            self.storage_conn.update_alarm.call_args_list)
        self.assertEqual([], self.notifier.notify.call_args_list)
