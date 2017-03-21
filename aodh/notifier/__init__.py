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

import abc

import cotyledon
from oslo_config import cfg
from oslo_log import log
import oslo_messaging
from oslo_utils import netutils
import six
from stevedore import extension

from aodh import messaging


LOG = log.getLogger(__name__)

OPTS = [
    cfg.IntOpt('batch_size',
               default=1,
               help='Number of notification messages to wait before '
                    'dispatching them.'),
    cfg.IntOpt('batch_timeout',
               help='Number of seconds to wait before dispatching samples '
                    'when batch_size is not reached (None means indefinitely).'
               ),
]


@six.add_metaclass(abc.ABCMeta)
class AlarmNotifier(object):
    """Base class for alarm notifier plugins."""

    @staticmethod
    def __init__(conf):
        pass

    @abc.abstractmethod
    def notify(self, action, alarm_id, alarm_name, severity, previous,
               current, reason, reason_data):
        """Notify that an alarm has been triggered.

        :param action: The action that is being attended, as a parsed URL.
        :param alarm_id: The triggered alarm.
        :param alarm_name: The name of triggered alarm.
        :param severity: The level of triggered alarm
        :param previous: The previous state of the alarm.
        :param current: The current state of the alarm.
        :param reason: The reason the alarm changed its state.
        :param reason_data: A dict representation of the reason.
        """


class AlarmNotifierService(cotyledon.Service):
    NOTIFIER_EXTENSIONS_NAMESPACE = "aodh.notifier"

    def __init__(self, worker_id, conf):
        super(AlarmNotifierService, self).__init__(worker_id)
        self.conf = conf
        transport = messaging.get_transport(self.conf)
        self.notifiers = extension.ExtensionManager(
            self.NOTIFIER_EXTENSIONS_NAMESPACE,
            invoke_on_load=True,
            invoke_args=(self.conf,))

        target = oslo_messaging.Target(topic=self.conf.notifier_topic)
        self.listener = messaging.get_batch_notification_listener(
            transport, [target], [AlarmEndpoint(self.notifiers)], False,
            self.conf.notifier.batch_size, self.conf.notifier.batch_timeout)
        self.listener.start()

    def terminate(self):
        self.listener.stop()
        self.listener.wait()


class AlarmEndpoint(object):

    def __init__(self, notifiers):
        self.notifiers = notifiers

    def sample(self, notifications):
        """Endpoint for alarm notifications"""
        LOG.debug('Received %s messages in batch.', len(notifications))
        for notification in notifications:
            self._process_alarm(self.notifiers, notification['payload'])

    @staticmethod
    def _handle_action(notifiers, action, alarm_id, alarm_name, severity,
                       previous, current, reason, reason_data):
        """Process action on alarm

        :param notifiers: list of possible notifiers.
        :param action: The action that is being attended, as a parsed URL.
        :param alarm_id: The triggered alarm.
        :param alarm_name: The name of triggered alarm.
        :param severity: The level of triggered alarm
        :param previous: The previous state of the alarm.
        :param current: The current state of the alarm.
        :param reason: The reason the alarm changed its state.
        :param reason_data: A dict representation of the reason.
        """

        try:
            action = netutils.urlsplit(action)
        except Exception:
            LOG.error(
                ("Unable to parse action %(action)s for alarm "
                 "%(alarm_id)s"), {'action': action, 'alarm_id': alarm_id})
            return

        try:
            notifier = notifiers[action.scheme].obj
        except KeyError:
            scheme = action.scheme
            LOG.error(
                ("Action %(scheme)s for alarm %(alarm_id)s is unknown, "
                 "cannot notify"),
                {'scheme': scheme, 'alarm_id': alarm_id})
            return

        try:
            LOG.debug("Notifying alarm %(id)s with action %(act)s",
                      {'id': alarm_id, 'act': action})
            notifier.notify(action, alarm_id, alarm_name, severity,
                            previous, current, reason, reason_data)
        except Exception:
            LOG.exception("Unable to notify alarm %s", alarm_id)

    @staticmethod
    def _process_alarm(notifiers, data):
        """Notify that alarm has been triggered.

        :param notifiers: list of possible notifiers
        :param data: (dict): alarm data
        """

        actions = data.get('actions')
        if not actions:
            LOG.error("Unable to notify for an alarm with no action")
            return

        for action in actions:
            AlarmEndpoint._handle_action(notifiers, action,
                                         data.get('alarm_id'),
                                         data.get('alarm_name'),
                                         data.get('severity'),
                                         data.get('previous'),
                                         data.get('current'),
                                         data.get('reason'),
                                         data.get('reason_data'))
