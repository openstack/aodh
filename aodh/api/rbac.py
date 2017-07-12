#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2014 Hewlett-Packard Company
# Copyright 2015 Red Hat, Inc.
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

"""Access Control Lists (ACL's) control access the API server."""

import pecan


def target_from_segregation_rule(headers, enforcer):
    """Return a target that corresponds of an alarm returned by segregation rule

    This allows to use project_id: in an oslo_policy rule for query/listing.

    :param headers: HTTP headers dictionary
    :param enforcer: policy enforcer

    :returns: target
    """

    project_id = get_limited_to_project(headers, enforcer)
    if project_id is not None:
        return {'project_id': project_id}
    return {}


def enforce(policy_name, headers, enforcer, target):
    """Return the user and project the request should be limited to.

    :param policy_name: the policy name to validate authz against.
    :param headers: HTTP headers dictionary
    :param enforcer: policy enforcer
    :param target: the alarm or "auto" to

    """
    rule_method = "telemetry:" + policy_name

    credentials = {
        'roles': headers.get('X-Roles', "").split(","),
        'user_id': headers.get('X-User-Id'),
        'project_id': headers.get('X-Project-Id'),
    }

    # TODO(sileht): add deprecation warning to be able to remove this:
    # maintain backward compat with Juno and previous by allowing the action if
    # there is no rule defined for it
    rules = enforcer.rules.keys()
    if rule_method not in rules:
        return

    if not enforcer.enforce(rule_method, target, credentials):
        pecan.core.abort(status_code=403,
                         detail='RBAC Authorization Failed')


# TODO(fabiog): these methods are still used because the scoping part is really
# convoluted and difficult to separate out.

def get_limited_to(headers, enforcer):
    """Return the user and project the request should be limited to.

    :param headers: HTTP headers dictionary
    :param enforcer: policy enforcer
    :return: A tuple of (user, project), set to None if there's no limit on
    one of these.

    """
    # TODO(sileht): Only filtering on role work currently for segregation
    # oslo.policy expects the target to be the alarm. That will allow
    # creating more enhanced rbac. But for now we enforce the
    # scoping of request to the project-id, so...
    target = {}
    credentials = {
        'roles': headers.get('X-Roles', "").split(","),
    }
    # maintain backward compat with Juno and previous by using context_is_admin
    # rule if the segregation rule (added in Kilo) is not defined
    rules = enforcer.rules.keys()
    rule_name = 'segregation' if 'segregation' in rules else 'context_is_admin'
    if not enforcer.enforce(rule_name, target, credentials):
        return headers.get('X-User-Id'), headers.get('X-Project-Id')

    return None, None


def get_limited_to_project(headers, enforcer):
    """Return the project the request should be limited to.

    :param headers: HTTP headers dictionary
    :param enforcer: policy enforcer
    :return: A project, or None if there's no limit on it.

    """
    return get_limited_to(headers, enforcer)[1]
