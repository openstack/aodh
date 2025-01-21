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


from oslo_config import cfg
from oslo_log import versionutils
from oslo_policy import policy

RULE_CONTEXT_IS_ADMIN = 'rule:context_is_admin'
RULE_ADMIN_OR_OWNER = 'rule:context_is_admin or project_id:%(project_id)s'
UNPROTECTED = ''

# Constants that represent common personas.
PROJECT_ADMIN = 'role:admin and project_id:%(project_id)s'
PROJECT_MEMBER = 'role:member and project_id:%(project_id)s'
PROJECT_READER = 'role:reader and project_id:%(project_id)s'

DEPRECATED_REASON = """
The alarm and quota APIs now support system-scope and default roles.
"""

deprecated_get_alarm = policy.DeprecatedRule(
    name="telemetry:get_alarm",
    check_str=RULE_ADMIN_OR_OWNER,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_get_alarms = policy.DeprecatedRule(
    name="telemetry:get_alarms",
    check_str=RULE_ADMIN_OR_OWNER,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_get_all_alarms = policy.DeprecatedRule(
    name="telemetry:get_alarms:all_projects",
    check_str=RULE_CONTEXT_IS_ADMIN,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_query_alarm = policy.DeprecatedRule(
    name="telemetry:query_alarm",
    check_str=RULE_ADMIN_OR_OWNER,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_create_alarm = policy.DeprecatedRule(
    name="telemetry:create_alarm",
    check_str=UNPROTECTED,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_change_alarm = policy.DeprecatedRule(
    name="telemetry:change_alarm",
    check_str=RULE_ADMIN_OR_OWNER,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_delete_alarm = policy.DeprecatedRule(
    name="telemetry:delete_alarm",
    check_str=RULE_ADMIN_OR_OWNER,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_get_alarm_state = policy.DeprecatedRule(
    name="telemetry:get_alarm_state",
    check_str=RULE_ADMIN_OR_OWNER,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_change_alarm_state = policy.DeprecatedRule(
    name="telemetry:change_alarm_state",
    check_str=RULE_ADMIN_OR_OWNER,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_alarm_history = policy.DeprecatedRule(
    name="telemetry:alarm_history",
    check_str=RULE_ADMIN_OR_OWNER,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_query_alarm_history = policy.DeprecatedRule(
    name="telemetry:query_alarm_history",
    check_str=RULE_ADMIN_OR_OWNER,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_get_quotas = policy.DeprecatedRule(
    name="telemetry:get_quotas",
    check_str=RULE_ADMIN_OR_OWNER,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since='Epoxy'
)
deprecated_update_quotas = policy.DeprecatedRule(
    name="telemetry:update_quotas",
    check_str=RULE_CONTEXT_IS_ADMIN,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_delete_quotas = policy.DeprecatedRule(
    name="telemetry:delete_quotas",
    check_str=RULE_CONTEXT_IS_ADMIN,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)


rules = [
    # This policy can be removed once all the policies in this file are no
    # longer deprecated and are using the new default policies with proper
    # scope support.
    policy.RuleDefault(
        name="context_is_admin",
        check_str="role:admin"
    ),
    policy.RuleDefault(
        name="segregation",
        check_str=RULE_CONTEXT_IS_ADMIN),
    # This policy can be removed once all the policies in this file are no
    # longer deprecated and are using the new default policies with proper
    # scope support.
    policy.RuleDefault(
        name="admin_or_owner",
        check_str=RULE_ADMIN_OR_OWNER
    ),
    # This policy can be removed once all the policies in this file are no
    # longer deprecated and are using the new default policies with proper
    # scope support. We shouldn't need a "default" policy if each policy has a
    # reasonable default. This concept of a broad "default" existed prior to
    # registering policies in code with their own default values.
    policy.RuleDefault(
        name="default",
        check_str=RULE_ADMIN_OR_OWNER
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:get_alarm",
        check_str=PROJECT_READER,
        scope_types=['project'],
        description='Get an alarm.',
        operations=[
            {
                'path': '/v2/alarms/{alarm_id}',
                'method': 'GET'
            }
        ],
        deprecated_rule=deprecated_get_alarm

    ),
    policy.DocumentedRuleDefault(
        name="telemetry:get_alarms",
        check_str=PROJECT_READER,
        scope_types=['project'],
        description='Get all alarms, based on the query provided.',
        operations=[
            {
                'path': '/v2/alarms',
                'method': 'GET'
            }
        ],
        deprecated_rule=deprecated_get_alarms
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:get_alarms:all_projects",
        check_str=PROJECT_ADMIN,
        scope_types=['project'],
        description='Get alarms of all projects.',
        operations=[
            {
                'path': '/v2/alarms',
                'method': 'GET'
            }
        ],
        deprecated_rule=deprecated_get_all_alarms
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:query_alarm",
        check_str=PROJECT_READER,
        scope_types=['project'],
        description='Get all alarms, based on the query provided.',
        operations=[
            {
                'path': '/v2/query/alarms',
                'method': 'POST'
            }
        ],
        deprecated_rule=deprecated_query_alarm
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:create_alarm",
        check_str=PROJECT_MEMBER,
        scope_types=['project'],
        description='Create a new alarm.',
        operations=[
            {
                'path': '/v2/alarms',
                'method': 'POST'
            }
        ],
        deprecated_rule=deprecated_create_alarm
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:change_alarm",
        check_str=PROJECT_MEMBER,
        scope_types=['project'],
        description='Modify this alarm.',
        operations=[
            {
                'path': '/v2/alarms/{alarm_id}',
                'method': 'PUT'
            }
        ],
        deprecated_rule=deprecated_change_alarm
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:delete_alarm",
        check_str=PROJECT_MEMBER,
        scope_types=['project'],
        description='Delete this alarm.',
        operations=[
            {
                'path': '/v2/alarms/{alarm_id}',
                'method': 'DELETE'
            }
        ],
        deprecated_rule=deprecated_delete_alarm
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:get_alarm_state",
        check_str=PROJECT_READER,
        scope_types=['project'],
        description='Get the state of this alarm.',
        operations=[
            {
                'path': '/v2/alarms/{alarm_id}/state',
                'method': 'GET'
            }
        ],
        deprecated_rule=deprecated_get_alarm_state
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:change_alarm_state",
        check_str=PROJECT_MEMBER,
        scope_types=['project'],
        description='Set the state of this alarm.',
        operations=[
            {
                'path': '/v2/alarms/{alarm_id}/state',
                'method': 'PUT'
            }
        ],
        deprecated_rule=deprecated_change_alarm_state
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:alarm_history",
        check_str=PROJECT_READER,
        scope_types=['project'],
        description='Assembles the alarm history requested.',
        operations=[
            {
                'path': '/v2/alarms/{alarm_id}/history',
                'method': 'GET'
            }
        ],
        deprecated_rule=deprecated_alarm_history
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:query_alarm_history",
        check_str=PROJECT_READER,
        scope_types=['project'],
        description='Define query for retrieving AlarmChange data.',
        operations=[
            {
                'path': '/v2/query/alarms/history',
                'method': 'POST'
            }
        ],
        deprecated_rule=deprecated_query_alarm_history
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:get_quotas",
        check_str=PROJECT_READER,
        scope_types=['project'],
        description='Get resources quotas for project.',
        operations=[
            {
                'path': '/v2/quotas',
                'method': 'Get'
            },
            {
                'path': '/v2/quotas/{project_id}',
                'method': 'Get'
            }
        ],
        deprecated_rule=deprecated_get_quotas
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:update_quotas",
        check_str=PROJECT_ADMIN,
        scope_types=['project'],
        description='Update resources quotas for project.',
        operations=[
            {
                'path': '/v2/quotas',
                'method': 'POST'
            }
        ],
        deprecated_rule=deprecated_update_quotas
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:delete_quotas",
        check_str=PROJECT_ADMIN,
        scope_types=['project'],
        description='Delete resources quotas for project.',
        operations=[
            {
                'path': '/v2/quotas/{project_id}',
                'method': 'DELETE'
            }
        ],
        deprecated_rule=deprecated_delete_quotas
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:get_metrics",
        check_str=PROJECT_READER,
        scope_types=['project'],
        description='Get all metrics.',
        operations=[
            {
                'path': '/v2/metrics',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name="telemetry:get_metrics:all_projects",
        check_str=PROJECT_ADMIN,
        scope_types=['project'],
        description='Get all metrics from all projects.',
        operations=[
            {
                'path': '/v2/metrics',
                'method': 'GET'
            }
        ]
    ),
]


def list_rules():
    return rules


def init(conf):
    enforcer = policy.Enforcer(conf, default_rule="default")
    # NOTE(gmann): Explictly disable the warnings for policies
    # changing their default check_str. With new RBAC policy
    # work, all the policy defaults have been changed and warning for
    # each policy started filling the logs limit for various tool.
    # Once we move to new defaults only world then we can enable these
    # warning again.
    enforcer.suppress_default_change_warnings = True
    enforcer.register_defaults(list_rules())
    return enforcer


def get_enforcer():
    # This method is used by oslopolicy CLI scripts in order to generate policy
    # files from overrides on disk and defaults in code.
    cfg.CONF([], project='aodh')
    return init(cfg.CONF)
