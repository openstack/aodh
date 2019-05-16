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
from oslo_utils import uuidutils
import six

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

    - Heat stack ID.
    - Heat autoscaling group ID.
    - The failed Octavia pool members.

    The resource ID in the autoscaling group is saved in the Octavia member
    tags. So, only Octavia stable/stein or later versions are supported.
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

        if not stack_id or not asg_id:
            LOG.warning(
                "stack_id and asg_id must exist to notify alarm %s", alarm_id
            )
            return

        resources = []
        unhealthy_members = reason_data.get("unhealthy_members", [])

        for member in unhealthy_members:
            for tag in member.get("tags", []):
                if uuidutils.is_uuid_like(tag):
                    resources.append(tag)

        if resources:
            try:
                heat_client = aodh_keystone.get_heat_client_from_trust(
                    self.conf, trust_id
                )

                for res in resources:
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
                LOG.exception("Failed to communicate with Heat service, "
                              "error: %s", six.text_type(e))
