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

import aodh.api
import aodh.api.controllers.v2.alarm_rules.gnocchi
import aodh.api.controllers.v2.alarms
import aodh.coordination
import aodh.evaluator
import aodh.evaluator.event
import aodh.evaluator.gnocchi
import aodh.event
import aodh.keystone_client
import aodh.notifier.rest
import aodh.notifier.zaqar
import aodh.service
import aodh.storage


def list_opts():
    return [
        ('DEFAULT',
         itertools.chain(
             aodh.evaluator.OPTS,
             aodh.evaluator.event.OPTS,
             aodh.evaluator.threshold.OPTS,
             aodh.notifier.rest.OPTS,
             aodh.queue.OPTS,
             aodh.service.OPTS)),
        ('api',
         itertools.chain(
             aodh.api.OPTS,
             aodh.api.controllers.v2.alarm_rules.gnocchi.GNOCCHI_OPTS,
             aodh.api.controllers.v2.alarms.ALARM_API_OPTS)),
        ('coordination', aodh.coordination.OPTS),
        ('database', aodh.storage.OPTS),
        ('evaluator', aodh.service.EVALUATOR_OPTS),
        ('listener', itertools.chain(aodh.service.LISTENER_OPTS,
                                     aodh.event.OPTS)),
        ('notifier', aodh.service.NOTIFIER_OPTS),
        ('service_credentials', aodh.keystone_client.OPTS),
        ('service_types', aodh.notifier.zaqar.SERVICE_OPTS),
        ('notifier', aodh.notifier.OPTS),
    ]


def list_keystoneauth_opts():
    # NOTE(sileht): the configuration file contains only the options
    # for the password plugin that handles keystone v2 and v3 API
    # with discovery. But other options are possible.
    return [('service_credentials', (
            loading.get_auth_common_conf_options() +
            loading.get_auth_plugin_conf_options('password')))]
