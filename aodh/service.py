#!/usr/bin/env python
#
# Copyright 2013-2017 Red Hat, Inc
# Copyright 2012-2015 eNovance <licensing@enovance.com>
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
import os

from keystoneauth1 import loading as ka_loading
from oslo_config import cfg
from oslo_db import options as db_options
import oslo_i18n
from oslo_log import log
from oslo_policy import opts as policy_opts
from oslo_reports import guru_meditation_report as gmr
from oslo_utils import importutils

from aodh.conf import defaults
from aodh import keystone_client
from aodh import messaging
from aodh import profiler
from aodh import version

profiler_opts = importutils.try_import('osprofiler.opts')

OPTS = [
    cfg.IntOpt('http_timeout',
               default=600,
               deprecated_for_removal=True,
               deprecated_reason=('This parameter is not used now and has no '
                                  'effect.'),
               help='Timeout seconds for HTTP requests. Set it to None to '
                    'disable timeout.'),
]

EVALUATOR_OPTS = [
    cfg.IntOpt('workers',
               default=1,
               min=1,
               help='Number of workers for evaluator service. '
               'default value is 1.'),
    cfg.IntOpt('evaluation_interval',
               default=60,
               deprecated_group='DEFAULT',
               help='Period of evaluation cycle, should'
               ' be >= than configured pipeline interval for'
               ' collection of underlying meters.'),
]

NOTIFIER_OPTS = [
    cfg.IntOpt('workers',
               default=1,
               min=1,
               help='Number of workers for notifier service. '
               'default value is 1.')
]

LISTENER_OPTS = [
    cfg.IntOpt('workers',
               default=1,
               min=1,
               help='Number of workers for listener service. '
                    'default value is 1.')
]


def prepare_service(argv=None, config_files=None):
    conf = cfg.ConfigOpts()
    oslo_i18n.enable_lazy()
    log.register_options(conf)
    log_levels = (
        conf.default_log_levels +
        [
            'futurist=INFO',
            'keystoneclient=INFO',
            'oslo_db.sqlalchemy=WARN',
            'cotyledon=INFO'
        ]
    )
    log.set_defaults(default_log_levels=log_levels)
    defaults.set_cors_middleware_defaults()
    db_options.set_defaults(conf)
    if profiler_opts:
        profiler_opts.set_defaults(conf)
    policy_opts.set_defaults(conf, policy_file=os.path.abspath(
        os.path.join(os.path.dirname(__file__), "api", "policy.yaml")))
    from aodh import opts
    # Register our own Aodh options
    for group, options in opts.list_opts():
        conf.register_opts(list(options),
                           group=None if group == "DEFAULT" else group)
    keystone_client.register_keystoneauth_opts(conf)

    conf(argv, project='aodh', validate_default_values=True,
         default_config_files=config_files,
         version=version.version_info.version_string())

    ka_loading.load_auth_from_conf_options(conf, "service_credentials")
    log.setup(conf, 'aodh')

    # NOTE(tkajinam): guru cannot run with service under apache daemon, so when
    # aod-api running with mod_wsgi, the argv is [], we don't start guru.
    if argv:
        gmr.TextGuruMeditation.setup_autorun(version)

    profiler.setup(conf)
    messaging.setup()
    return conf
