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
import uuid

import mock

from aodh import evaluator
from aodh.evaluator import event as event_evaluator
from aodh.storage import models
from aodh.tests import constants
from aodh.tests.evaluator import base


class TestEventAlarmEvaluate(base.TestEvaluatorBase):
    EVALUATOR = event_evaluator.EventAlarmEvaluator

    @staticmethod
    def _alarm(**kwargs):
        alarm_id = kwargs.get('id') or str(uuid.uuid4())
        return models.Alarm(name=kwargs.get('name', alarm_id),
                            type='event',
                            enabled=True,
                            alarm_id=alarm_id,
                            description='desc',
                            state=kwargs.get('state', 'insufficient data'),
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
        return {'message_id': kwargs.get('id') or str(uuid.uuid4()),
                'event_type': kwargs.get('event_type', 'type0'),
                'traits': kwargs.get('traits', [])}

    def _do_test_event_alarm(self, alarms, events,
                             expect_project_in_query=None,
                             expect_alarm_states=None,
                             expect_alarm_updates=None,
                             expect_notifications=None):
        self.storage_conn.get_alarms.return_value = alarms

        self.evaluator.evaluate_events(events)

        if expect_project_in_query is not None:
            self.assertEqual([mock.call(enabled=True,
                                        alarm_type='event',
                                        project=expect_project_in_query)],
                             self.storage_conn.get_alarms.call_args_list)
        if expect_alarm_states is not None:
            for expected, alarm in zip(expect_alarm_states, alarms):
                self.assertEqual(expected, alarm.state)
        if expect_alarm_updates is not None:
            self.assertEqual([mock.call(a) for a in expect_alarm_updates],
                             self.storage_conn.update_alarm.call_args_list)
        if expect_notifications is not None:
            expected = []
            for n in expect_notifications:
                alarm = n['alarm']
                event = n['event']
                previous = n.get('previous', evaluator.UNKNOWN)
                reason = ('Event (message_id=%(e)s) hit the query of alarm '
                          '(id=%(a)s)' %
                          {'e': event['message_id'], 'a': alarm.alarm_id})
                data = {'type': 'event', 'event': event}
                expected.append(mock.call(alarm, previous, reason, data))
            self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_fire_alarm_in_the_same_project_id(self):
        alarm = self._alarm(project='project1')
        event = self._event(traits=[['project_id', 1, 'project1']])
        self._do_test_event_alarm([alarm], [event],
                                  expect_project_in_query='project1',
                                  expect_alarm_states=[evaluator.ALARM],
                                  expect_alarm_updates=[alarm],
                                  expect_notifications=[dict(alarm=alarm,
                                                             event=event)])

    def test_fire_alarm_in_the_same_tenant_id(self):
        alarm = self._alarm(project='project1')
        event = self._event(traits=[['tenant_id', 1, 'project1']])
        self._do_test_event_alarm([alarm], [event],
                                  expect_project_in_query='project1',
                                  expect_alarm_states=[evaluator.ALARM],
                                  expect_alarm_updates=[alarm],
                                  expect_notifications=[dict(alarm=alarm,
                                                             event=event)])

    def test_fire_alarm_in_project_none(self):
        alarm = self._alarm(project='')
        event = self._event()
        self._do_test_event_alarm([alarm], [event],
                                  expect_project_in_query='',
                                  expect_alarm_states=[evaluator.ALARM],
                                  expect_alarm_updates=[alarm],
                                  expect_notifications=[dict(alarm=alarm,
                                                             event=event)])

    def test_continue_following_evaluation_after_exception(self):
        alarms = [
            self._alarm(),
            self._alarm(),
        ]
        event = self._event()
        original = event_evaluator.EventAlarmEvaluator._sanitize(event)
        with mock.patch.object(event_evaluator.EventAlarmEvaluator,
                               '_sanitize',
                               side_effect=[Exception('boom'), original]):
            self._do_test_event_alarm(alarms, [event],
                                      expect_alarm_states=[evaluator.UNKNOWN,
                                                           evaluator.ALARM],
                                      expect_alarm_updates=[alarms[1]],
                                      expect_notifications=[
                                          dict(alarm=alarms[1], event=event)])

    def test_skip_event_missing_event_type(self):
        alarm = self._alarm()
        event = {'message_id': str(uuid.uuid4()), 'traits': []}
        self._do_test_event_alarm([alarm], [event],
                                  expect_alarm_states=[evaluator.UNKNOWN],
                                  expect_alarm_updates=[],
                                  expect_notifications=[])

    def test_skip_event_missing_message_id(self):
        alarm = self._alarm()
        event = {'event_type': 'type1', 'traits': []}
        self._do_test_event_alarm([alarm], [event],
                                  expect_alarm_states=[evaluator.UNKNOWN],
                                  expect_alarm_updates=[],
                                  expect_notifications=[])

    def test_continue_alarming_when_repeat_actions_enabled(self):
        alarm = self._alarm(repeat=True, state=evaluator.ALARM)
        event = self._event()
        self._do_test_event_alarm([alarm], [event],
                                  expect_alarm_states=[evaluator.ALARM],
                                  expect_alarm_updates=[],
                                  expect_notifications=[
                                      dict(alarm=alarm,
                                           event=event,
                                           previous=evaluator.ALARM)])

    def test_do_not_continue_alarming_when_repeat_actions_disabled(self):
        alarm = self._alarm(repeat=False, state=evaluator.ALARM)
        event = self._event()
        self._do_test_event_alarm([alarm], [event],
                                  expect_alarm_states=[evaluator.ALARM],
                                  expect_alarm_updates=[],
                                  expect_notifications=[])

    def test_skip_uninterested_event_type(self):
        alarm = self._alarm(event_type='compute.instance.exists')
        event = self._event(event_type='compute.instance.update')
        self._do_test_event_alarm([alarm], [event],
                                  expect_alarm_states=[evaluator.UNKNOWN],
                                  expect_alarm_updates=[],
                                  expect_notifications=[])

    def test_fire_alarm_event_type_pattern_matched(self):
        alarm = self._alarm(event_type='compute.instance.*')
        event = self._event(event_type='compute.instance.update')
        self._do_test_event_alarm([alarm], [event],
                                  expect_alarm_states=[evaluator.ALARM],
                                  expect_alarm_updates=[alarm],
                                  expect_notifications=[dict(alarm=alarm,
                                                             event=event)])

    def test_skip_event_type_pattern_unmatched(self):
        alarm = self._alarm(event_type='compute.instance.*')
        event = self._event(event_type='dummy.compute.instance')
        self._do_test_event_alarm([alarm], [event],
                                  expect_alarm_states=[evaluator.UNKNOWN],
                                  expect_alarm_updates=[],
                                  expect_notifications=[])

    def test_fire_alarm_query_matched(self):
        alarm = self._alarm(query=[dict(field="traits.state",
                                        value="stopped",
                                        op="eq")])
        event = self._event(traits=[['state', 1, 'stopped']])
        self._do_test_event_alarm([alarm], [event],
                                  expect_alarm_states=[evaluator.ALARM],
                                  expect_alarm_updates=[alarm],
                                  expect_notifications=[dict(alarm=alarm,
                                                             event=event)])

    def test_skip_query_unmatched(self):
        alarm = self._alarm(query=[dict(field="traits.state",
                                        value="stopped",
                                        op="eq")])
        event = self._event(traits=[['state', 1, 'active']])
        self._do_test_event_alarm([alarm], [event],
                                  expect_alarm_states=[evaluator.UNKNOWN],
                                  expect_alarm_updates=[],
                                  expect_notifications=[])
