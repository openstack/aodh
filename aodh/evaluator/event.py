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

import copy
import fnmatch
import operator

from oslo_config import cfg
from oslo_log import log
from oslo_utils import timeutils

from aodh import evaluator
from aodh.i18n import _, _LE

LOG = log.getLogger(__name__)

COMPARATORS = {
    'gt': operator.gt,
    'lt': operator.lt,
    'ge': operator.ge,
    'le': operator.le,
    'eq': operator.eq,
    'ne': operator.ne,
}

OPTS = [
    cfg.IntOpt('event_alarm_cache_ttl',
               default=60,
               help='TTL of event alarm caches, in seconds. '
                    'Set to 0 to disable caching.'),
]


class EventAlarmEvaluator(evaluator.Evaluator):

    def __init__(self, conf, notifier):
        super(EventAlarmEvaluator, self).__init__(conf, notifier)
        self.caches = {}

    def evaluate_events(self, events):
        """Evaluate the events by referring related alarms."""

        if not isinstance(events, list):
            events = [events]

        LOG.debug('Starting event alarm evaluation: #events = %d',
                  len(events))
        for event in events:
            LOG.debug('Evaluating event: event = %s', event)

            if not self._validate(event):
                LOG.debug('Aborting evaluation of the event.')
                continue

            project = self._get_project(event)
            for alarm in self._get_project_alarms(project):
                try:
                    self._evaluate_alarm(alarm, event)
                except Exception:
                    LOG.exception(_LE('Failed to evaluate alarm (id=%(a)s) '
                                      'triggered by event = %(e)s.'),
                                  {'a': alarm.alarm_id, 'e': event})

        LOG.debug('Finished event alarm evaluation.')

    @staticmethod
    def _validate(event):
        """Validate received event has mandatory parameters."""

        if not event:
            LOG.error(_LE('Received invalid event (empty or None)'))
            return False

        if not event.get('event_type'):
            LOG.error(_LE('Failed to extract event_type from event = %s'),
                      event)
            return False

        if not event.get('message_id'):
            LOG.error(_LE('Failed to extract message_id from event = %s'),
                      event)
            return False

        return True

    @staticmethod
    def _get_project(event):
        """Extract project ID from the event."""
        for trait in event.get('traits') or []:
            if trait[0] in (u'tenant_id', u'project_id'):
                return trait[2]
        return ''

    def _get_project_alarms(self, project):
        if self.conf.event_alarm_cache_ttl and project in self.caches:
            if timeutils.is_older_than(self.caches[project]['updated'],
                                       self.conf.event_alarm_cache_ttl):
                del self.caches[project]
            else:
                return self.caches[project]['alarms']

        alarms = self._storage_conn.get_alarms(enabled=True,
                                               alarm_type='event',
                                               project=project)

        if self.conf.event_alarm_cache_ttl:
            self.caches[project] = {
                'alarms': alarms,
                'updated': timeutils.utcnow()
            }

        return alarms

    @staticmethod
    def _sanitize(event):
        """Change traits format to dict."""
        e = copy.deepcopy(event)
        e['traits'] = {t[0]: t[2] for t in event.get('traits', [])}
        return e

    def _evaluate_alarm(self, alarm, event):
        """Evaluate the alarm by referring the received event.

        This function compares each condition of the alarm on the assumption
        that all conditions are combined by AND operator.
        When the received event met conditions defined in alarm 'event_type'
        and 'query', the alarm will be fired and updated to state='alarm'
        (alarmed).
        Note: by this evaluator, the alarm won't be changed to state='ok'
        nor state='insufficient data'.
        """

        LOG.debug('Evaluating alarm (id=%(a)s) triggered by event '
                  '(message_id=%(e)s).',
                  {'a': alarm.alarm_id, 'e': event['message_id']})

        if not alarm.repeat_actions and alarm.state == evaluator.ALARM:
            LOG.debug('Skip evaluation of the alarm id=%s which have already '
                      'fired.', alarm.alarm_id)
            return

        event_pattern = alarm.rule['event_type']
        if not fnmatch.fnmatch(event['event_type'], event_pattern):
            LOG.debug('Aborting evaluation of the alarm (id=%s) due to '
                      'uninterested event_type.', alarm.alarm_id)
            return

        value = self._sanitize(event)

        def _compare(condition):
            op = COMPARATORS[condition.get('op', 'eq')]
            v = value
            for f in condition['field'].split('.'):
                if hasattr(v, 'get'):
                    v = v.get(f)
                else:
                    break
            LOG.debug('Comparing value=%(v)s against condition=%(c)s .',
                      {'v': v, 'c': condition})
            return op(v, condition['value'])

        for condition in alarm.rule['query']:
            if not _compare(condition):
                LOG.debug('Aborting evaluation of the alarm due to '
                          'unmet condition=%s .', condition)
                return

        self._fire_alarm(alarm, event)

    def _fire_alarm(self, alarm, event):
        """Update alarm state and fire alarm via alarm notifier."""

        state = evaluator.ALARM
        reason = (_('Event (message_id=%(message)s) hit the query of alarm '
                    '(id=%(alarm)s)') %
                  {'message': event['message_id'], 'alarm': alarm.alarm_id})
        reason_data = {'type': 'event', 'event': event}
        self._refresh(alarm, state, reason, reason_data)

    def _refresh(self, alarm, state, reason, reason_data):
        super(EventAlarmEvaluator, self)._refresh(alarm, state,
                                                  reason, reason_data)

        project = alarm.project_id
        if self.conf.event_alarm_cache_ttl and project in self.caches:
            for index, a in enumerate(self.caches[project]['alarms']):
                if a.alarm_id == alarm.alarm_id:
                    alarm.state = state
                    self.caches[project]['alarms'][index] = alarm
                    break

    # NOTE(r-mibu): This method won't be used, but we have to define here in
    # order to overwrite the abstract method in the super class.
    # TODO(r-mibu): Change the base (common) class design for evaluators.
    def evaluate(self, alarm):
        pass
