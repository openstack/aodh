# Copyright 2016 Hewlett Packard Enterprise Development Company, L.P.
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

from oslo_config import cfg
from oslo_middleware import cors
from oslo_policy import opts as policy_opts


def set_lib_defaults():
    """Update default value for configuration options from other namespace.

    Example, oslo lib config options. This is needed for
    config generator tool to pick these default value changes.
    https://docs.openstack.org/oslo.config/latest/cli/
    generator.html#modifying-defaults-from-other-namespaces
    """
    set_cors_middleware_defaults()

    # Update default value of oslo.policy policy_file, ,
    # enforce_scope, and enforce_new_defaults config options.
    policy_opts.set_defaults(cfg.CONF, 'policy.yaml',
                             enforce_scope=False,
                             enforce_new_defaults=False)


def set_cors_middleware_defaults():
    """Update default configuration options for oslo.middleware."""
    cors.set_defaults(
        allow_headers=['X-Auth-Token',
                       'X-Openstack-Request-Id',
                       'X-Subject-Token'],
        expose_headers=['X-Auth-Token',
                        'X-Openstack-Request-Id',
                        'X-Subject-Token'],
        allow_methods=['GET',
                       'PUT',
                       'POST',
                       'DELETE',
                       'PATCH']
    )
