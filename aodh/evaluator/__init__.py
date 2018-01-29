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
import datetime
import json
import threading

from concurrent import futures
import cotyledon
import croniter
from futurist import periodics
from oslo_config import cfg
from oslo_log import log
from oslo_utils import timeutils
from oslo_utils import uuidutils
import pytz
import six
from stevedore import extension

import aodh
from aodh import coordination
from aodh import keystone_client
from aodh import messaging
from aodh import queue
from aodh import storage
from aodh.storage import models

LOG = log.getLogger(__name__)

UNKNOWN = 'insufficient data'
OK = 'ok'
ALARM = 'alarm'


OPTS = [
    cfg.BoolOpt('record_history',
                default=True,
                help='Record alarm change events.'
                ),
]


@six.add_metaclass(abc.ABCMeta)
class Evaluator(object):
    """Base class for alarm rule evaluator plugins."""

    def __init__(self, conf):
        self.conf = conf
        self.notifier = queue.AlarmNotifier(self.conf)
        self.storage_conn = None
        self._ks_client = None
        self._alarm_change_notifier = None

    @property
    def ks_client(self):
        if self._ks_client is None:
            self._ks_client = keystone_client.get_client(self.conf)
        return self._ks_client

    @property
    def _storage_conn(self):
        if not self.storage_conn:
            self.storage_conn = storage.get_connection_from_config(self.conf)
        return self.storage_conn

    @property
    def alarm_change_notifier(self):
        if not self._alarm_change_notifier:
            transport = messaging.get_transport(self.conf)
            self._alarm_change_notifier = messaging.get_notifier(
                transport, publisher_id="aodh.evaluator")
        return self._alarm_change_notifier

    def _record_change(self, alarm, reason):
        if not self.conf.record_history:
            return
        type = models.AlarmChange.STATE_TRANSITION
        detail = json.dumps({'state': alarm.state,
                             'transition_reason': reason})
        user_id, project_id = self.ks_client.user_id, self.ks_client.project_id
        on_behalf_of = alarm.project_id
        now = timeutils.utcnow()
        severity = alarm.severity
        payload = dict(event_id=uuidutils.generate_uuid(),
                       alarm_id=alarm.alarm_id,
                       type=type,
                       detail=detail,
                       user_id=user_id,
                       project_id=project_id,
                       on_behalf_of=on_behalf_of,
                       timestamp=now,
                       severity=severity)

        try:
            self._storage_conn.record_alarm_change(payload)
        except aodh.NotImplementedError:
            pass
        notification = "alarm.state_transition"
        self.alarm_change_notifier.info({},
                                        notification, payload)

    def _refresh(self, alarm, state, reason, reason_data, always_record=False):
        """Refresh alarm state."""
        try:
            previous = alarm.state
            alarm.state = state
            alarm.state_reason = reason
            if previous != state or always_record:
                LOG.info('alarm %(id)s transitioning to %(state)s because '
                         '%(reason)s', {'id': alarm.alarm_id,
                                        'state': state,
                                        'reason': reason})
                try:
                    self._storage_conn.update_alarm(alarm)
                except storage.AlarmNotFound:
                    LOG.warning("Skip updating this alarm's state, the"
                                "alarm: %s has been deleted",
                                alarm.alarm_id)
                else:
                    self._record_change(alarm, reason)
                self.notifier.notify(alarm, previous, reason, reason_data)
            elif alarm.repeat_actions:
                self.notifier.notify(alarm, previous, reason, reason_data)
        except Exception:
            # retry will occur naturally on the next evaluation
            # cycle (unless alarm state reverts in the meantime)
            LOG.exception('alarm state update failed')

    @classmethod
    def within_time_constraint(cls, alarm):
        """Check whether the alarm is within at least one of its time limits.

        If there are none, then the answer is yes.
        """
        if not alarm.time_constraints:
            return True

        now_utc = timeutils.utcnow().replace(tzinfo=pytz.utc)
        for tc in alarm.time_constraints:
            tz = pytz.timezone(tc['timezone']) if tc['timezone'] else None
            now_tz = now_utc.astimezone(tz) if tz else now_utc
            start_cron = croniter.croniter(tc['start'], now_tz)
            if cls._is_exact_match(start_cron, now_tz):
                return True
            # start_cron.cur has changed in _is_exact_match(),
            # croniter cannot recover properly in some corner case.
            start_cron = croniter.croniter(tc['start'], now_tz)
            latest_start = start_cron.get_prev(datetime.datetime)
            duration = datetime.timedelta(seconds=tc['duration'])
            if latest_start <= now_tz <= latest_start + duration:
                return True
        return False

    @staticmethod
    def _is_exact_match(cron, ts):
        """Handle edge in case when both parameters are equal.

        Handle edge case where if the timestamp is the same as the
        cron point in time to the minute, croniter returns the previous
        start, not the current. We can check this by first going one
        step back and then one step forward and check if we are
        at the original point in time.
        """
        cron.get_prev()
        diff = (ts - cron.get_next(datetime.datetime)).total_seconds()
        return abs(diff) < 60  # minute precision

    @abc.abstractmethod
    def evaluate(self, alarm):
        """Interface definition.

        evaluate an alarm
        alarm Alarm: an instance of the Alarm
        """


class AlarmEvaluationService(cotyledon.Service):

    PARTITIONING_GROUP_NAME = "alarm_evaluator"
    EVALUATOR_EXTENSIONS_NAMESPACE = "aodh.evaluator"

    def __init__(self, worker_id, conf):
        super(AlarmEvaluationService, self).__init__(worker_id)
        self.conf = conf

        ef = lambda: futures.ThreadPoolExecutor(max_workers=10)
        self.periodic = periodics.PeriodicWorker.create(
            [], executor_factory=ef)

        self.evaluators = extension.ExtensionManager(
            namespace=self.EVALUATOR_EXTENSIONS_NAMESPACE,
            invoke_on_load=True,
            invoke_args=(self.conf,)
        )
        self.storage_conn = storage.get_connection_from_config(self.conf)

        self.partition_coordinator = coordination.PartitionCoordinator(
            self.conf)
        self.partition_coordinator.start()
        self.partition_coordinator.join_group(self.PARTITIONING_GROUP_NAME)

        # allow time for coordination if necessary
        delay_start = self.partition_coordinator.is_active()

        if self.evaluators:
            @periodics.periodic(spacing=self.conf.evaluation_interval,
                                run_immediately=not delay_start)
            def evaluate_alarms():
                self._evaluate_assigned_alarms()

            self.periodic.add(evaluate_alarms)

        if self.partition_coordinator.is_active():
            heartbeat_interval = min(self.conf.coordination.heartbeat,
                                     self.conf.evaluation_interval / 4)

            @periodics.periodic(spacing=heartbeat_interval,
                                run_immediately=True)
            def heartbeat():
                self.partition_coordinator.heartbeat()

            self.periodic.add(heartbeat)

        t = threading.Thread(target=self.periodic.start)
        t.daemon = True
        t.start()

    def terminate(self):
        self.periodic.stop()
        self.partition_coordinator.stop()
        self.periodic.wait()

    def _evaluate_assigned_alarms(self):
        try:
            alarms = self._assigned_alarms()
            LOG.info('initiating evaluation cycle on %d alarms',
                     len(alarms))
            for alarm in alarms:
                self._evaluate_alarm(alarm)
        except Exception:
            LOG.exception('alarm evaluation cycle failed')

    def _evaluate_alarm(self, alarm):
        """Evaluate the alarms assigned to this evaluator."""
        if alarm.type not in self.evaluators:
            LOG.debug('skipping alarm %s: type unsupported', alarm.alarm_id)
            return

        LOG.debug('evaluating alarm %s', alarm.alarm_id)
        try:
            self.evaluators[alarm.type].obj.evaluate(alarm)
        except Exception:
            LOG.exception('Failed to evaluate alarm %s', alarm.alarm_id)

    def _assigned_alarms(self):
        # NOTE(r-mibu): The 'event' type alarms will be evaluated by the
        # event-driven alarm evaluator, so this periodical evaluator skips
        # those alarms.
        all_alarms = self.storage_conn.get_alarms(enabled=True,
                                                  exclude=dict(type='event'))
        all_alarms = list(all_alarms)
        all_alarm_ids = [a.alarm_id for a in all_alarms]
        selected = self.partition_coordinator.extract_my_subset(
            self.PARTITIONING_GROUP_NAME, all_alarm_ids)
        return list(filter(lambda a: a.alarm_id in selected, all_alarms))
