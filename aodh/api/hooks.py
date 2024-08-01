#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
from oslo_policy import opts
from pecan import hooks

from aodh.api import policies

# TODO(gmann): Remove overriding the default value of config options:
# - 'policy_file' once oslo_policy change their default value to what is
# overridden here.
# - 'enforce_scope', and 'enforce_new_defaults' once aodh is ready with the
# new RBAC (oslo_policy enable them by default)
DEFAULT_POLICY_FILE = 'policy.yaml'
opts.set_defaults(
    cfg.CONF,
    DEFAULT_POLICY_FILE,
    enforce_scope=False,
    enforce_new_defaults=False)


class ConfigHook(hooks.PecanHook):
    """Attach the configuration and policy enforcer object to the request.

    That allows controllers to get it.
    """

    def __init__(self, conf):
        self.conf = conf
        self.enforcer = policies.init(conf)

    def before(self, state):
        state.request.cfg = self.conf
        state.request.enforcer = self.enforcer


class DBHook(hooks.PecanHook):

    def __init__(self, alarm_conn):
        self.storage = alarm_conn

    def before(self, state):
        state.request.storage = self.storage


class TranslationHook(hooks.PecanHook):

    def after(self, state):
        # After a request has been done, we need to see if
        # ClientSideError has added an error onto the response.
        # If it has we need to get it info the thread-safe WSGI
        # environ to be used by the ParsableErrorMiddleware.
        if hasattr(state.response, 'translatable_error'):
            state.request.environ['translatable_error'] = (
                state.response.translatable_error)
