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

from oslo_context import context
import pecan


def target_from_segregation_rule(req, enforcer):
    """Return a target corresponding to an alarm returned by segregation rule

    This allows to use project_id: in an oslo_policy rule for query/listing.

    :param req: Webob Request object
    :param enforcer: policy enforcer

    :returns: target
    """

    project_id = get_limited_to_project(req, enforcer)
    if project_id is not None:
        return {'project_id': project_id}
    return {}


def enforce(policy_name, req, enforcer, target):
    """Return the user and project the request should be limited to.

    :param policy_name: the policy name to validate authz against.
    :param req: Webob Request object
    :param enforcer: policy enforcer
    :param target: the alarm or "auto" to

    """
    rule_method = "telemetry:" + policy_name
    ctxt = context.RequestContext.from_environ(req.environ)

    if not enforcer.enforce(rule_method, target, ctxt.to_dict()):
        pecan.core.abort(status_code=403,
                         detail='RBAC Authorization Failed')


# TODO(fabiog): these methods are still used because the scoping part is really
# convoluted and difficult to separate out.

def get_limited_to(req, enforcer):
    """Return the user and project the request should be limited to.

    :param req: Webob Request object
    :param enforcer: policy enforcer
    :return: A tuple of (user, project), set to None if there's no limit on
    one of these.

    """
    # TODO(sileht): Only filtering on role work currently for segregation
    # oslo.policy expects the target to be the alarm. That will allow
    # creating more enhanced rbac. But for now we enforce the
    # scoping of request to the project-id, so...
    target = {}
    ctxt = context.RequestContext.from_environ(req.environ)
    # maintain backward compat with Juno and previous by using context_is_admin
    # rule if the segregation rule (added in Kilo) is not defined
    rules = enforcer.rules.keys()
    rule_name = 'segregation' if 'segregation' in rules else 'context_is_admin'
    if not enforcer.enforce(rule_name, target, ctxt.to_dict()):
        return ctxt.user_id, ctxt.project_id

    return None, None


def get_limited_to_project(req, enforcer):
    """Return the project the request should be limited to.

    :param req: Webob Request object
    :param enforcer: policy enforcer
    :return: A project, or None if there's no limit on it.

    """
    return get_limited_to(req, enforcer)[1]


def is_admin(req, enforcer):
    ctxt = context.RequestContext.from_environ(req.environ)
    return enforcer.enforce('context_is_admin', {}, ctxt.to_dict())
