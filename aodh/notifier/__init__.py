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
import logging

from oslo_config import cfg
import oslo_messaging
from oslo_service import service as os_service
from oslo_utils import netutils
import six
from stevedore import extension

from aodh.i18n import _
from aodh import messaging

OPTS = [
    cfg.StrOpt('ipc_protocol',
               default='queue',
               choices=['queue', 'rpc'],
               help='The protocol used to communicate between evaluator and '
                    'notifier services.'),
]

LOG = logging.getLogger(__name__)


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


class AlarmNotifierService(os_service.Service):
    NOTIFIER_EXTENSIONS_NAMESPACE = "aodh.notifier"

    def __init__(self, conf):
        super(AlarmNotifierService, self).__init__()
        transport = messaging.get_transport(conf)

        self.notifiers = extension.ExtensionManager(
            self.NOTIFIER_EXTENSIONS_NAMESPACE,
            invoke_on_load=True,
            invoke_args=(conf,))

        if conf.ipc_protocol == 'rpc':
            self.ipc = 'rpc'
            self.rpc_server = messaging.get_rpc_server(
                conf, transport, conf.notifier_rpc_topic, self)
        else:
            self.ipc = 'queue'
            target = oslo_messaging.Target(topic=conf.notifier_topic)
            self.listener = messaging.get_notification_listener(
                transport, [target],
                [AlarmEndpoint(self.notifiers)])

    def start(self):
        super(AlarmNotifierService, self).start()
        if self.ipc == 'rpc':
            self.rpc_server.start()
        else:
            self.listener.start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def stop(self):
        if self.ipc == 'rpc':
            self.rpc_server.stop()
        else:
            self.listener.stop()
            self.listener.wait()
        super(AlarmNotifierService, self).stop()

    def notify_alarm(self, context, data):
        process_alarm(self.notifiers, data)


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
            _("Unable to parse action %(action)s for alarm %(alarm_id)s"),
            {'action': action, 'alarm_id': alarm_id})
        return

    try:
        notifier = notifiers[action.scheme].obj
    except KeyError:
        scheme = action.scheme
        LOG.error(
            _("Action %(scheme)s for alarm %(alarm_id)s is unknown, "
              "cannot notify"),
            {'scheme': scheme, 'alarm_id': alarm_id})
        return

    try:
        LOG.debug("Notifying alarm %(id)s with action %(act)s",
                  {'id': alarm_id, 'act': action})
        notifier.notify(action, alarm_id, alarm_name, severity,
                        previous, current, reason, reason_data)
    except Exception:
        LOG.exception(_("Unable to notify alarm %s"), alarm_id)
        return


def process_alarm(notifiers, data):
    """Notify that alarm has been triggered.

    :param notifiers: list of possible notifiers
    :param data: (dict): alarm data
    """

    actions = data.get('actions')
    if not actions:
        LOG.error(_("Unable to notify for an alarm with no action"))
        return

    for action in actions:
        _handle_action(notifiers, action,
                       data.get('alarm_id'),
                       data.get('alarm_name'),
                       data.get('severity'),
                       data.get('previous'),
                       data.get('current'),
                       data.get('reason'),
                       data.get('reason_data'))


class AlarmEndpoint(object):

    def __init__(self, notifiers):
        self.notifiers = notifiers

    def sample(self, ctxt, publisher_id, event_type, payload, metadata):
        """Endpoint for alarm notifications"""
        process_alarm(self.notifiers, payload)
