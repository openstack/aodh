#
# Copyright 2013-2015 eNovance <licensing@enovance.com>
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
from oslo_log import log
import six

from aodh import messaging
from aodh.storage import models

OPTS = [
    cfg.StrOpt('notifier_rpc_topic',
               default='alarm_notifier',
               deprecated_group='alarm',
               help='The topic that aodh uses for alarm notifier '
                    'messages.'),
]

LOG = log.getLogger(__name__)


class RPCAlarmNotifier(object):
    def __init__(self, conf):
        transport = messaging.get_transport(conf)
        self.client = messaging.get_rpc_client(
            transport, topic=conf.notifier_rpc_topic,
            version="1.0")

    def notify(self, alarm, previous, reason, reason_data):
        actions = getattr(alarm, models.Alarm.ALARM_ACTIONS_MAP[alarm.state])
        if not actions:
            LOG.debug('alarm %(alarm_id)s has no action configured '
                      'for state transition from %(previous)s to '
                      'state %(state)s, skipping the notification.',
                      {'alarm_id': alarm.alarm_id,
                       'previous': previous,
                       'state': alarm.state})
            return
        self.client.cast({},
                         'notify_alarm', data={
                             'actions': actions,
                             'alarm_id': alarm.alarm_id,
                             'alarm_name': alarm.name,
                             'severity': alarm.severity,
                             'previous': previous,
                             'current': alarm.state,
                             'reason': six.text_type(reason),
                             'reason_data': reason_data})
