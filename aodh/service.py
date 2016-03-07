#!/usr/bin/env python
#
# Copyright 2013 Red Hat, Inc
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
import socket

from oslo_config import cfg
from oslo_db import options as db_options
import oslo_i18n
from oslo_log import log
from oslo_policy import opts as policy_opts

from aodh.conf import defaults
from aodh import keystone_client
from aodh import messaging


OPTS = [
    cfg.StrOpt('host',
               default=socket.gethostname(),
               help='Name of this node, which must be valid in an AMQP '
               'key. Can be an opaque identifier. For ZeroMQ only, must '
               'be a valid host name, FQDN, or IP address.'),
    cfg.IntOpt('http_timeout',
               default=600,
               help='Timeout seconds for HTTP requests. Set it to None to '
                    'disable timeout.'),
    cfg.IntOpt('evaluation_interval',
               default=60,
               help='Period of evaluation cycle, should'
               ' be >= than configured pipeline interval for'
               ' collection of underlying meters.',
               deprecated_group='alarm',
               deprecated_opts=[cfg.DeprecatedOpt(
                   'threshold_evaluation_interval', group='alarm')]),
]


def prepare_service(argv=None, config_files=None):
    conf = cfg.ConfigOpts()
    oslo_i18n.enable_lazy()
    log.register_options(conf)
    log_levels = (conf.default_log_levels +
                  ['stevedore=INFO', 'keystoneclient=INFO'])
    log.set_defaults(default_log_levels=log_levels)
    defaults.set_cors_middleware_defaults()
    db_options.set_defaults(conf)
    policy_opts.set_defaults(conf)
    from aodh import opts
    # Register our own Aodh options
    for group, options in opts.list_opts():
        conf.register_opts(list(options),
                           group=None if group == "DEFAULT" else group)
    keystone_client.register_keystoneauth_opts(conf)

    conf(argv, project='aodh', validate_default_values=True,
         default_config_files=config_files)

    keystone_client.setup_keystoneauth(conf)
    log.setup(conf, 'aodh')
    messaging.setup()
    return conf
