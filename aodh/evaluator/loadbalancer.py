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

import datetime

from dateutil import parser
from octaviaclient.api.v2 import octavia
from oslo_config import cfg
from oslo_log import log
from oslo_utils import timeutils

from aodh import evaluator
from aodh.evaluator import threshold
from aodh import keystone_client as aodh_keystone

LOG = log.getLogger(__name__)

ALARM_TYPE = "loadbalancer_member_health"

OPTS = [
    cfg.IntOpt('member_creation_time',
               default=120,
               help='The time in seconds to wait for the load balancer '
                    'member creation.'
               ),
]


class LoadBalancerMemberHealthEvaluator(evaluator.Evaluator):
    def __init__(self, conf):
        super(LoadBalancerMemberHealthEvaluator, self).__init__(conf)
        self._lb_client = None

    @property
    def lb_client(self):
        if self._lb_client is None:
            endpoint = aodh_keystone.url_for(
                self.conf,
                service_type='load-balancer',
                interface=self.conf.service_credentials.interface,
                region_name=self.conf.service_credentials.region_name
            )
            self._lb_client = octavia.OctaviaAPI(
                session=aodh_keystone.get_session(self.conf),
                service_type='load-balancer',
                endpoint=endpoint
            )

        return self._lb_client

    def _get_unhealthy_members(self, pool_id):
        """Get number of unhealthy members in a pool.

        The member(virutual machine) operating_status keeps ERROR after
        creation before the application is up and running inside, it should be
        ignored during the check.
        """
        unhealthy_members = []

        try:
            ret = self.lb_client.member_list(pool_id)
        except Exception as e:
            LOG.warning("Failed to communicate with load balancing service, "
                        "error: %s", str(e))
            raise threshold.InsufficientDataError(
                'failed to communicate with load balancing service',
                []
            )

        if getattr(ret, 'status_code', None):
            # Some error happened
            raise threshold.InsufficientDataError(ret.content, [])

        for m in ret.get("members", []):
            try:
                created_time = parser.parse(m['created_at'], ignoretz=True)
            except ValueError:
                LOG.warning('Failed to parse the member created time.')
                continue

            now = timeutils.utcnow()
            t = self.conf.member_creation_time
            if now - created_time < datetime.timedelta(seconds=t):
                LOG.debug("Ignore member which was created within %ss", t)
                continue

            if m["admin_state_up"] and m["operating_status"] == "ERROR":
                unhealthy_members.append(m)

        return unhealthy_members

    def _transition_alarm(self, alarm, new_state, members,
                          count, unknown_reason, pool_id=None,
                          stack_id=None, asg_id=None):
        transition = alarm.state != new_state
        last = members[-1] if members else None

        reason_data = {
            'type': ALARM_TYPE,
            'count': count,
            'most_recent': last,
            'unhealthy_members': members,
            "pool_id": pool_id,
            "stack_id": stack_id,
            "asg_id": asg_id
        }

        if transition:
            reason = ('Transition to %(state)s due to %(count)d members'
                      ' unhealthy, most recent: %(most_recent)s' %
                      dict(state=new_state, count=count, most_recent=last))
        else:
            reason = ('Remaining as %(state)s' % dict(state=new_state))

        reason = unknown_reason or reason

        # Refresh and trigger alarm based on state transition.
        self._refresh(alarm, new_state, reason, reason_data)

    def evaluate(self, alarm):
        if not self.within_time_constraint(alarm):
            LOG.debug('Attempted to evaluate alarm %s, but it is not '
                      'within its time constraint.', alarm.alarm_id)
            return

        LOG.debug("Evaluating %s rule alarm %s ...", ALARM_TYPE,
                  alarm.alarm_id)

        pool_id = alarm.rule["pool_id"]
        error_mems = []
        try:
            error_mems = self._get_unhealthy_members(pool_id)
        except threshold.InsufficientDataError as e:
            evaluation = (evaluator.UNKNOWN, e.statistics, 0, e.reason)
        else:
            state = evaluator.ALARM if len(error_mems) > 0 else evaluator.OK
            evaluation = (state, error_mems, len(error_mems), None)

        self._transition_alarm(alarm, *evaluation, pool_id=pool_id,
                               stack_id=alarm.rule.get("stack_id"),
                               asg_id=alarm.rule.get("autoscaling_group_id"))
