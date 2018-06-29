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

import voluptuous
import wsme
from wsme import types as wtypes

from aodh.api.controllers.v2 import base
from aodh.i18n import _


# Schema validation for the event type query.
_q_validator = voluptuous.Schema(
    {"field": voluptuous.Match(r"^[a-zA-Z.',0-9_-]*$"),
     "op": voluptuous.In(base.operation_kind),
     "value": voluptuous.In(["string", "integer", "float", "boolean", ""])})


class AlarmEventRule(base.AlarmRule):
    """Alarm Event Rule.

    Describe when to trigger the alarm based on an event
    """

    event_type = wsme.wsattr(wtypes.text)
    "The type of event (default is '*')"

    query = wsme.wsattr([base.Query])
    "The query to find the event (default is [])"

    def __init__(self, event_type=None, query=None):
        event_type = event_type or '*'
        query = [base.Query(**q) for q in query or []]
        super(AlarmEventRule, self).__init__(event_type=event_type,
                                             query=query)

    @classmethod
    def validate_alarm(cls, alarm):
        super(AlarmEventRule, cls).validate_alarm(alarm)
        for i in alarm.event_rule.query:
            i._get_value_as_type()
            try:
                _q_validator({"field": i.field, "op": i.op,
                              "value": i.type})
            except voluptuous.MultipleInvalid as e:
                raise base.ClientSideError(
                    _("Query value or traits invalid: %s") % str(e))

    @property
    def default_description(self):
        return _('Alarm when %s event occurred.') % self.event_type

    def as_dict(self):
        rule = self.as_dict_from_keys(['event_type'])
        rule['query'] = [q.as_dict() for q in self.query]
        return rule

    @classmethod
    def sample(cls):
        return cls(event_type='compute.instance.update',
                   query=[{'field': 'traits.instance_id"',
                           'value': '153462d0-a9b8-4b5b-8175-9e4b05e9b856',
                           'op': 'eq',
                           'type': 'string'}])
