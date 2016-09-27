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

import cotyledon
from oslo_config import cfg
from oslo_log import log
import oslo_messaging

from aodh.evaluator import event
from aodh import messaging
from aodh import storage

LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('event_alarm_topic',
               default='alarm.all',
               deprecated_group='DEFAULT',
               help='The topic that aodh uses for event alarm evaluation.'),
    cfg.IntOpt('batch_size',
               default=1,
               help='Number of notification messages to wait before '
               'dispatching them.'),
    cfg.IntOpt('batch_timeout',
               help='Number of seconds to wait before dispatching samples '
               'when batch_size is not reached (None means indefinitely).'),
]


class EventAlarmEndpoint(object):

    def __init__(self, evaluator):
        self.evaluator = evaluator

    def sample(self, notifications):
        LOG.debug('Received %s messages in batch.', len(notifications))
        for notification in notifications:
            self.evaluator.evaluate_events(notification['payload'])


class EventAlarmEvaluationService(cotyledon.Service):
    def __init__(self, worker_id, conf):
        super(EventAlarmEvaluationService, self).__init__(worker_id)
        self.conf = conf
        self.storage_conn = storage.get_connection_from_config(self.conf)
        self.evaluator = event.EventAlarmEvaluator(self.conf)
        self.listener = messaging.get_batch_notification_listener(
            messaging.get_transport(self.conf),
            [oslo_messaging.Target(
                topic=self.conf.listener.event_alarm_topic)],
            [EventAlarmEndpoint(self.evaluator)], False,
            self.conf.listener.batch_size,
            self.conf.listener.batch_timeout)
        self.listener.start()

    def terminate(self):
        self.listener.stop()
        self.listener.wait()
