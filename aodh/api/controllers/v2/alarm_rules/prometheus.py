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

    @staticmethod
    def validate(rule):
        # TO-DO(mmagr): validate Prometheus query maybe?
        return rule

    def as_dict(self):
        rule = self.as_dict_from_keys(['comparison_operator', 'threshold',
                                       'query'])
        return rule
