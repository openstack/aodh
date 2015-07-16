#
# Copyright 2013 eNovance <licensing@enovance.com>
#
# Authors: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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

import croniter
from oslo_config import cfg
from oslo_context import context
from oslo_log import log
from oslo_utils import timeutils
import pytz
import six
import uuid

import aodh
from aodh.i18n import _
from aodh import messaging
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

cfg.CONF.register_opts(OPTS, group="alarm")


@six.add_metaclass(abc.ABCMeta)
class Evaluator(object):
    """Base class for alarm rule evaluator plugins."""

    def __init__(self, notifier):
        self.notifier = notifier
        self.storage_conn = None

    @property
    def _storage_conn(self):
        if not self.storage_conn:
            self.storage_conn = storage.get_connection_from_config(cfg.CONF)
        return self.storage_conn

    def _record_change(self, alarm):
        if not cfg.CONF.alarm.record_history:
            return
        type = models.AlarmChange.STATE_TRANSITION
        detail = json.dumps({'state': alarm.state})
        # TODO(liusheng) the user_id and project_id should be
        # specify than None?
        user_id = None
        project_id = None
        on_behalf_of = alarm.project_id
        now = timeutils.utcnow()
        payload = dict(event_id=str(uuid.uuid4()),
                       alarm_id=alarm.alarm_id,
                       type=type,
                       detail=detail,
                       user_id=user_id,
                       project_id=project_id,
                       on_behalf_of=on_behalf_of,
                       timestamp=now)

        try:
            self._storage_conn.record_alarm_change(payload)
        except aodh.NotImplementedError:
            pass
        notification = "alarm.state_transition"
        transport = messaging.get_transport()
        notifier = messaging.get_notifier(transport,
                                          publisher_id="aodh.alarm.evaluator")
        notifier.info(context.RequestContext(), notification, payload)

    def _refresh(self, alarm, state, reason, reason_data):
        """Refresh alarm state."""
        try:
            previous = alarm.state
            alarm.state = state
            if previous != state:
                LOG.info(_('alarm %(id)s transitioning to %(state)s because '
                           '%(reason)s') % {'id': alarm.alarm_id,
                                            'state': state,
                                            'reason': reason})

                self._storage_conn.update_alarm(alarm)
                self._record_change(alarm)
            if self.notifier:
                self.notifier.notify(alarm, previous, reason, reason_data)
        except Exception:
            # retry will occur naturally on the next evaluation
            # cycle (unless alarm state reverts in the meantime)
            LOG.exception(_('alarm state update failed'))

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
        diff = timeutils.total_seconds(ts - cron.get_next(datetime.datetime))
        return abs(diff) < 60  # minute precision

    @abc.abstractmethod
    def evaluate(self, alarm):
        """Interface definition.

        evaluate an alarm
        alarm Alarm: an instance of the Alarm
        """
