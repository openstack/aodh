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
#

from oslo_log import log
import six
import stevedore

from aodh import evaluator
from aodh.evaluator import threshold
from aodh.i18n import _

LOG = log.getLogger(__name__)

STATE_CHANGE = {evaluator.ALARM: 'outside their threshold.',
                evaluator.OK: 'inside their threshold.',
                evaluator.UNKNOWN: 'state evaluated to unknown.'}


class RuleTarget(object):

    def __init__(self, rule, rule_evaluator, rule_name):
        self.rule = rule
        self.type = rule.get('type')
        self.rule_evaluator = rule_evaluator
        self.rule_name = rule_name
        self.state = None
        self.trending_state = None
        self.statistics = None
        self.evaluated = False

    def evaluate(self):
        # Evaluate a sub-rule of composite rule
        if not self.evaluated:
            LOG.debug('Evaluating %(type)s rule: %(rule)s',
                      {'type': self.type, 'rule': self.rule})
            try:
                self.state, self.trending_state, self.statistics, __, __ = \
                    self.rule_evaluator.evaluate_rule(self.rule)
            except threshold.InsufficientDataError as e:
                self.state = evaluator.UNKNOWN
                self.trending_state = None
                self.statistics = e.statistics
            self.evaluated = True


class RuleEvaluationBase(object):
    def __init__(self, rule_target):
        self.rule_target = rule_target

    def __str__(self):
        return self.rule_target.rule_name


class OkEvaluation(RuleEvaluationBase):

    def __bool__(self):
        self.rule_target.evaluate()
        return self.rule_target.state == evaluator.OK

    __nonzero__ = __bool__


class AlarmEvaluation(RuleEvaluationBase):

    def __bool__(self):
        self.rule_target.evaluate()
        return self.rule_target.state == evaluator.ALARM

    __nonzero__ = __bool__


class AndOp(object):
    def __init__(self, rule_targets):
        self.rule_targets = rule_targets

    def __bool__(self):
        return all(self.rule_targets)

    def __str__(self):
        return '(' + ' and '.join(six.moves.map(str, self.rule_targets)) + ')'

    __nonzero__ = __bool__


class OrOp(object):
    def __init__(self, rule_targets):
        self.rule_targets = rule_targets

    def __bool__(self):
        return any(self.rule_targets)

    def __str__(self):
        return '(' + ' or '.join(six.moves.map(str, self.rule_targets)) + ')'

    __nonzero__ = __bool__


class CompositeEvaluator(evaluator.Evaluator):
    def __init__(self, conf):
        super(CompositeEvaluator, self).__init__(conf)
        self.conf = conf
        self._threshold_evaluators = None
        self.rule_targets = []
        self.rule_name_prefix = 'rule'
        self.rule_num = 0

    @property
    def threshold_evaluators(self):
        if not self._threshold_evaluators:
            threshold_types = ('threshold', 'gnocchi_resources_threshold',
                               'gnocchi_aggregation_by_metrics_threshold',
                               'gnocchi_aggregation_by_resources_threshold')
            self._threshold_evaluators = stevedore.NamedExtensionManager(
                'aodh.evaluator', threshold_types, invoke_on_load=True,
                invoke_args=(self.conf,))
        return self._threshold_evaluators

    def _parse_composite_rule(self, alarm_rule):
        """Parse the composite rule.

        The composite rule is assembled by sub threshold rules with 'and',
        'or', the form can be nested. e.g. the form of composite rule can be
        like this:
        {
            "and": [threshold_rule0, threshold_rule1,
                    {'or': [threshold_rule2, threshold_rule3,
                            threshold_rule4, threshold_rule5]}]
        }
        """
        if (isinstance(alarm_rule, dict) and len(alarm_rule) == 1
                and list(alarm_rule)[0] in ('and', 'or')):
            and_or_key = list(alarm_rule)[0]
            if and_or_key == 'and':
                rules = (self._parse_composite_rule(r) for r in
                         alarm_rule['and'])
                rules_alarm, rules_ok = zip(*rules)
                return AndOp(rules_alarm), OrOp(rules_ok)
            else:
                rules = (self._parse_composite_rule(r) for r in
                         alarm_rule['or'])
                rules_alarm, rules_ok = zip(*rules)
                return OrOp(rules_alarm), AndOp(rules_ok)
        else:
            rule_evaluator = self.threshold_evaluators[alarm_rule['type']].obj
            self.rule_num += 1
            name = self.rule_name_prefix + str(self.rule_num)
            rule = RuleTarget(alarm_rule, rule_evaluator, name)
            self.rule_targets.append(rule)
            return AlarmEvaluation(rule), OkEvaluation(rule)

    def _reason(self, alarm, new_state, rule_target_alarm):
        transition = alarm.state != new_state
        reason_data = {
            'type': 'composite',
            'composition_form': str(rule_target_alarm)}
        root_cause_rules = {}
        for rule in self.rule_targets:
            if rule.state == new_state:
                root_cause_rules.update({rule.rule_name: rule.rule})
        reason_data.update(causative_rules=root_cause_rules)
        params = {'state': new_state,
                  'expression': str(rule_target_alarm),
                  'rules': ', '.join(sorted(root_cause_rules)),
                  'description': STATE_CHANGE[new_state]}
        if transition:
            reason = (_('Composite rule alarm with composition form: '
                        '%(expression)s transition to %(state)s, due to '
                        'rules: %(rules)s %(description)s') % params)

        else:
            reason = (_('Composite rule alarm with composition form: '
                        '%(expression)s remaining as %(state)s, due to '
                        'rules: %(rules)s %(description)s') % params)

        return reason, reason_data

    def _evaluate_sufficient(self, alarm, rule_target_alarm, rule_target_ok):
        # Some of evaluated rules are unknown states or trending states.
        for rule in self.rule_targets:
            if rule.trending_state is not None:
                if alarm.state == evaluator.UNKNOWN:
                    rule.state = rule.trending_state
                elif rule.trending_state == evaluator.ALARM:
                    rule.state = evaluator.OK
                elif rule.trending_state == evaluator.OK:
                    rule.state = evaluator.ALARM
                else:
                    rule.state = alarm.state

        alarm_triggered = bool(rule_target_alarm)
        if alarm_triggered:
            reason, reason_data = self._reason(alarm, evaluator.ALARM,
                                               rule_target_alarm)
            self._refresh(alarm, evaluator.ALARM, reason, reason_data)
            return True

        ok_result = bool(rule_target_ok)
        if ok_result:
            reason, reason_data = self._reason(alarm, evaluator.OK,
                                               rule_target_alarm)
            self._refresh(alarm, evaluator.OK, reason, reason_data)
            return True
        return False

    def evaluate(self, alarm):
        if not self.within_time_constraint(alarm):
            LOG.debug('Attempted to evaluate alarm %s, but it is not '
                      'within its time constraint.', alarm.alarm_id)
            return

        LOG.debug("Evaluating composite rule alarm %s ...", alarm.alarm_id)
        self.rule_targets = []
        self.rule_num = 0
        rule_target_alarm, rule_target_ok = self._parse_composite_rule(
            alarm.rule)

        sufficient = self._evaluate_sufficient(alarm, rule_target_alarm,
                                               rule_target_ok)
        if not sufficient:
            for rule in self.rule_targets:
                rule.evaluate()
            sufficient = self._evaluate_sufficient(alarm, rule_target_alarm,
                                                   rule_target_ok)

        if not sufficient:
            # The following unknown situations is like these:
            # 1. 'unknown' and 'alarm'
            # 2. 'unknown' or 'ok'
            reason, reason_data = self._reason(alarm, evaluator.UNKNOWN,
                                               rule_target_alarm)
            if alarm.state != evaluator.UNKNOWN:
                self._refresh(alarm, evaluator.UNKNOWN, reason, reason_data)
            else:
                LOG.debug(reason)
