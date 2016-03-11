#
# Copyright 2013-2015 Red Hat, Inc
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
import datetime
import operator
import six

from ceilometerclient import client as ceiloclient
from oslo_log import log
from oslo_utils import timeutils

from aodh import evaluator
from aodh.evaluator import utils
from aodh.i18n import _, _LW
from aodh import keystone_client

LOG = log.getLogger(__name__)

COMPARATORS = {
    'gt': operator.gt,
    'lt': operator.lt,
    'ge': operator.ge,
    'le': operator.le,
    'eq': operator.eq,
    'ne': operator.ne,
}


class ThresholdEvaluator(evaluator.Evaluator):

    # the sliding evaluation window is extended to allow
    # for reporting/ingestion lag
    look_back = 1

    def __init__(self, conf):
        super(ThresholdEvaluator, self).__init__(conf)
        self._cm_client = None

    @property
    def cm_client(self):
        if self._cm_client is None:
            auth_config = self.conf.service_credentials
            self._cm_client = ceiloclient.get_client(
                version=2,
                session=keystone_client.get_session(self.conf),
                # ceiloclient adapter options
                region_name=auth_config.region_name,
                interface=auth_config.interface,
            )

        return self._cm_client

    @classmethod
    def _bound_duration(cls, rule):
        """Bound the duration of the statistics query."""
        now = timeutils.utcnow()
        # when exclusion of weak datapoints is enabled, we extend
        # the look-back period so as to allow a clearer sample count
        # trend to be established
        look_back = (cls.look_back if not rule.get('exclude_outliers')
                     else rule['evaluation_periods'])
        window = ((rule.get('period', None) or rule['granularity'])
                  * (rule['evaluation_periods'] + look_back))
        start = now - datetime.timedelta(seconds=window)
        LOG.debug('query stats from %(start)s to '
                  '%(now)s', {'start': start, 'now': now})
        return start.isoformat(), now.isoformat()

    @staticmethod
    def _sanitize(rule, statistics):
        """Sanitize statistics."""
        LOG.debug('sanitize stats %s', statistics)
        if rule.get('exclude_outliers'):
            key = operator.attrgetter('count')
            mean = utils.mean(statistics, key)
            stddev = utils.stddev(statistics, key, mean)
            lower = mean - 2 * stddev
            upper = mean + 2 * stddev
            inliers, outliers = utils.anomalies(statistics, key, lower, upper)
            if outliers:
                LOG.debug('excluded weak datapoints with sample counts %s',
                          [s.count for s in outliers])
                statistics = inliers
            else:
                LOG.debug('no excluded weak datapoints')

        # in practice statistics are always sorted by period start, not
        # strictly required by the API though
        statistics = statistics[-rule['evaluation_periods']:]
        result_statistics = [getattr(stat, rule['statistic'])
                             for stat in statistics]
        LOG.debug('pruned statistics to %d', len(statistics))
        return result_statistics

    def _statistics(self, rule, start, end):
        """Retrieve statistics over the current window."""
        after = dict(field='timestamp', op='ge', value=start)
        before = dict(field='timestamp', op='le', value=end)
        query = copy.copy(rule['query'])
        query.extend([before, after])
        LOG.debug('stats query %s', query)
        try:
            return self.cm_client.statistics.list(
                meter_name=rule['meter_name'], q=query,
                period=rule['period'])
        except Exception:
            LOG.exception(_('alarm stats retrieval failed'))
            return []

    @staticmethod
    def _reason_data(disposition, count, most_recent):
        """Create a reason data dictionary for this evaluator type."""
        return {'type': 'threshold', 'disposition': disposition,
                'count': count, 'most_recent': most_recent}

    @classmethod
    def _reason(cls, alarm, statistics, state, count):
        """Fabricate reason string."""
        if state == evaluator.OK:
            disposition = 'inside'
            count = len(statistics) - count
        else:
            disposition = 'outside'
        last = statistics[-1] if statistics else None
        transition = alarm.state != state
        reason_data = cls._reason_data(disposition, count, last)
        if transition:
            return (_('Transition to %(state)s due to %(count)d samples'
                      ' %(disposition)s threshold, most recent:'
                      ' %(most_recent)s')
                    % dict(reason_data, state=state)), reason_data
        return (_('Remaining as %(state)s due to %(count)d samples'
                  ' %(disposition)s threshold, most recent: %(most_recent)s')
                % dict(reason_data, state=state)), reason_data

    def evaluate_rule(self, alarm_rule):
        """Evaluate alarm rule.

        :returns: state, trending state and statistics.
        """
        start, end = self._bound_duration(alarm_rule)
        statistics = self._statistics(alarm_rule, start, end)
        statistics = self._sanitize(alarm_rule, statistics)
        sufficient = len(statistics) >= alarm_rule['evaluation_periods']
        if not sufficient:
            return evaluator.UNKNOWN, None, statistics, len(statistics)

        def _compare(value):
            op = COMPARATORS[alarm_rule['comparison_operator']]
            limit = alarm_rule['threshold']
            LOG.debug('comparing value %(value)s against threshold'
                      ' %(limit)s', {'value': value, 'limit': limit})
            return op(value, limit)

        compared = list(six.moves.map(_compare, statistics))
        distilled = all(compared)
        unequivocal = distilled or not any(compared)
        number_outside = len([c for c in compared if c])

        if unequivocal:
            state = evaluator.ALARM if distilled else evaluator.OK
            return state, None, statistics, number_outside
        else:
            trending_state = evaluator.ALARM if compared[-1] else evaluator.OK
            return None, trending_state, statistics, number_outside

    def _transition_alarm(self, alarm, state, trending_state, statistics,
                          outside_count):
        unknown = alarm.state == evaluator.UNKNOWN
        continuous = alarm.repeat_actions

        if trending_state:
            if unknown or continuous:
                state = trending_state if unknown else alarm.state
                reason, reason_data = self._reason(alarm, statistics, state,
                                                   outside_count)
                self._refresh(alarm, state, reason, reason_data)
                return

        if state == evaluator.UNKNOWN and not unknown:
            LOG.warning(_LW('Expecting %(expected)d datapoints but only get '
                            '%(actual)d') % {
                'expected': alarm.rule['evaluation_periods'],
                'actual': len(statistics)})
            # Reason is not same as log message because we want to keep
            # consistent since thirdparty software may depend on old format.
            reason = _('%d datapoints are unknown') % alarm.rule[
                'evaluation_periods']
            last = None if not statistics else statistics[-1]
            reason_data = self._reason_data('unknown',
                                            alarm.rule['evaluation_periods'],
                                            last)
            self._refresh(alarm, state, reason, reason_data)

        elif state and (alarm.state != state or continuous):
            reason, reason_data = self._reason(alarm, statistics, state,
                                               outside_count)
            self._refresh(alarm, state, reason, reason_data)

    def evaluate(self, alarm):
        if not self.within_time_constraint(alarm):
            LOG.debug('Attempted to evaluate alarm %s, but it is not '
                      'within its time constraint.', alarm.alarm_id)
            return

        state, trending_state, statistics, outside_count = self.evaluate_rule(
            alarm.rule)
        self._transition_alarm(alarm, state, trending_state, statistics,
                               outside_count)
