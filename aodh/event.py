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

from oslo_config import cfg
import oslo_messaging
from oslo_service import service

from aodh.evaluator import event
from aodh import messaging
from aodh import storage


OPTS = [
    cfg.StrOpt('event_alarm_topic',
               default='alarm.all',
               help='The topic that aodh uses for event alarm evaluation.'),
]


class EventAlarmEndpoint(object):

    def __init__(self, evaluator):
        self.evaluator = evaluator

    def sample(self, ctxt, publisher_id, event_type, payload, metadata):
        # TODO(r-mibu): requeue on error
        self.evaluator.evaluate_events(payload)


class EventAlarmEvaluationService(service.Service):

    def __init__(self, conf):
        super(EventAlarmEvaluationService, self).__init__()
        self.conf = conf
        self.storage_conn = storage.get_connection_from_config(self.conf)
        self.evaluator = event.EventAlarmEvaluator(self.conf)

    def start(self):
        super(EventAlarmEvaluationService, self).start()
        self.listener = messaging.get_notification_listener(
            messaging.get_transport(self.conf),
            [oslo_messaging.Target(topic=self.conf.event_alarm_topic)],
            [EventAlarmEndpoint(self.evaluator)])
        self.listener.start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def stop(self):
        self.listener.stop()
        self.listener.wait()
        super(EventAlarmEvaluationService, self).stop()
