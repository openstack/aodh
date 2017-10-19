# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


from oslo_policy import policy

RULE_CONTEXT_IS_ADMIN = 'rule:context_is_admin'
RULE_ADMIN_OR_OWNER = 'rule:context_is_admin or project_id:%(project_id)s'
UNPROTECTED = ''

rules = [
    policy.RuleDefault(
        name="context_is_admin",
        check_str="role:admin"
    ),
    policy.RuleDefault(
        name="segregation",
        check_str=RULE_CONTEXT_IS_ADMIN),
    policy.RuleDefault(
        name="admin_or_owner",
        check_str=RULE_ADMIN_OR_OWNER
    ),
    policy.RuleDefault(
        name="default",
        check_str=RULE_ADMIN_OR_OWNER
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:get_alarm",
        check_str=RULE_ADMIN_OR_OWNER,
        description='Get an alarm.',
        operations=[
            {
                'path': '/v2/alarms/{alarm_id}',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:get_alarms",
        check_str=RULE_ADMIN_OR_OWNER,
        description='Get all alarms, based on the query provided.',
        operations=[
            {
                'path': '/v2/alarms',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:query_alarm",
        check_str=RULE_ADMIN_OR_OWNER,
        description='Get all alarms, based on the query provided.',
        operations=[
            {
                'path': '/v2/query/alarms',
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:create_alarm",
        check_str=UNPROTECTED,
        description='Create a new alarm.',
        operations=[
            {
                'path': '/v2/alarms',
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:change_alarm",
        check_str=RULE_ADMIN_OR_OWNER,
        description='Modify this alarm.',
        operations=[
            {
                'path': '/v2/alarms/{alarm_id}',
                'method': 'PUT'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:delete_alarm",
        check_str=RULE_ADMIN_OR_OWNER,
        description='Delete this alarm.',
        operations=[
            {
                'path': '/v2/alarms/{alarm_id}',
                'method': 'DELETE'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:get_alarm_state",
        check_str=RULE_ADMIN_OR_OWNER,
        description='Get the state of this alarm.',
        operations=[
            {
                'path': '/v2/alarms/{alarm_id}/state',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:change_alarm_state",
        check_str=RULE_ADMIN_OR_OWNER,
        description='Set the state of this alarm.',
        operations=[
            {
                'path': '/v2/alarms/{alarm_id}/state',
                'method': 'PUT'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:alarm_history",
        check_str=RULE_ADMIN_OR_OWNER,
        description='Assembles the alarm history requested.',
        operations=[
            {
                'path': '/v2/alarms/{alarm_id}/history',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:query_alarm_history",
        check_str=RULE_ADMIN_OR_OWNER,
        description='Define query for retrieving AlarmChange data.',
        operations=[
            {
                'path': '/v2/query/alarms/history',
                'method': 'POST'
            }
        ]
    )
]


def list_rules():
    return rules
