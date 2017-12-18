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
import json
import operator

from oslo_config import cfg
from oslo_log import log
from oslo_utils import fnmatch
from oslo_utils import timeutils
import six

from aodh import evaluator
from aodh.i18n import _

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


def _sanitize_trait_value(value, trait_type):
    if trait_type in (2, 'integer'):
        return int(value)
    elif trait_type in (3, 'float'):
        return float(value)
    elif trait_type in (4, 'datetime'):
        return timeutils.normalize_time(timeutils.parse_isotime(value))
    else:
        return six.text_type(value)


class InvalidEvent(Exception):
    """Error raised when the received event is missing mandatory fields."""


class Event(object):
    """Wrapped event object to hold converted values for this evaluator."""

    TRAIT_FIELD = 0
    TRAIT_TYPE = 1
    TRAIT_VALUE = 2

    def __init__(self, event):
        self.obj = event
        self._validate()
        self.id = event.get('message_id')
        self._parse_traits()

    def _validate(self):
        """Validate received event has mandatory parameters."""

        if not self.obj:
            LOG.error('Received invalid event (empty or None)')
            raise InvalidEvent()

        if not self.obj.get('event_type'):
            LOG.error('Failed to extract event_type from event = %s',
                      self.obj)
            raise InvalidEvent()

        if not self.obj.get('message_id'):
            LOG.error('Failed to extract message_id from event = %s',
                      self.obj)
            raise InvalidEvent()

    def _parse_traits(self):
        self.traits = {}
        self.project = ''
        for t in self.obj.get('traits', []):
            k = t[self.TRAIT_FIELD]
            v = _sanitize_trait_value(t[self.TRAIT_VALUE], t[self.TRAIT_TYPE])
            self.traits[k] = v
            if k in ('tenant_id', 'project_id'):
                self.project = v

    def get_value(self, field):
        if field.startswith('traits.'):
            key = field.split('.', 1)[-1]
            return self.traits.get(key)

        v = self.obj
        for f in field.split('.'):
            if hasattr(v, 'get'):
                v = v.get(f)
            else:
                return None
        return v


class Alarm(object):
    """Wrapped alarm object to hold converted values for this evaluator."""

    TRAIT_TYPES = {
        'none': 0,
        'string': 1,
        'integer': 2,
        'float': 3,
        'datetime': 4,
    }

    def __init__(self, alarm):
        self.obj = alarm
        self.id = alarm.alarm_id
        self._parse_query()

    def _parse_query(self):
        self.query = []
        for q in self.obj.rule.get('query', []):
            if not q['field'].startswith('traits.'):
                self.query.append(q)
                continue
            type_num = self.TRAIT_TYPES[q.get('type') or 'string']
            field = q['field']
            value = _sanitize_trait_value(q.get('value'), type_num)
            op = COMPARATORS[q.get('op', 'eq')]
            self.query.append({'field': field, 'value': value, 'op': op})

    def fired_and_no_repeat(self):
        return (not self.obj.repeat_actions and
                self.obj.state == evaluator.ALARM)

    def event_type_to_watch(self, event_type):
        return fnmatch.fnmatch(event_type, self.obj.rule['event_type'])


class EventAlarmEvaluator(evaluator.Evaluator):

    def __init__(self, conf):
        super(EventAlarmEvaluator, self).__init__(conf)
        self.caches = {}

    def evaluate_events(self, events):
        """Evaluate the events by referring related alarms."""

        if not isinstance(events, list):
            events = [events]

        LOG.debug('Starting event alarm evaluation: #events = %d',
                  len(events))
        for e in events:
            LOG.debug('Evaluating event: event = %s', e)
            try:
                event = Event(e)
            except InvalidEvent:
                LOG.warning('Event <%s> is invalid, aborting evaluation '
                            'for it.', e)
                continue

            for id, alarm in six.iteritems(
                    self._get_project_alarms(event.project)):
                try:
                    self._evaluate_alarm(alarm, event)
                except Exception:
                    LOG.exception('Failed to evaluate alarm (id=%(a)s) '
                                  'triggered by event = %(e)s.',
                                  {'a': id, 'e': e})

        LOG.debug('Finished event alarm evaluation.')

    def _get_project_alarms(self, project):
        if self.conf.event_alarm_cache_ttl and project in self.caches:
            if timeutils.is_older_than(self.caches[project]['updated'],
                                       self.conf.event_alarm_cache_ttl):
                del self.caches[project]
            else:
                return self.caches[project]['alarms']

        # TODO(r-mibu): Implement "changes-since" at the storage API and make
        # this function update only alarms changed from the last access.
        alarms = {a.alarm_id: Alarm(a) for a in
                  self._storage_conn.get_alarms(enabled=True,
                                                alarm_type='event',
                                                project=project)}

        if self.conf.event_alarm_cache_ttl:
            self.caches[project] = {
                'alarms': alarms,
                'updated': timeutils.utcnow()
            }

        return alarms

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
                  '(message_id=%(e)s).', {'a': alarm.id, 'e': event.id})

        if alarm.fired_and_no_repeat():
            LOG.debug('Skip evaluation of the alarm id=%s which have already '
                      'fired.', alarm.id)
            return

        if not alarm.event_type_to_watch(event.obj['event_type']):
            LOG.debug('Aborting evaluation of the alarm (id=%s) since '
                      'event_type is not matched.', alarm.id)
            return

        def _compare(condition):
            v = event.get_value(condition['field'])
            LOG.debug('Comparing value=%(v)s against condition=%(c)s .',
                      {'v': v, 'c': condition})
            return condition['op'](v, condition['value'])

        for condition in alarm.query:
            if not _compare(condition):
                LOG.debug('Aborting evaluation of the alarm due to '
                          'unmet condition=%s .', condition)
                return

        self._fire_alarm(alarm, event)

    def _fire_alarm(self, alarm, event):
        """Update alarm state and fire alarm via alarm notifier."""

        state = evaluator.ALARM
        reason = (_('Event <id=%(id)s,event_type=%(event_type)s> hits the '
                    'query <query=%(alarm_query)s>.') %
                  {'id': event.id,
                   'event_type': event.get_value('event_type'),
                   'alarm_query': json.dumps(alarm.obj.rule['query'],
                                             sort_keys=True)})
        reason_data = {'type': 'event', 'event': event.obj}
        always_record = alarm.obj.repeat_actions
        self._refresh(alarm.obj, state, reason, reason_data, always_record)

    def _refresh(self, alarm, state, reason, reason_data, always_record):
        super(EventAlarmEvaluator, self)._refresh(alarm, state,
                                                  reason, reason_data,
                                                  always_record)

        project = alarm.project_id
        if self.conf.event_alarm_cache_ttl and project in self.caches:
            self.caches[project]['alarms'][alarm.alarm_id].obj.state = state

    # NOTE(r-mibu): This method won't be used, but we have to define here in
    # order to overwrite the abstract method in the super class.
    # TODO(r-mibu): Change the base (common) class design for evaluators.
    def evaluate(self, alarm):
        pass
