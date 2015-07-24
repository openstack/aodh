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


def enforce(policy_name, headers, enforcer):
    """Return the user and project the request should be limited to.

    :param policy_name: the policy name to validate authz against.
    :param headers: HTTP headers dictionary
    :param enforcer: policy enforcer


    """
    rule_method = "telemetry:" + policy_name

    policy_dict = dict()
    policy_dict['roles'] = headers.get('X-Roles', "").split(",")
    policy_dict['target.user_id'] = (headers.get('X-User-Id'))
    policy_dict['target.project_id'] = (headers.get('X-Project-Id'))

    # maintain backward compat with Juno and previous by allowing the action if
    # there is no rule defined for it
    rules = enforcer.rules.keys()
    if (('default' in rules or rule_method in rules) and
            not enforcer.enforce(rule_method, {}, policy_dict)):
        pecan.core.abort(status_code=403, detail='RBAC Authorization Failed')


# TODO(fabiog): these methods are still used because the scoping part is really
# convoluted and difficult to separate out.

def get_limited_to(headers, enforcer):
    """Return the user and project the request should be limited to.

    :param headers: HTTP headers dictionary
    :param enforcer: policy enforcer
    :return: A tuple of (user, project), set to None if there's no limit on
    one of these.

    """
    policy_dict = dict()
    policy_dict['roles'] = headers.get('X-Roles', "").split(",")
    policy_dict['target.user_id'] = (headers.get('X-User-Id'))
    policy_dict['target.project_id'] = (headers.get('X-Project-Id'))

    # maintain backward compat with Juno and previous by using context_is_admin
    # rule if the segregation rule (added in Kilo) is not defined
    rules = enforcer.rules.keys()
    rule_name = 'segregation' if 'segregation' in rules else 'context_is_admin'
    if not enforcer.enforce(rule_name,
                            {},
                            policy_dict):
        return headers.get('X-User-Id'), headers.get('X-Project-Id')

    return None, None


def get_limited_to_project(headers, enforcer):
    """Return the project the request should be limited to.

    :param headers: HTTP headers dictionary
    :return: A project, or None if there's no limit on it.

    """
    return get_limited_to(headers, enforcer)[1]
