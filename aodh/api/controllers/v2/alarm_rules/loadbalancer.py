# Copyright 2019 Catalyst Cloud Ltd.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import wsme
from wsme import types as wtypes

from aodh.api.controllers.v2 import base


class LoadBalancerMemberHealthRule(base.AlarmRule):
    pool_id = wsme.wsattr(wtypes.text, mandatory=True)
    "ID of a load balancer pool the members belongs to."

    stack_id = wsme.wsattr(wtypes.text, mandatory=True)
    "ID of a Heat stack which contains the load balancer member."

    autoscaling_group_id = wsme.wsattr(wtypes.text, mandatory=True)
    "ID of a Heat autoscaling group that contains the load balancer member."

    def as_dict(self):
        rule = self.as_dict_from_keys(
            ['pool_id', 'stack_id', 'autoscaling_group_id']
        )
        return rule

    @staticmethod
    def create_hook(alarm):
        pass
