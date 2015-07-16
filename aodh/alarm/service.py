#
# Copyright 2013 Red Hat, Inc
# Copyright 2013 eNovance <licensing@enovance.com>
#
# Authors: Eoghan Glynn <eglynn@redhat.com>
#          Julien Danjou <julien@danjou.info>
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

from oslo_config import cfg
from oslo_log import log
from oslo_service import service as os_service
from oslo_utils import netutils
import six
from stevedore import extension

from aodh import alarm as aodh_alarm
from aodh.alarm import rpc as rpc_alarm
from aodh import coordination as coordination
from aodh.i18n import _
from aodh import messaging
from aodh import storage


OPTS = [
    cfg.IntOpt('evaluation_interval',
               default=60,
               help='Period of evaluation cycle, should'
                    ' be >= than configured pipeline interval for'
                    ' collection of underlying meters.',
               deprecated_opts=[cfg.DeprecatedOpt(
                   'threshold_evaluation_interval', group='alarm')]),
]

cfg.CONF.register_opts(OPTS, group='alarm')

LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class AlarmService(object):

    def __init__(self):
        super(AlarmService, self).__init__()
        self.storage_conn = None
        self._load_evaluators()

    @property
    def _storage_conn(self):
        if not self.storage_conn:
            self.storage_conn = storage.get_connection_from_config(cfg.CONF)
        return self.storage_conn

    def _load_evaluators(self):
        self.evaluators = extension.ExtensionManager(
            namespace=aodh_alarm.EVALUATOR_EXTENSIONS_NAMESPACE,
            invoke_on_load=True,
            invoke_args=(rpc_alarm.RPCAlarmNotifier(),)
        )

    def _evaluate_assigned_alarms(self):
        try:
            alarms = self._assigned_alarms()
            LOG.info(_('initiating evaluation cycle on %d alarms') %
                     len(alarms))
            for alarm in alarms:
                self._evaluate_alarm(alarm)
        except Exception:
            LOG.exception(_('alarm evaluation cycle failed'))

    def _evaluate_alarm(self, alarm):
        """Evaluate the alarms assigned to this evaluator."""
        if alarm.type not in self.evaluators:
            LOG.debug(_('skipping alarm %s: type unsupported') %
                      alarm.alarm_id)
            return

        LOG.debug(_('evaluating alarm %s') % alarm.alarm_id)
        try:
            self.evaluators[alarm.type].obj.evaluate(alarm)
        except Exception:
            LOG.exception(_('Failed to evaluate alarm %s'), alarm.alarm_id)

    @abc.abstractmethod
    def _assigned_alarms(self):
        pass


class AlarmEvaluationService(AlarmService, os_service.Service):

    PARTITIONING_GROUP_NAME = "alarm_evaluator"

    def __init__(self):
        super(AlarmEvaluationService, self).__init__()
        self.partition_coordinator = coordination.PartitionCoordinator()

    def start(self):
        super(AlarmEvaluationService, self).start()
        self.storage_conn = storage.get_connection_from_config(cfg.CONF)
        self.partition_coordinator.start()
        self.partition_coordinator.join_group(self.PARTITIONING_GROUP_NAME)

        # allow time for coordination if necessary
        delay_start = self.partition_coordinator.is_active()

        if self.evaluators:
            interval = cfg.CONF.alarm.evaluation_interval
            self.tg.add_timer(
                interval,
                self._evaluate_assigned_alarms,
                initial_delay=interval if delay_start else None)
        if self.partition_coordinator.is_active():
            heartbeat_interval = min(cfg.CONF.coordination.heartbeat,
                                     cfg.CONF.alarm.evaluation_interval / 4)
            self.tg.add_timer(heartbeat_interval,
                              self.partition_coordinator.heartbeat)
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def _assigned_alarms(self):
        all_alarms = self._storage_conn.get_alarms(enabled=True)
        return self.partition_coordinator.extract_my_subset(
            self.PARTITIONING_GROUP_NAME, all_alarms)


class AlarmNotifierService(os_service.Service):

    def __init__(self):
        super(AlarmNotifierService, self).__init__()
        transport = messaging.get_transport()
        self.rpc_server = messaging.get_rpc_server(
            transport, cfg.CONF.alarm.notifier_rpc_topic, self)

    def start(self):
        super(AlarmNotifierService, self).start()
        self.rpc_server.start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def stop(self):
        self.rpc_server.stop()
        super(AlarmNotifierService, self).stop()

    def _handle_action(self, action, alarm_id, alarm_name, severity,
                       previous, current, reason, reason_data):
        try:
            action = netutils.urlsplit(action)
        except Exception:
            LOG.error(
                _("Unable to parse action %(action)s for alarm %(alarm_id)s"),
                {'action': action, 'alarm_id': alarm_id})
            return

        try:
            notifier = aodh_alarm.NOTIFIERS[action.scheme].obj
        except KeyError:
            scheme = action.scheme
            LOG.error(
                _("Action %(scheme)s for alarm %(alarm_id)s is unknown, "
                  "cannot notify"),
                {'scheme': scheme, 'alarm_id': alarm_id})
            return

        try:
            LOG.debug(_("Notifying alarm %(id)s with action %(act)s") % (
                      {'id': alarm_id, 'act': action}))
            notifier.notify(action, alarm_id, alarm_name, severity,
                            previous, current, reason, reason_data)
        except Exception:
            LOG.exception(_("Unable to notify alarm %s"), alarm_id)
            return

    def notify_alarm(self, context, data):
        """Notify that alarm has been triggered.

           :param context: Request context.
           :param data: (dict):

             - actions, the URL of the action to run; this is mapped to
               extensions automatically
             - alarm_id, the ID of the alarm that has been triggered
             - alarm_name, the name of the alarm that has been triggered
             - severity, the level of the alarm that has been triggered
             - previous, the previous state of the alarm
             - current, the new state the alarm has transitioned to
             - reason, the reason the alarm changed its state
             - reason_data, a dict representation of the reason
        """
        actions = data.get('actions')
        if not actions:
            LOG.error(_("Unable to notify for an alarm with no action"))
            return

        for action in actions:
            self._handle_action(action,
                                data.get('alarm_id'),
                                data.get('alarm_name'),
                                data.get('severity'),
                                data.get('previous'),
                                data.get('current'),
                                data.get('reason'),
                                data.get('reason_data'))
