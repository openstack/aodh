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

from oslo_log import log

from aodh import keystone_client as aodh_keystone
from aodh import notifier

LOG = log.getLogger(__name__)


class TrustHeatAlarmNotifier(notifier.AlarmNotifier):
    """Heat autohealing notifier.

    The auto-healing notifier works together with loadbalancer_member_health
    evaluator.

    Presumably, the end user defines a Heat template which contains an
    autoscaling group and all the members in the group are joined in an Octavia
    load balancer in order to expose service to the outside, so that when the
    stack scales up or scales down, Heat makes sure the new members are joining
    the load balancer automatically and the old members are removed.

    However, this notifier deals with the situation that when some member
    fails, the stack could be recovered by marking the given autoscaling group
    member unhealthy, then update Heat stack in place. In order to do that, the
    notifier needs to know:

    - Heat top/root stack ID.
    - Heat autoscaling group ID.
    - The failed Octavia pool members.
    """

    def __init__(self, conf):
        super(TrustHeatAlarmNotifier, self).__init__(conf)
        self.conf = conf

    def notify(self, action, alarm_id, alarm_name, severity, previous, current,
               reason, reason_data):
        LOG.info(
            "Notifying alarm %(alarm_name)s %(alarm_id)s of %(severity)s "
            "priority from %(previous)s to %(current)s with action %(action)s"
            " because %(reason)s." %
            {'alarm_name': alarm_name,
             'alarm_id': alarm_id,
             'severity': severity,
             'previous': previous,
             'current': current,
             'action': action.geturl(),
             'reason': reason}
        )

        trust_id = action.username
        stack_id = reason_data.get("stack_id")
        asg_id = reason_data.get("asg_id")
        unhealthy_members = reason_data.get("unhealthy_members", [])
        unhealthy_resources = []

        if not stack_id or not asg_id:
            LOG.error(
                "stack_id and asg_id must exist to notify alarm %s", alarm_id
            )
            return

        heat_client = aodh_keystone.get_heat_client_from_trust(
            self.conf, trust_id
        )

        for member in unhealthy_members:
            target_resources = heat_client.resources.list(
                stack_id, nested_depth=3,
                filters={"physical_resource_id": member["id"]}
            )
            if len(target_resources) > 0:
                # There should be only one item.
                unhealthy_resources.append(
                    target_resources[0].parent_resource
                )

        if not unhealthy_resources:
            LOG.warning("No unhealthy resource found for the alarm %s",
                        alarm_id)
            return

        try:
            for res in unhealthy_resources:
                heat_client.resources.mark_unhealthy(
                    asg_id,
                    res,
                    True,
                    "unhealthy load balancer member"
                )
                LOG.info(
                    "Heat resource %(resource_id)s is marked as unhealthy "
                    "for alarm %(alarm_id)s",
                    {"resource_id": res, "alarm_id": alarm_id}
                )

            heat_client.stacks.update(stack_id, existing=True)
            LOG.info(
                "Heat stack %(stack_id)s is updated for alarm "
                "%(alarm_id)s",
                {"stack_id": stack_id, "alarm_id": alarm_id}
            )
        except Exception as e:
            LOG.exception("Failed to communicate with Heat service for alarm "
                          "%s, error: %s",
                          alarm_id, str(e))
