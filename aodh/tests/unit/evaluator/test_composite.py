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
"""Tests for aodh/evaluator/composite.py
"""

from ceilometerclient.v2 import statistics
import fixtures
import mock
from oslo_utils import timeutils
from oslo_utils import uuidutils
import six
from six import moves

from aodh import evaluator
from aodh.evaluator import composite
from aodh.storage import models
from aodh.tests import constants
from aodh.tests.unit.evaluator import base


class BaseCompositeEvaluate(base.TestEvaluatorBase):
    EVALUATOR = composite.CompositeEvaluator

    def setUp(self):
        self.client = self.useFixture(fixtures.MockPatch(
            'aodh.evaluator.gnocchi.client'
        )).mock.Client.return_value
        super(BaseCompositeEvaluate, self).setUp()

    @staticmethod
    def _get_stats(attr, value, count=1):
        return statistics.Statistics(None, {attr: value, 'count': count})

    @staticmethod
    def _get_gnocchi_stats(granularity, values):
        now = timeutils.utcnow_ts()
        return [[six.text_type(now - len(values) * granularity),
                 granularity, value] for value in values]

    @staticmethod
    def _reason(new_state, user_expression, causative_rules=(),
                transition=True):
        root_cause_rules = {}
        for index, rule in causative_rules:
            name = 'rule%s' % index
            root_cause_rules.update({name: rule})
        description = {evaluator.ALARM: 'outside their threshold.',
                       evaluator.OK: 'inside their threshold.',
                       evaluator.UNKNOWN: 'state evaluated to unknown.'}
        params = {'state': new_state,
                  'expression': user_expression,
                  'rules': ', '.join(sorted(six.iterkeys(root_cause_rules))),
                  'description': description[new_state]}
        reason_data = {
            'type': 'composite',
            'composition_form': user_expression}
        reason_data.update(causative_rules=root_cause_rules)
        if transition:
            reason = ('Composite rule alarm with composition form: '
                      '%(expression)s transition to %(state)s, due to '
                      'rules: %(rules)s %(description)s' % params)
        else:
            reason = ('Composite rule alarm with composition form: '
                      '%(expression)s remaining as %(state)s, due to '
                      'rules: %(rules)s %(description)s' % params)
        return reason, reason_data


class CompositeTest(BaseCompositeEvaluate):
    sub_rule1 = {
        "type": "threshold",
        "meter_name": "cpu_util",
        "evaluation_periods": 5,
        "threshold": 0.8,
        "query": [{
            "field": "metadata.metering.stack_id",
            "value": "36b20eb3-d749-4964-a7d2-a71147cd8145",
            "op": "eq"
        }],
        "statistic": "avg",
        "period": 60,
        "exclude_outliers": False,
        "comparison_operator": "gt"
    }

    sub_rule2 = {
        "type": "threshold",
        "meter_name": "disk.iops",
        "evaluation_periods": 4,
        "threshold": 200,
        "query": [{
            "field": "metadata.metering.stack_id",
            "value": "36b20eb3-d749-4964-a7d2-a71147cd8145",
            "op": "eq"
        }],
        "statistic": "max",
        "period": 60,
        "exclude_outliers": False,
        "comparison_operator": "gt"
    }

    sub_rule3 = {
        "type": "threshold",
        "meter_name": "network.incoming.packets.rate",
        "evaluation_periods": 3,
        "threshold": 1000,
        "query": [{
            "field": "metadata.metering.stack_id",
            "value": "36b20eb3-d749-4964-a7d2-a71147cd8145",
            "op": "eq"
        }],
        "statistic": "avg",
        "period": 60,
        "exclude_outliers": False,
        "comparison_operator": "gt"
    }

    sub_rule4 = {
        "type": "gnocchi_resources_threshold",
        'comparison_operator': 'gt',
        'threshold': 80.0,
        'evaluation_periods': 5,
        'aggregation_method': 'mean',
        'granularity': 60,
        'metric': 'cpu_util',
        'resource_type': 'instance',
        'resource_id': 'my_instance',
    }

    sub_rule5 = {
        "type": "gnocchi_aggregation_by_metrics_threshold",
        'comparison_operator': 'le',
        'threshold': 10.0,
        'evaluation_periods': 4,
        'aggregation_method': 'max',
        'granularity': 300,
        'metrics': ['0bb1604d-1193-4c0a-b4b8-74b170e35e83',
                    '9ddc209f-42f8-41e1-b8f1-8804f59c4053']
    }

    sub_rule6 = {
        "type": "gnocchi_aggregation_by_resources_threshold",
        'comparison_operator': 'gt',
        'threshold': 80.0,
        'evaluation_periods': 6,
        'aggregation_method': 'mean',
        'granularity': 50,
        'metric': 'cpu_util',
        'resource_type': 'instance',
        'query': '{"=": {"server_group": "my_autoscaling_group"}}'
    }

    def prepare_alarms(self):
        self.alarms = [
            models.Alarm(name='alarm_threshold_nest',
                         description='alarm with sub rules nested combined',
                         type='composite',
                         enabled=True,
                         user_id='fake_user',
                         project_id='fake_project',
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
                         rule={
                             "or": [self.sub_rule1,
                                    {"and": [self.sub_rule2, self.sub_rule3]
                                     }]
                         },
                         severity='critical'),
            models.Alarm(name='alarm_threshold_or',
                         description='alarm on one of sub rules triggered',
                         type='composite',
                         enabled=True,
                         user_id='fake_user',
                         project_id='fake_project',
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
                         rule={
                             "or": [self.sub_rule1, self.sub_rule2,
                                    self.sub_rule3]
                         },
                         severity='critical'
                         ),
            models.Alarm(name='alarm_threshold_and',
                         description='alarm on all the sub rules triggered',
                         type='composite',
                         enabled=True,
                         user_id='fake_user',
                         project_id='fake_project',
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
                         rule={
                             "and": [self.sub_rule1, self.sub_rule2,
                                     self.sub_rule3]
                         },
                         severity='critical'
                         ),
            models.Alarm(name='alarm_multi_type_rules',
                         description='alarm with threshold and gnocchi rules',
                         type='composite',
                         enabled=True,
                         user_id='fake_user',
                         project_id='fake_project',
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
                         rule={
                             "and": [self.sub_rule2, self.sub_rule3,
                                     {'or': [self.sub_rule1, self.sub_rule4,
                                             self.sub_rule5, self.sub_rule6]}]
                         },
                         severity='critical'
                         ),
        ]

    def test_simple_insufficient(self):
        self._set_all_alarms('ok')
        self.api_client.statistics.list.return_value = []
        self.client.metric.aggregation.return_value = []
        self.client.metric.get_measures.return_value = []
        self._evaluate_all_alarms()
        self._assert_all_alarms('insufficient data')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        expected = [mock.call(self.alarms[0],
                              'ok',
                              *self._reason(
                                  'insufficient data',
                                  '(rule1 or (rule2 and rule3))',
                                  ((1, self.sub_rule1), (2, self.sub_rule2),
                                   (3, self.sub_rule3)))),
                    mock.call(self.alarms[1],
                              'ok',
                              *self._reason(
                                  'insufficient data',
                                  '(rule1 or rule2 or rule3)',
                                  ((1, self.sub_rule1), (2, self.sub_rule2),
                                   (3, self.sub_rule3)))),
                    mock.call(self.alarms[2],
                              'ok',
                              *self._reason(
                                  'insufficient data',
                                  '(rule1 and rule2 and rule3)',
                                  ((1, self.sub_rule1), (2, self.sub_rule2),
                                   (3, self.sub_rule3)))),
                    mock.call(
                        self.alarms[3],
                        'ok',
                        *self._reason(
                            'insufficient data',
                            '(rule1 and rule2 and (rule3 or rule4 or rule5 '
                            'or rule6))',
                            ((1, self.sub_rule2), (2, self.sub_rule3),
                             (3, self.sub_rule1), (4, self.sub_rule4),
                             (5, self.sub_rule5), (6, self.sub_rule6))))]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_alarm_full_trip_with_multi_type_rules(self):
        alarm = self.alarms[3]
        alarm.state = 'ok'
        # following results of sub-rules evaluation to trigger
        # final "alarm" state:
        # self.sub_rule2: alarm
        # self.sub_rule3: alarm
        # self.sub_rule1: ok
        # self.sub_rule4: ok
        # self.sub_rule5: ok
        # self.sub_rule6: alarm
        maxs = [self._get_stats('max', self.sub_rule2['threshold'] + 0.01 * v)
                for v in moves.xrange(1, 5)]
        avgs1 = [self._get_stats('avg', self.sub_rule3['threshold'] + 0.01 * v)
                 for v in moves.xrange(1, 4)]
        avgs2 = [self._get_stats('avg', self.sub_rule1['threshold'] - 0.01 * v)
                 for v in moves.xrange(1, 6)]

        gavgs1 = self._get_gnocchi_stats(60, [self.sub_rule4['threshold']
                                              - v for v in moves.xrange(1, 6)])
        gmaxs = self._get_gnocchi_stats(300, [self.sub_rule5['threshold'] + v
                                              for v in moves.xrange(1, 5)])
        gavgs2 = self._get_gnocchi_stats(50, [self.sub_rule6['threshold'] + v
                                              for v in moves.xrange(1, 7)])

        self.api_client.statistics.list.side_effect = [maxs, avgs1, avgs2]
        self.client.metric.get_measures.side_effect = [gavgs1]
        self.client.metric.aggregation.side_effect = [gmaxs, gavgs2]
        self.evaluator.evaluate(alarm)
        self.assertEqual(3, self.api_client.statistics.list.call_count)
        self.assertEqual(1, self.client.metric.get_measures.call_count)
        self.assertEqual(2, self.client.metric.aggregation.call_count)
        self.assertEqual('alarm', alarm.state)
        expected = mock.call(
            alarm, 'ok',
            *self._reason(
                'alarm',
                '(rule1 and rule2 and (rule3 or rule4 or rule5 or rule6))',
                ((1, self.sub_rule2), (2, self.sub_rule3),
                 (6, self.sub_rule6))))
        self.assertEqual(expected, self.notifier.notify.call_args)

    def test_alarm_with_short_circuit_logic(self):
        alarm = self.alarms[1]
        # self.sub_rule1: alarm
        avgs = [self._get_stats('avg', self.sub_rule1['threshold'] + 0.01 * v)
                for v in moves.xrange(1, 6)]
        self.api_client.statistics.list.side_effect = [avgs]
        self.evaluator.evaluate(alarm)
        self.assertEqual('alarm', alarm.state)
        self.assertEqual(1, self.api_client.statistics.list.call_count)
        expected = mock.call(self.alarms[1], 'insufficient data',
                             *self._reason(
                                 'alarm',
                                 '(rule1 or rule2 or rule3)',
                                 ((1, self.sub_rule1),)))
        self.assertEqual(expected, self.notifier.notify.call_args)

    def test_ok_with_short_circuit_logic(self):
        alarm = self.alarms[2]
        # self.sub_rule1: ok
        avgs = [self._get_stats('avg', self.sub_rule1['threshold'] - 0.01 * v)
                for v in moves.xrange(1, 6)]
        self.api_client.statistics.list.side_effect = [avgs]
        self.evaluator.evaluate(alarm)
        self.assertEqual('ok', alarm.state)
        self.assertEqual(1, self.api_client.statistics.list.call_count)
        expected = mock.call(self.alarms[2], 'insufficient data',
                             *self._reason(
                                 'ok',
                                 '(rule1 and rule2 and rule3)',
                                 ((1, self.sub_rule1),)))
        self.assertEqual(expected, self.notifier.notify.call_args)

    def test_unknown_state_with_sub_rules_trending_state(self):
        alarm = self.alarms[0]
        maxs = [self._get_stats('max', self.sub_rule2['threshold'] + 0.01 * v)
                for v in moves.xrange(-1, 4)]
        avgs = [self._get_stats('avg', self.sub_rule3['threshold'] + 0.01 * v)
                for v in moves.xrange(-1, 3)]
        avgs2 = [self._get_stats('avg', self.sub_rule1['threshold'] - 0.01 * v)
                 for v in moves.xrange(1, 6)]
        self.api_client.statistics.list.side_effect = [avgs2, maxs, avgs]
        self.evaluator.evaluate(alarm)
        self.assertEqual('alarm', alarm.state)
        expected = mock.call(self.alarms[0], 'insufficient data',
                             *self._reason(
                                 'alarm',
                                 '(rule1 or (rule2 and rule3))',
                                 ((2, self.sub_rule2),
                                  (3, self.sub_rule3))))
        self.assertEqual(expected, self.notifier.notify.call_args)

    def test_known_state_with_sub_rules_trending_state(self):
        alarm = self.alarms[0]
        alarm.repeat_actions = True
        alarm.state = 'ok'
        maxs = [self._get_stats('max', self.sub_rule2['threshold'] + 0.01 * v)
                for v in moves.xrange(-1, 4)]
        avgs = [self._get_stats('avg', self.sub_rule3['threshold'] + 0.01 * v)
                for v in moves.xrange(-1, 3)]
        avgs2 = [self._get_stats('avg', self.sub_rule1['threshold'] - 0.01 * v)
                 for v in moves.xrange(1, 6)]
        self.api_client.statistics.list.side_effect = [avgs2, maxs, avgs]
        self.evaluator.evaluate(alarm)
        self.assertEqual('ok', alarm.state)
        expected = mock.call(self.alarms[0], 'ok',
                             *self._reason(
                                 'ok',
                                 '(rule1 or (rule2 and rule3))',
                                 ((1, self.sub_rule1),
                                  (2, self.sub_rule2),
                                  (3, self.sub_rule3)), False))
        self.assertEqual(expected, self.notifier.notify.call_args)

    def test_known_state_with_sub_rules_trending_state_and_not_repeat(self):
        alarm = self.alarms[2]
        alarm.state = 'ok'
        maxs = [self._get_stats('max', self.sub_rule2['threshold'] + 0.01 * v)
                for v in moves.xrange(-1, 4)]
        avgs = [self._get_stats('avg', self.sub_rule3['threshold'] + 0.01 * v)
                for v in moves.xrange(-1, 3)]
        avgs2 = [self._get_stats('avg', self.sub_rule1['threshold'] - 0.01 * v)
                 for v in moves.xrange(1, 6)]
        self.api_client.statistics.list.side_effect = [avgs2, maxs, avgs]
        self.evaluator.evaluate(alarm)
        self.assertEqual('ok', alarm.state)
        self.assertEqual([], self.notifier.notify.mock_calls)


class OtherCompositeTest(BaseCompositeEvaluate):
    sub_rule1 = {
        'evaluation_periods': 3,
        'metric': 'radosgw.objects.containers',
        'resource_id': 'alarm-resource-1',
        'aggregation_method': 'mean',
        'granularity': 60,
        'threshold': 5.0,
        'type': 'gnocchi_resources_threshold',
        'comparison_operator': 'ge',
        'resource_type': 'ceph_account'
    }

    sub_rule2 = {
        'evaluation_periods': 3,
        'metric': 'radosgw.objects.containers',
        'resource_id': 'alarm-resource-2',
        'aggregation_method': 'mean',
        'granularity': 60,
        'threshold': 5.0,
        'type': 'gnocchi_resources_threshold',
        'comparison_operator': 'ge',
        'resource_type': 'ceph_account'
    }

    def prepare_alarms(self):
        self.alarms = [
            models.Alarm(name='composite-GRT-OR-GRT',
                         description='composite alarm converted',
                         type='composite',
                         enabled=True,
                         user_id='fake_user',
                         project_id='fake_project',
                         state='insufficient data',
                         state_reason='insufficient data',
                         state_timestamp=constants.MIN_DATETIME,
                         timestamp=constants.MIN_DATETIME,
                         insufficient_data_actions=['log://'],
                         ok_actions=['log://'],
                         alarm_actions=['log://'],
                         repeat_actions=False,
                         alarm_id=uuidutils.generate_uuid(),
                         time_constraints=[],
                         rule={
                             "or": [self.sub_rule1, self.sub_rule2]
                         },
                         severity='critical'
                         ),
        ]

    def test_simple_ok(self):
        self._set_all_alarms('alarm')

        gavgs1 = [['2016-11-24T10:00:00+00:00', 3600.0, 3.0],
                  ['2016-11-24T10:00:00+00:00', 900.0, 3.0],
                  ['2016-11-24T10:00:00+00:00', 300.0, 3.0],
                  ['2016-11-24T10:01:00+00:00', 60.0, 2.0],
                  ['2016-11-24T10:02:00+00:00', 60.0, 3.0],
                  ['2016-11-24T10:03:00+00:00', 60.0, 4.0],
                  ['2016-11-24T10:04:00+00:00', 60.0, 5.0]]

        gavgs2 = [['2016-11-24T10:00:00+00:00', 3600.0, 3.0],
                  ['2016-11-24T10:00:00+00:00', 900.0, 3.0],
                  ['2016-11-24T10:00:00+00:00', 300.0, 3.0],
                  ['2016-11-24T10:01:00+00:00', 60.0, 2.0],
                  ['2016-11-24T10:02:00+00:00', 60.0, 3.0],
                  ['2016-11-24T10:03:00+00:00', 60.0, 4.0],
                  ['2016-11-24T10:04:00+00:00', 60.0, 5.0]]

        self.client.metric.get_measures.side_effect = [gavgs1, gavgs2]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        expected = [mock.call(self.alarms[0], 'alarm',
                              *self._reason('ok', '(rule1 or rule2)',
                                            ((1, self.sub_rule1),
                                             (2, self.sub_rule2))))]
        self.assertEqual(expected, self.notifier.notify.call_args_list)
