#
# Copyright 2015 NEC Corporation.
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
import six

import mock
from oslo_serialization import jsonutils
from oslo_utils import timeutils
from oslo_utils import uuidutils

from aodh import evaluator
from aodh.evaluator import event as event_evaluator
from aodh.storage import models
from aodh.tests import constants
from aodh.tests.unit.evaluator import base


class TestEventAlarmEvaluate(base.TestEvaluatorBase):
    EVALUATOR = event_evaluator.EventAlarmEvaluator

    @staticmethod
    def _alarm(**kwargs):
        alarm_id = kwargs.get('id') or uuidutils.generate_uuid()
        return models.Alarm(name=kwargs.get('name', alarm_id),
                            type='event',
                            enabled=True,
                            alarm_id=alarm_id,
                            description='desc',
                            state=kwargs.get('state', 'insufficient data'),
                            state_reason='reason',
                            severity='critical',
                            state_timestamp=constants.MIN_DATETIME,
                            timestamp=constants.MIN_DATETIME,
                            ok_actions=[],
                            insufficient_data_actions=[],
                            alarm_actions=[],
                            repeat_actions=kwargs.get('repeat', False),
                            user_id='user',
                            project_id=kwargs.get('project', ''),
                            time_constraints=[],
                            rule=dict(event_type=kwargs.get('event_type', '*'),
                                      query=kwargs.get('query', [])))

    @staticmethod
    def _event(**kwargs):
        return {'message_id': kwargs.get('id') or uuidutils.generate_uuid(),
                'event_type': kwargs.get('event_type', 'type0'),
                'traits': kwargs.get('traits', [])}

    def _setup_alarm_storage(self, alarms):
        self._stored_alarms = {a.alarm_id: copy.deepcopy(a) for a in alarms}
        self._update_history = []

        def get_alarms(**kwargs):
            return (a for a in six.itervalues(self._stored_alarms))

        def update_alarm(alarm):
            self._stored_alarms[alarm.alarm_id] = copy.deepcopy(alarm)
            self._update_history.append(dict(alarm_id=alarm.alarm_id,
                                             state=alarm.state))

        self.storage_conn.get_alarms.side_effect = get_alarms
        self.storage_conn.update_alarm.side_effect = update_alarm

    def _setup_alarm_notifier(self):
        self._notification_history = []

        def notify(alarm, previous, reason, data):
            self._notification_history.append(dict(alarm_id=alarm.alarm_id,
                                                   state=alarm.state,
                                                   previous=previous,
                                                   reason=reason,
                                                   data=data))

        self.notifier.notify.side_effect = notify

    def _do_test_event_alarm(self, alarms, events,
                             expect_db_queries=None,
                             expect_alarm_states=None,
                             expect_alarm_updates=None,
                             expect_notifications=None):
        self._setup_alarm_storage(alarms)
        self._setup_alarm_notifier()

        self.evaluator.evaluate_events(events)

        if expect_db_queries is not None:
            expected = [mock.call(enabled=True,
                                  alarm_type='event',
                                  project=p) for p in expect_db_queries]
            self.assertEqual(expected,
                             self.storage_conn.get_alarms.call_args_list)

        if expect_alarm_states is not None:
            for alarm_id, state in six.iteritems(expect_alarm_states):
                self.assertEqual(state, self._stored_alarms[alarm_id].state)

        if expect_alarm_updates is not None:
            self.assertEqual(len(expect_alarm_updates),
                             len(self._update_history))
            for alarm, h in zip(expect_alarm_updates, self._update_history):
                expected = dict(alarm_id=alarm.alarm_id,
                                state=evaluator.ALARM)
                self.assertEqual(expected, h)

        if expect_notifications is not None:
            self.assertEqual(len(expect_notifications),
                             len(self._notification_history))
            for n, h in zip(expect_notifications, self._notification_history):
                alarm = n['alarm']
                event = n['event']
                previous = n.get('previous', evaluator.UNKNOWN)
                reason = ('Event <id=%(e)s,event_type=%(type)s> hits the '
                          'query <query=%(query)s>.') % {
                    'e': event['message_id'],
                    'type': event['event_type'],
                    'query': jsonutils.dumps(alarm.rule['query'],
                                             sort_keys=True)}
                data = {'type': 'event', 'event': event}
                expected = dict(alarm_id=alarm.alarm_id,
                                state=evaluator.ALARM,
                                previous=previous,
                                reason=reason,
                                data=data)
                self.assertEqual(expected, h)

    def test_fire_alarm_in_the_same_project_id(self):
        alarm = self._alarm(project='project1')
        event = self._event(traits=[['project_id', 1, 'project1']])
        self._do_test_event_alarm(
            [alarm], [event],
            expect_db_queries=['project1'],
            expect_alarm_states={alarm.alarm_id: evaluator.ALARM},
            expect_alarm_updates=[alarm],
            expect_notifications=[dict(alarm=alarm, event=event)])

    def test_fire_alarm_in_the_same_tenant_id(self):
        alarm = self._alarm(project='project1')
        event = self._event(traits=[['tenant_id', 1, 'project1']])
        self._do_test_event_alarm(
            [alarm], [event],
            expect_db_queries=['project1'],
            expect_alarm_states={alarm.alarm_id: evaluator.ALARM},
            expect_alarm_updates=[alarm],
            expect_notifications=[dict(alarm=alarm, event=event)])

    def test_fire_alarm_in_project_none(self):
        alarm = self._alarm(project='')
        event = self._event()
        self._do_test_event_alarm(
            [alarm], [event],
            expect_db_queries=[''],
            expect_alarm_states={alarm.alarm_id: evaluator.ALARM},
            expect_alarm_updates=[alarm],
            expect_notifications=[dict(alarm=alarm, event=event)])

    def test_continue_following_evaluation_after_exception(self):
        alarms = [
            self._alarm(id=1),
            self._alarm(id=2),
        ]
        event = self._event()

        original = self.evaluator._fire_alarm

        with mock.patch.object(event_evaluator.EventAlarmEvaluator,
                               '_fire_alarm') as _fire_alarm:
            def _side_effect(*args, **kwargs):
                _fire_alarm.side_effect = original
                return Exception('boom')

            _fire_alarm.side_effect = _side_effect

            self._do_test_event_alarm(
                alarms, [event],
                expect_alarm_states={alarms[0].alarm_id: evaluator.UNKNOWN,
                                     alarms[1].alarm_id: evaluator.ALARM},
                expect_alarm_updates=[alarms[1]],
                expect_notifications=[dict(alarm=alarms[1], event=event)])

    def test_skip_event_missing_event_type(self):
        alarm = self._alarm()
        event = {'message_id': uuidutils.generate_uuid(), 'traits': []}
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.UNKNOWN},
            expect_alarm_updates=[],
            expect_notifications=[])

    def test_skip_event_missing_message_id(self):
        alarm = self._alarm()
        event = {'event_type': 'type1', 'traits': []}
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.UNKNOWN},
            expect_alarm_updates=[],
            expect_notifications=[])

    def test_continue_alarming_when_repeat_actions_enabled(self):
        alarm = self._alarm(repeat=True, state=evaluator.ALARM)
        event = self._event()
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.ALARM},
            expect_alarm_updates=[alarm],
            expect_notifications=[dict(alarm=alarm, event=event,
                                       previous=evaluator.ALARM)])

    def test_do_not_continue_alarming_when_repeat_actions_disabled(self):
        alarm = self._alarm(repeat=False, state=evaluator.ALARM)
        event = self._event()
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.ALARM},
            expect_alarm_updates=[],
            expect_notifications=[])

    def test_skip_uninterested_event_type(self):
        alarm = self._alarm(event_type='compute.instance.exists')
        event = self._event(event_type='compute.instance.update')
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.UNKNOWN},
            expect_alarm_updates=[],
            expect_notifications=[])

    def test_fire_alarm_event_type_pattern_matched(self):
        alarm = self._alarm(event_type='compute.instance.*')
        event = self._event(event_type='compute.instance.update')
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.ALARM},
            expect_alarm_updates=[alarm],
            expect_notifications=[dict(alarm=alarm, event=event)])

    def test_skip_event_type_pattern_unmatched(self):
        alarm = self._alarm(event_type='compute.instance.*')
        event = self._event(event_type='dummy.compute.instance')
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.UNKNOWN},
            expect_alarm_updates=[],
            expect_notifications=[])

    def test_fire_alarm_query_matched_string(self):
        alarm = self._alarm(query=[dict(field="traits.state",
                                        value="stopped",
                                        op="eq")])
        event = self._event(traits=[['state', 1, 'stopped']])
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.ALARM},
            expect_alarm_updates=[alarm],
            expect_notifications=[dict(alarm=alarm, event=event)])

    def test_skip_query_unmatched_string(self):
        alarm = self._alarm(query=[dict(field="traits.state",
                                        value="stopped",
                                        op="eq")])
        event = self._event(traits=[['state', 1, 'active']])
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.UNKNOWN},
            expect_alarm_updates=[],
            expect_notifications=[])

    def test_fire_alarm_query_matched_integer(self):
        alarm = self._alarm(query=[dict(field="traits.instance_type_id",
                                        type="integer",
                                        value="5",
                                        op="eq")])
        event = self._event(traits=[['instance_type_id', 2, 5]])
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.ALARM},
            expect_alarm_updates=[alarm],
            expect_notifications=[dict(alarm=alarm, event=event)])

    def test_skip_query_unmatched_integer(self):
        alarm = self._alarm(query=[dict(field="traits.instance_type_id",
                                        type="integer",
                                        value="5",
                                        op="eq")])
        event = self._event(traits=[['instance_type_id', 2, 6]])
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.UNKNOWN},
            expect_alarm_updates=[],
            expect_notifications=[])

    def test_fire_alarm_query_matched_float(self):
        alarm = self._alarm(query=[dict(field="traits.io_read_kbs",
                                        type="float",
                                        value="123.456",
                                        op="eq")])
        event = self._event(traits=[['io_read_kbs', 3, 123.456]])
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.ALARM},
            expect_alarm_updates=[alarm],
            expect_notifications=[dict(alarm=alarm, event=event)])

    def test_skip_query_unmatched_float(self):
        alarm = self._alarm(query=[dict(field="traits.io_read_kbs",
                                        type="float",
                                        value="123.456",
                                        op="eq")])
        event = self._event(traits=[['io_read_kbs', 3, 456.123]])
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.UNKNOWN},
            expect_alarm_updates=[],
            expect_notifications=[])

    def test_fire_alarm_query_matched_datetime(self):
        alarm = self._alarm(query=[dict(field="traits.created_at",
                                        type="datetime",
                                        value="2015-09-01T18:52:27.214309",
                                        op="eq")])
        event = self._event(traits=[['created_at', 4,
                                     '2015-09-01T18:52:27.214309']])
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.ALARM},
            expect_alarm_updates=[alarm],
            expect_notifications=[dict(alarm=alarm, event=event)])

    def test_skip_query_unmatched_datetime(self):
        alarm = self._alarm(query=[dict(field="traits.created_at",
                                        type="datetime",
                                        value="2015-09-01T18:52:27.214309",
                                        op="eq")])
        event = self._event(traits=[['created_at', 4,
                                     '2015-09-02T18:52:27.214309']])
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.UNKNOWN},
            expect_alarm_updates=[],
            expect_notifications=[])

    def test_skip_alarm_due_to_uncompareable_trait(self):
        alarm = self._alarm(query=[dict(field="traits.created_at",
                                        type="datetime",
                                        value="2015-09-01T18:52:27.214309",
                                        op="eq")])
        event = self._event(traits=[['created_at', 3, 123.456]])
        self._do_test_event_alarm(
            [alarm], [event],
            expect_alarm_states={alarm.alarm_id: evaluator.UNKNOWN},
            expect_alarm_updates=[],
            expect_notifications=[])

    def test_event_alarm_cache_hit(self):
        alarm = self._alarm(project='project2', event_type='none')
        events = [
            self._event(traits=[['project_id', 1, 'project2']]),
            self._event(traits=[['project_id', 1, 'project2']]),
        ]
        self._do_test_event_alarm([alarm], events,
                                  expect_db_queries=['project2'])

    def test_event_alarm_cache_updated_after_fired(self):
        alarm = self._alarm(project='project2', event_type='type1',
                            repeat=False)
        events = [
            self._event(event_type='type1',
                        traits=[['project_id', 1, 'project2']]),
            self._event(event_type='type1',
                        traits=[['project_id', 1, 'project2']]),
        ]
        self._do_test_event_alarm(
            [alarm], events,
            expect_db_queries=['project2'],
            expect_alarm_states={alarm.alarm_id: evaluator.ALARM},
            expect_alarm_updates=[alarm],
            expect_notifications=[dict(alarm=alarm, event=events[0])])

    def test_event_alarm_caching_disabled(self):
        alarm = self._alarm(project='project2', event_type='none')
        events = [
            self._event(traits=[['project_id', 1, 'project2']]),
            self._event(traits=[['project_id', 1, 'project2']]),
        ]
        self.evaluator.conf.event_alarm_cache_ttl = 0
        self._do_test_event_alarm([alarm], events,
                                  expect_db_queries=['project2', 'project2'])

    @mock.patch.object(timeutils, 'utcnow')
    def test_event_alarm_cache_expired(self, mock_utcnow):
        alarm = self._alarm(project='project2', event_type='none')
        events = [
            self._event(traits=[['project_id', 1, 'project2']]),
            self._event(traits=[['project_id', 1, 'project2']]),
        ]
        mock_utcnow.side_effect = [
            datetime.datetime(2015, 1, 1, 0, 0, 0),
            datetime.datetime(2015, 1, 1, 1, 0, 0),
            datetime.datetime(2015, 1, 1, 1, 1, 0),
        ]
        self._do_test_event_alarm([alarm], events,
                                  expect_db_queries=['project2', 'project2'])

    def test_event_alarm_cache_miss(self):
        events = [
            self._event(traits=[['project_id', 1, 'project2']]),
            self._event(traits=[['project_id', 1, 'project3']]),
        ]
        self._do_test_event_alarm([], events,
                                  expect_db_queries=['project2', 'project3'])
