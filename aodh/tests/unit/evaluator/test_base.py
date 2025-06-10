#
# Copyright 2013 IBM Corp
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
import datetime
from unittest import mock

from oslo_utils import timeutils
from oslotest import base

from aodh import evaluator
from aodh import queue


class TestEvaluatorBaseClass(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        self.called = False

    def _notify(self, alarm, previous, reason, details):
        self.called = True
        raise Exception('Boom!')

    @mock.patch.object(queue, 'AlarmNotifier')
    def test_base_refresh(self, notifier):
        notifier.notify = self._notify

        class EvaluatorSub(evaluator.Evaluator):
            def evaluate(self, alarm):
                pass

        ev = EvaluatorSub(mock.MagicMock())
        ev.notifier = notifier
        ev.storage_conn = mock.MagicMock()
        ev._record_change = mock.MagicMock()
        ev._refresh(mock.MagicMock(), mock.MagicMock(),
                    mock.MagicMock(), mock.MagicMock())
        ev.storage_conn.update_alarm.assert_called_once_with(mock.ANY)
        ev._record_change.assert_called_once_with(mock.ANY, mock.ANY)
        self.assertTrue(self.called)

    @mock.patch.object(timeutils, 'utcnow')
    def test_base_time_constraints(self, mock_utcnow):
        alarm = mock.MagicMock()
        alarm.time_constraints = [
            {'name': 'test',
             'description': 'test',
             'start': '0 11 * * *',  # daily at 11:00
             'duration': 10800,  # 3 hours
             'timezone': ''},
            {'name': 'test2',
             'description': 'test',
             'start': '0 23 * * *',  # daily at 23:00
             'duration': 10800,  # 3 hours
             'timezone': ''},
        ]
        cls = evaluator.Evaluator
        mock_utcnow.return_value = datetime.datetime(2014, 1, 1, 12, 0, 0)
        self.assertTrue(cls.within_time_constraint(alarm))

        mock_utcnow.return_value = datetime.datetime(2014, 1, 2, 1, 0, 0)
        self.assertTrue(cls.within_time_constraint(alarm))

        mock_utcnow.return_value = datetime.datetime(2014, 1, 2, 5, 0, 0)
        self.assertFalse(cls.within_time_constraint(alarm))

    @mock.patch.object(timeutils, 'utcnow')
    def test_base_time_constraints_by_month(self, mock_utcnow):
        alarm = mock.MagicMock()
        alarm.time_constraints = [
            {'name': 'test',
             'description': 'test',
             'start': '0 11 31 1,3,5,7,8,10,12 *',  # every 31st at 11:00
             'duration': 10800,  # 3 hours
             'timezone': ''},
        ]
        cls = evaluator.Evaluator
        mock_utcnow.return_value = datetime.datetime(2015, 3, 31, 11, 30, 0)
        self.assertTrue(cls.within_time_constraint(alarm))

    @mock.patch.object(timeutils, 'utcnow')
    def test_base_time_constraints_complex(self, mock_utcnow):
        alarm = mock.MagicMock()
        alarm.time_constraints = [
            {'name': 'test',
             'description': 'test',
             # Every consecutive 2 minutes (from the 3rd to the 57th) past
             # every consecutive 2 hours (between 3:00 and 12:59) on every day.
             'start': '3-57/2 3-12/2 * * *',
             'duration': 30,
             'timezone': ''}
        ]
        cls = evaluator.Evaluator

        # test minutes inside
        mock_utcnow.return_value = datetime.datetime(2014, 1, 5, 3, 3, 0)
        self.assertTrue(cls.within_time_constraint(alarm))
        mock_utcnow.return_value = datetime.datetime(2014, 1, 5, 3, 31, 0)
        self.assertTrue(cls.within_time_constraint(alarm))
        mock_utcnow.return_value = datetime.datetime(2014, 1, 5, 3, 57, 0)
        self.assertTrue(cls.within_time_constraint(alarm))

        # test minutes outside
        mock_utcnow.return_value = datetime.datetime(2014, 1, 5, 3, 2, 0)
        self.assertFalse(cls.within_time_constraint(alarm))
        mock_utcnow.return_value = datetime.datetime(2014, 1, 5, 3, 4, 0)
        self.assertFalse(cls.within_time_constraint(alarm))
        mock_utcnow.return_value = datetime.datetime(2014, 1, 5, 3, 58, 0)
        self.assertFalse(cls.within_time_constraint(alarm))

        # test hours inside
        mock_utcnow.return_value = datetime.datetime(2014, 1, 5, 3, 31, 0)
        self.assertTrue(cls.within_time_constraint(alarm))
        mock_utcnow.return_value = datetime.datetime(2014, 1, 5, 5, 31, 0)
        self.assertTrue(cls.within_time_constraint(alarm))
        mock_utcnow.return_value = datetime.datetime(2014, 1, 5, 11, 31, 0)
        self.assertTrue(cls.within_time_constraint(alarm))

        # test hours outside
        mock_utcnow.return_value = datetime.datetime(2014, 1, 5, 1, 31, 0)
        self.assertFalse(cls.within_time_constraint(alarm))
        mock_utcnow.return_value = datetime.datetime(2014, 1, 5, 4, 31, 0)
        self.assertFalse(cls.within_time_constraint(alarm))
        mock_utcnow.return_value = datetime.datetime(2014, 1, 5, 12, 31, 0)
        self.assertFalse(cls.within_time_constraint(alarm))

    @mock.patch.object(timeutils, 'utcnow')
    def test_base_time_constraints_timezone(self, mock_utcnow):
        alarm = mock.MagicMock()
        cls = evaluator.Evaluator
        mock_utcnow.return_value = datetime.datetime(2014, 1, 1, 11, 0, 0)

        alarm.time_constraints = [
            {'name': 'test',
             'description': 'test',
             'start': '0 11 * * *',  # daily at 11:00
             'duration': 10800,  # 3 hours
             'timezone': 'Europe/Ljubljana'}
        ]
        self.assertTrue(cls.within_time_constraint(alarm))

        alarm.time_constraints = [
            {'name': 'test2',
             'description': 'test2',
             'start': '0 11 * * *',  # daily at 11:00
             'duration': 10800,  # 3 hours
             'timezone': 'US/Eastern'}
        ]
        self.assertFalse(cls.within_time_constraint(alarm))
