# Copyright 2014-2015 eNovance
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
import itertools

from keystoneauth1 import loading
from oslo_config import cfg

import aodh.api
import aodh.api.controllers.v2.alarms
import aodh.coordination
import aodh.evaluator
import aodh.evaluator.event
import aodh.evaluator.gnocchi
import aodh.event
import aodh.keystone_client
import aodh.notifier.rest
import aodh.rpc
import aodh.service
import aodh.storage


def list_opts():
    return [
        ('DEFAULT',
         itertools.chain(
             aodh.evaluator.OPTS,
             aodh.evaluator.event.OPTS,
             aodh.evaluator.gnocchi.OPTS,
             aodh.event.OPTS,
             aodh.notifier.OPTS,
             aodh.notifier.rest.OPTS,
             aodh.queue.OPTS,
             aodh.rpc.OPTS,
             aodh.service.OPTS,
             aodh.api.controllers.v2.alarms.ALARM_API_OPTS)),
        ('api',
         itertools.chain(
             aodh.api.OPTS,
             [
                 cfg.StrOpt(
                     'paste_config',
                     deprecated_name='api_paste_config',
                     deprecated_group='DEFAULT',
                     default="api_paste.ini",
                     help="Configuration file for WSGI definition of API."),
                 cfg.IntOpt(
                     'workers', default=1,
                     deprecated_name='api_workers',
                     deprecated_group='DEFAULT',
                     min=1,
                     help='Number of workers for aodh API server.'),
                 cfg.BoolOpt('pecan_debug',
                             default=False,
                             help='Toggle Pecan Debug Middleware.'),
             ])),
        ('coordination', aodh.coordination.OPTS),
        ('database', aodh.storage.OPTS),
        ('service_credentials', aodh.keystone_client.OPTS),
    ]


def list_keystoneauth_opts():
    # NOTE(sileht): the configuration file contains only the options
    # for the password plugin that handles keystone v2 and v3 API
    # with discovery. But other options are possible.
    # Also, the default loaded plugin is password-aodh-legacy for
    # backward compatibily
    return [('service_credentials', (
            loading.get_auth_common_conf_options() +
            loading.get_auth_plugin_conf_options('password')))]
