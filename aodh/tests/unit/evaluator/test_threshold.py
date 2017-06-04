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
"""Tests for aodh/evaluator/threshold.py
"""
import copy
import datetime
import json

from ceilometerclient import exc
from ceilometerclient.v2 import statistics
import mock
from oslo_utils import timeutils
from oslo_utils import uuidutils
import pytz
from six import moves

from aodh.evaluator import threshold
from aodh import messaging
from aodh.storage import models
from aodh.tests import constants
from aodh.tests.unit.evaluator import base


class TestEvaluate(base.TestEvaluatorBase):
    EVALUATOR = threshold.ThresholdEvaluator

    def prepare_alarms(self):
        self.alarms = [
            models.Alarm(name='instance_running_hot',
                         description='instance_running_hot',
                         type='threshold',
                         enabled=True,
                         user_id='foobar',
                         project_id='snafu',
                         alarm_id=uuidutils.generate_uuid(),
                         state='insufficient data',
                         state_timestamp=constants.MIN_DATETIME,
                         state_reason='Not evaluated',
                         timestamp=constants.MIN_DATETIME,
                         insufficient_data_actions=[],
                         ok_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         time_constraints=[],
                         rule=dict(
                             comparison_operator='gt',
                             threshold=80.0,
                             evaluation_periods=5,
                             statistic='avg',
                             period=60,
                             meter_name='cpu_util',
                             query=[{'field': 'meter',
                                     'op': 'eq',
                                     'value': 'cpu_util'},
                                    {'field': 'resource_id',
                                     'op': 'eq',
                                     'value': 'my_instance'}]),
                         severity='critical'
                         ),
            models.Alarm(name='group_running_idle',
                         description='group_running_idle',
                         type='threshold',
                         enabled=True,
                         user_id='foobar',
                         project_id='snafu',
                         state='insufficient data',
                         state_timestamp=constants.MIN_DATETIME,
                         state_reason='Not evaluated',
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
                             statistic='max',
                             period=300,
                             meter_name='cpu_util',
                             query=[{'field': 'meter',
                                     'op': 'eq',
                                     'value': 'cpu_util'},
                                    {'field': 'metadata.user_metadata.AS',
                                     'op': 'eq',
                                     'value': 'my_group'}]),
                         severity='critical'
                         ),
        ]

    @staticmethod
    def _get_stat(attr, value, count=1):
        return statistics.Statistics(None, {attr: value, 'count': count})

    @staticmethod
    def _reason_data(disposition, count, most_recent):
        return {'type': 'threshold', 'disposition': disposition,
                'count': count, 'most_recent': most_recent}

    def _set_all_rules(self, field, value):
        for alarm in self.alarms:
            alarm.rule[field] = value

    def test_retry_transient_api_failure(self):
        broken = exc.CommunicationError(message='broken')
        avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] - v)
                for v in moves.xrange(5)]
        maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] + v)
                for v in moves.xrange(1, 5)]
        self.api_client.statistics.list.side_effect = [broken,
                                                       broken,
                                                       avgs,
                                                       maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('insufficient data')
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')

    def test_simple_insufficient(self):
        self._set_all_alarms('ok')
        self.api_client.statistics.list.return_value = []
        self._evaluate_all_alarms()
        self._assert_all_alarms('insufficient data')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        expected = [mock.call(
            alarm,
            'ok',
            ('%d datapoints are unknown'
             % alarm.rule['evaluation_periods']),
            self._reason_data('unknown',
                              alarm.rule['evaluation_periods'],
                              None))
            for alarm in self.alarms]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_less_insufficient_data(self):
        self._set_all_alarms('ok')
        avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] - v)
                for v in moves.xrange(4)]
        maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                for v in moves.xrange(1, 4)]
        self.api_client.statistics.list.side_effect = [avgs, maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('insufficient data')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(update_calls, expected)
        expected = [mock.call(
            alarm,
            'ok',
            ('%d datapoints are unknown'
             % alarm.rule['evaluation_periods']),
            self._reason_data('unknown',
                              alarm.rule['evaluation_periods'],
                              alarm.rule['threshold'] - 3))
            for alarm in self.alarms]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_simple_alarm_trip(self):
        self._set_all_alarms('ok')
        avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] + v)
                for v in moves.xrange(1, 6)]
        maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                for v in moves.xrange(4)]
        self.api_client.statistics.list.side_effect = [avgs, maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        reasons = ['Transition to alarm due to 5 samples outside'
                   ' threshold, most recent: %s' % avgs[-1].avg,
                   'Transition to alarm due to 4 samples outside'
                   ' threshold, most recent: %s' % maxs[-1].max]
        reason_datas = [self._reason_data('outside', 5, avgs[-1].avg),
                        self._reason_data('outside', 4, maxs[-1].max)]
        expected = [mock.call(alarm, 'ok', reason, reason_data)
                    for alarm, reason, reason_data
                    in zip(self.alarms, reasons, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    @mock.patch.object(timeutils, 'utcnow')
    def test_lag_configuration(self, mock_utcnow):
        mock_utcnow.return_value = datetime.datetime(2012, 7, 2, 10, 45)
        self.api_client.statistics.list.side_effect = []

        self._set_all_alarms('ok')
        self._evaluate_all_alarms()
        self._set_all_alarms('ok')
        self.conf.set_override("additional_ingestion_lag", 42)
        self._evaluate_all_alarms()

        self.assertEqual([
            mock.call(
                meter_name='cpu_util', period=60,
                q=[{'value': 'cpu_util', 'op': 'eq', 'field': 'meter'},
                   {'value': 'my_instance', 'op': 'eq',
                    'field': 'resource_id'},
                   {'value': '2012-07-02T10:45:00', 'op': 'le',
                    'field': 'timestamp'},
                   {'value': '2012-07-02T10:39:00', 'op': 'ge',
                    'field': 'timestamp'}]),
            mock.call(
                meter_name='cpu_util', period=300,
                q=[{'value': 'cpu_util', 'op': 'eq', 'field': 'meter'},
                   {'value': 'my_group', 'op': 'eq',
                    'field': 'metadata.user_metadata.AS'},
                   {'value': '2012-07-02T10:45:00', 'op': 'le',
                    'field': 'timestamp'},
                   {'value': '2012-07-02T10:20:00', 'op': 'ge',
                    'field': 'timestamp'}]),
            mock.call(
                meter_name='cpu_util', period=60,
                q=[{'value': 'cpu_util', 'op': 'eq', 'field': 'meter'},
                   {'value': 'my_instance', 'op': 'eq',
                    'field': 'resource_id'},
                   {'value': '2012-07-02T10:45:00', 'op': 'le',
                    'field': 'timestamp'},
                   {'value': '2012-07-02T10:38:18', 'op': 'ge',
                    'field': 'timestamp'}]),
            mock.call(
                meter_name='cpu_util', period=300,
                q=[{'value': 'cpu_util', 'op': 'eq', 'field': 'meter'},
                   {'value': 'my_group', 'op': 'eq',
                    'field': 'metadata.user_metadata.AS'},
                   {'value': '2012-07-02T10:45:00', 'op': 'le',
                    'field': 'timestamp'},
                   {'value': '2012-07-02T10:19:18', 'op': 'ge',
                    'field': 'timestamp'}])],
            self.api_client.statistics.list.mock_calls)

    def test_simple_alarm_clear(self):
        self._set_all_alarms('alarm')
        avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] - v)
                for v in moves.xrange(5)]
        maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] + v)
                for v in moves.xrange(1, 5)]
        self.api_client.statistics.list.side_effect = [avgs, maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        reasons = ['Transition to ok due to 5 samples inside'
                   ' threshold, most recent: %s' % avgs[-1].avg,
                   'Transition to ok due to 4 samples inside'
                   ' threshold, most recent: %s' % maxs[-1].max]
        reason_datas = [self._reason_data('inside', 5, avgs[-1].avg),
                        self._reason_data('inside', 4, maxs[-1].max)]
        expected = [mock.call(alarm, 'alarm', reason, reason_data)
                    for alarm, reason, reason_data
                    in zip(self.alarms, reasons, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

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
            payload = dict(
                event_id='fake_event_id_%s' % num,
                alarm_id=alarm.alarm_id,
                type=type,
                detail=detail,
                user_id='fake_user_id',
                project_id='fake_project_id',
                on_behalf_of=on_behalf_of,
                timestamp=datetime.datetime(2015, 7, 26, 3, 33, 21, 876795))
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
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] + v)
                    for v in moves.xrange(1, 6)]
            maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                    for v in moves.xrange(4)]
            self.api_client.statistics.list.side_effect = [avgs, maxs]
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

    def test_equivocal_from_known_state(self):
        self._set_all_alarms('ok')
        avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] + v)
                for v in moves.xrange(5)]
        maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                for v in moves.xrange(-1, 3)]
        self.api_client.statistics.list.side_effect = [avgs, maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        self.assertEqual(
            [],
            self.storage_conn.update_alarm.call_args_list)
        self.assertEqual([], self.notifier.notify.call_args_list)

    def test_equivocal_from_known_state_and_repeat_actions(self):
        self._set_all_alarms('ok')
        self.alarms[1].repeat_actions = True
        avgs = [self._get_stat('avg',
                               self.alarms[0].rule['threshold'] + v)
                for v in moves.xrange(5)]
        maxs = [self._get_stat('max',
                               self.alarms[1].rule['threshold'] - v)
                for v in moves.xrange(-1, 3)]
        self.api_client.statistics.list.side_effect = [avgs, maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        self.assertEqual([],
                         self.storage_conn.update_alarm.call_args_list)
        reason = ('Remaining as ok due to 1 samples inside'
                  ' threshold, most recent: 8.0')
        reason_datas = self._reason_data('inside', 1, 8.0)
        expected = [mock.call(self.alarms[1], 'ok', reason, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_unequivocal_from_known_state_and_repeat_actions(self):
        self._set_all_alarms('alarm')
        self.alarms[1].repeat_actions = True
        avgs = [self._get_stat('avg',
                               self.alarms[0].rule['threshold'] + v)
                for v in moves.xrange(1, 6)]
        maxs = [self._get_stat('max',
                               self.alarms[1].rule['threshold'] - v)
                for v in moves.xrange(4)]
        self.api_client.statistics.list.side_effect = [avgs, maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')
        self.assertEqual([],
                         self.storage_conn.update_alarm.call_args_list)
        reason = ('Remaining as alarm due to 4 samples outside'
                  ' threshold, most recent: 7.0')
        reason_datas = self._reason_data('outside', 4, 7.0)
        expected = [mock.call(self.alarms[1], 'alarm',
                              reason, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_state_change_and_repeat_actions(self):
        self._set_all_alarms('ok')
        self.alarms[0].repeat_actions = True
        self.alarms[1].repeat_actions = True
        avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] + v)
                for v in moves.xrange(1, 6)]
        maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                for v in moves.xrange(4)]
        self.api_client.statistics.list.side_effect = [avgs, maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        reasons = ['Transition to alarm due to 5 samples outside'
                   ' threshold, most recent: %s' % avgs[-1].avg,
                   'Transition to alarm due to 4 samples outside'
                   ' threshold, most recent: %s' % maxs[-1].max]
        reason_datas = [self._reason_data('outside', 5, avgs[-1].avg),
                        self._reason_data('outside', 4, maxs[-1].max)]
        expected = [mock.call(alarm, 'ok', reason, reason_data)
                    for alarm, reason, reason_data
                    in zip(self.alarms, reasons, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_evaluation_keep_alarm_attributes_constant(self):
        self._set_all_alarms('ok')
        original_alarms = copy.deepcopy(self.alarms)
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] + v)
                    for v in moves.xrange(1, 6)]
            maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                    for v in moves.xrange(4)]
            self.api_client.statistics.list.side_effect = [avgs, maxs]
            self._evaluate_all_alarms()
            self._assert_all_alarms('alarm')
            primitive_alarms = [a.as_dict() for a in self.alarms]
            for alarm in original_alarms:
                alarm.state = 'alarm'
                alarm.state_reason = mock.ANY
            primitive_original_alarms = [a.as_dict() for a in original_alarms]
            self.assertEqual(primitive_original_alarms, primitive_alarms)

    def test_equivocal_from_unknown(self):
        self._set_all_alarms('insufficient data')
        avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] + v)
                for v in moves.xrange(1, 6)]
        maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                for v in moves.xrange(-3, 1)]
        self.api_client.statistics.list.side_effect = [avgs, maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        reasons = ['Transition to alarm due to 5 samples outside'
                   ' threshold, most recent: %s' % avgs[-1].avg,
                   'Transition to alarm due to 1 samples outside'
                   ' threshold, most recent: %s' % maxs[-1].max]
        reason_datas = [self._reason_data('outside', 5, avgs[-1].avg),
                        self._reason_data('outside', 1, maxs[-1].max)]
        expected = [mock.call(alarm, 'insufficient data',
                              reason, reason_data)
                    for alarm, reason, reason_data
                    in zip(self.alarms, reasons, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def _do_test_bound_duration(self, start, exclude_outliers=None):
        alarm = self.alarms[0]
        if exclude_outliers is not None:
            alarm.rule['exclude_outliers'] = exclude_outliers
        with mock.patch.object(timeutils, 'utcnow') as mock_utcnow:
            mock_utcnow.return_value = datetime.datetime(2012, 7, 2, 10, 45)
            constraint = self.evaluator._bound_duration(alarm.rule)
            self.assertEqual((start, timeutils.utcnow().isoformat()),
                             constraint)

    def test_bound_duration_outlier_exclusion_defaulted(self):
        self._do_test_bound_duration('2012-07-02T10:39:00')

    def test_bound_duration_outlier_exclusion_clear(self):
        self._do_test_bound_duration('2012-07-02T10:39:00', False)

    def test_bound_duration_outlier_exclusion_set(self):
        self._do_test_bound_duration('2012-07-02T10:35:00', True)

    def _do_test_simple_alarm_trip_outlier_exclusion(self, exclude_outliers):
        self._set_all_rules('exclude_outliers', exclude_outliers)
        self._set_all_alarms('ok')
        # most recent datapoints inside threshold but with
        # anomalously low sample count
        threshold = self.alarms[0].rule['threshold']
        avgs = [self._get_stat('avg',
                               threshold + (v if v < 10 else -v),
                               count=20 if v < 10 else 1)
                for v in moves.xrange(1, 11)]
        threshold = self.alarms[1].rule['threshold']
        maxs = [self._get_stat('max',
                               threshold - (v if v < 7 else -v),
                               count=20 if v < 7 else 1)
                for v in moves.xrange(8)]
        self.api_client.statistics.list.side_effect = [avgs, maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm' if exclude_outliers else 'ok')
        if exclude_outliers:
            expected = [mock.call(alarm) for alarm in self.alarms]
            update_calls = self.storage_conn.update_alarm.call_args_list
            self.assertEqual(expected, update_calls)
            reasons = ['Transition to alarm due to 5 samples outside'
                       ' threshold, most recent: %s' % avgs[-2].avg,
                       'Transition to alarm due to 4 samples outside'
                       ' threshold, most recent: %s' % maxs[-2].max]
            reason_datas = [self._reason_data('outside', 5, avgs[-2].avg),
                            self._reason_data('outside', 4, maxs[-2].max)]
            expected = [mock.call(alarm, 'ok', reason, reason_data)
                        for alarm, reason, reason_data
                        in zip(self.alarms, reasons, reason_datas)]
            self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_simple_alarm_trip_with_outlier_exclusion(self):
        self. _do_test_simple_alarm_trip_outlier_exclusion(True)

    def test_simple_alarm_no_trip_without_outlier_exclusion(self):
        self. _do_test_simple_alarm_trip_outlier_exclusion(False)

    def _do_test_simple_alarm_clear_outlier_exclusion(self, exclude_outliers):
        self._set_all_rules('exclude_outliers', exclude_outliers)
        self._set_all_alarms('alarm')
        # most recent datapoints outside threshold but with
        # anomalously low sample count
        threshold = self.alarms[0].rule['threshold']
        avgs = [self._get_stat('avg',
                               threshold - (v if v < 9 else -v),
                               count=20 if v < 9 else 1)
                for v in moves.xrange(10)]
        threshold = self.alarms[1].rule['threshold']
        maxs = [self._get_stat('max',
                               threshold + (v if v < 8 else -v),
                               count=20 if v < 8 else 1)
                for v in moves.xrange(1, 9)]
        self.api_client.statistics.list.side_effect = [avgs, maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok' if exclude_outliers else 'alarm')
        if exclude_outliers:
            expected = [mock.call(alarm) for alarm in self.alarms]
            update_calls = self.storage_conn.update_alarm.call_args_list
            self.assertEqual(expected, update_calls)
            reasons = ['Transition to ok due to 5 samples inside'
                       ' threshold, most recent: %s' % avgs[-2].avg,
                       'Transition to ok due to 4 samples inside'
                       ' threshold, most recent: %s' % maxs[-2].max]
            reason_datas = [self._reason_data('inside', 5, avgs[-2].avg),
                            self._reason_data('inside', 4, maxs[-2].max)]
            expected = [mock.call(alarm, 'alarm', reason, reason_data)
                        for alarm, reason, reason_data
                        in zip(self.alarms, reasons, reason_datas)]
            self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_simple_alarm_clear_with_outlier_exclusion(self):
        self. _do_test_simple_alarm_clear_outlier_exclusion(True)

    def test_simple_alarm_no_clear_without_outlier_exclusion(self):
        self. _do_test_simple_alarm_clear_outlier_exclusion(False)

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
        self.alarms[1].time_constraints = self.alarms[0].time_constraints
        dt = datetime.datetime(2014, 1, 1, 12, 0, 0,
                               tzinfo=pytz.timezone('Europe/Ljubljana'))
        mock_utcnow.return_value = dt.astimezone(pytz.UTC)
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            # the following part based on test_simple_insufficient
            self.api_client.statistics.list.return_value = []
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
                ('%d datapoints are unknown'
                 % alarm.rule['evaluation_periods']),
                self._reason_data('unknown',
                                  alarm.rule['evaluation_periods'],
                                  None))
                for alarm in self.alarms]
            self.assertEqual(expected, self.notifier.notify.call_args_list)

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
        self.alarms[1].time_constraints = self.alarms[0].time_constraints
        dt = datetime.datetime(2014, 1, 1, 15, 0, 0,
                               tzinfo=pytz.timezone('Europe/Ljubljana'))
        mock_utcnow.return_value = dt.astimezone(pytz.UTC)
        self.api_client.statistics.list.return_value = []
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual([], update_calls,
                         "Alarm should not change state if the current "
                         " time is outside its time constraint.")
        self.assertEqual([], self.notifier.notify.call_args_list)
