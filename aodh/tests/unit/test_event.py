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

import mock
import time

from oslo_config import fixture as fixture_config
import oslo_messaging
from oslo_messaging import server

from aodh import event
from aodh import service
from aodh.tests import base as tests_base


class TestEventAlarmEvaluationService(tests_base.BaseTestCase):

    def setUp(self):
        super(TestEventAlarmEvaluationService, self).setUp()

        conf = service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf
        self.setup_messaging(self.CONF)
        self.service = event.EventAlarmEvaluationService(self.CONF)
        self._msg_notifier = oslo_messaging.Notifier(
            self.transport, topics=['alarm.all'], driver='messaging',
            publisher_id='test-publisher')

    @mock.patch('aodh.storage.get_connection_from_config',
                mock.MagicMock())
    def test_start_and_stop_service(self):
        self.addCleanup(self.service.stop)
        self.service.start()
        self.assertIsInstance(self.service.listener,
                              server.MessageHandlingServer)

    @mock.patch('aodh.storage.get_connection_from_config',
                mock.MagicMock())
    def test_listener_start_called(self):
        listener = mock.Mock()
        with mock.patch('aodh.messaging.get_batch_notification_listener',
                        return_value=listener):
            self.addCleanup(self.service.stop)
            self.service.start()
        self.assertTrue(listener.start.called)

    @mock.patch('aodh.event.EventAlarmEndpoint.sample')
    def test_batch_event_listener(self, mocked):
        received_events = []
        mocked.side_effect = lambda msg: received_events.append(msg)
        self.CONF.set_override("batch_size", 2, 'listener')
        with mock.patch('aodh.storage.get_connection_from_config'):
            self.svc = event.EventAlarmEvaluationService(self.CONF)
            self.svc.start()
        event1 = {'event_type': 'compute.instance.update',
                  'traits': ['foo', 'bar'],
                  'message_id': '20d03d17-4aba-4900-a179-dba1281a3451',
                  'generated': '2016-04-23T06:50:21.622739'}
        event2 = {'event_type': 'compute.instance.update',
                  'traits': ['foo', 'bar'],
                  'message_id': '20d03d17-4aba-4900-a179-dba1281a3452',
                  'generated': '2016-04-23T06:50:23.622739'}
        self._msg_notifier.sample({}, 'event', event1)
        self._msg_notifier.sample({}, 'event', event2)
        time.sleep(1)
        self.assertEqual(1, len(received_events))
        self.assertEqual(2, len(received_events[0]))
        self.svc.stop()
