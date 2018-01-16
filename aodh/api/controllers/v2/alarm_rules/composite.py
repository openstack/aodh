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

from stevedore import named
from wsme.rest import json as wjson
from wsme import types as wtypes

from aodh.api.controllers.v2 import base
from aodh.i18n import _


class InvalidCompositeRule(base.ClientSideError):
    def __init__(self, error):
        err = _('Invalid input composite rule: %s, it should '
                'be a dict with an "and" or "or" as key, and the '
                'value of dict should be a list of basic threshold '
                'rules or sub composite rules, can be nested.') % error
        super(InvalidCompositeRule, self).__init__(err)


class CompositeRule(wtypes.UserType):
    """Composite alarm rule.

    A simple dict type to preset composite rule.
    """

    basetype = wtypes.text
    name = 'composite_rule'

    threshold_plugins = None

    def __init__(self):
        threshold_rules = ('gnocchi_resources_threshold',
                           'gnocchi_aggregation_by_metrics_threshold',
                           'gnocchi_aggregation_by_resources_threshold')
        CompositeRule.threshold_plugins = named.NamedExtensionManager(
            "aodh.alarm.rule", threshold_rules)
        super(CompositeRule, self).__init__()

    @staticmethod
    def valid_composite_rule(rules):
        if isinstance(rules, dict) and len(rules) == 1:
            and_or_key = list(rules)[0]
            if and_or_key not in ('and', 'or'):
                raise base.ClientSideError(
                    _('Threshold rules should be combined with "and" or "or"'))
            if isinstance(rules[and_or_key], list):
                for sub_rule in rules[and_or_key]:
                    CompositeRule.valid_composite_rule(sub_rule)
            else:
                raise InvalidCompositeRule(rules)
        elif isinstance(rules, dict):
            rule_type = rules.pop('type', None)
            if not rule_type:
                raise base.ClientSideError(_('type must be set in every rule'))

            if rule_type not in CompositeRule.threshold_plugins:
                plugins = sorted(CompositeRule.threshold_plugins.names())
                err = _('Unsupported sub-rule type :%(rule)s in composite '
                        'rule, should be one of: %(plugins)s') % {
                            'rule': rule_type,
                            'plugins': plugins}
                raise base.ClientSideError(err)
            plugin = CompositeRule.threshold_plugins[rule_type].plugin
            wjson.fromjson(plugin, rules)
            rule_dict = plugin(**rules).as_dict()
            rules.update(rule_dict)
            rules.update(type=rule_type)
        else:
            raise InvalidCompositeRule(rules)

    @staticmethod
    def validate(value):
        try:
            json.dumps(value)
        except TypeError:
            raise base.ClientSideError(_('%s is not JSON serializable')
                                       % value)
        else:
            CompositeRule.valid_composite_rule(value)
            return value

    @staticmethod
    def frombasetype(value):
        return CompositeRule.validate(value)

    @staticmethod
    def create_hook(alarm):
        pass

    @staticmethod
    def validate_alarm(alarm):
        pass

    @staticmethod
    def update_hook(alarm):
        pass

    @staticmethod
    def as_dict():
        pass

    @staticmethod
    def __call__(**rule):
        return rule

composite_rule = CompositeRule()
