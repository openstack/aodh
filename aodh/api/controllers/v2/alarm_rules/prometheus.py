#
# Copyright 2023 Red Hat, Inc
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

from oslo_log import log
import wsme
from wsme import types as wtypes

from aodh.api.controllers.v2 import base
from aodh.api.controllers.v2 import utils as v2_utils


LOG = log.getLogger(__name__)


class PrometheusRule(base.AlarmRule):
    comparison_operator = base.AdvEnum('comparison_operator', str,
                                       'lt', 'le', 'eq', 'ne', 'ge', 'gt',
                                       default='eq')
    "The comparison against the alarm threshold"

    threshold = wsme.wsattr(float, mandatory=True)
    "The threshold of the alarm"

    query = wsme.wsattr(wtypes.text, mandatory=True)
    "The Prometheus query"

    @classmethod
    def validate_alarm(cls, alarm):
        super().validate_alarm(alarm)

        rule = alarm.prometheus_rule

        auth_project = v2_utils.get_auth_project(alarm.project_id)
        cls.scope_to_project = None
        if auth_project:
            cls.scope_to_project = auth_project
        return rule

    def as_dict(self):
        rule = self.as_dict_from_keys(['comparison_operator', 'threshold',
                                       'query', 'scope_to_project'])
        return rule
