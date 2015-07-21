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

import aodh.api
import aodh.api.app
import aodh.api.controllers.v2.alarms
import aodh.coordination
import aodh.notifier.rest
import aodh.rpc
import aodh.service
import aodh.storage


def list_opts():
    return [
        ('DEFAULT',
         itertools.chain(aodh.api.app.OPTS,
                         aodh.notifier.rest.OPTS,
                         aodh.service.OPTS,
                         aodh.rpc.OPTS,
                         aodh.storage.OLD_OPTS,)),
        ('alarm',
         itertools.chain(aodh.alarm.evaluator.gnocchi.OPTS,
                         aodh.api.controllers.v2.alarms.ALARM_API_OPTS)),
        ('api',
         itertools.chain(aodh.api.OPTS,
                         aodh.api.app.API_OPTS,)),
        ('coordination', aodh.coordination.OPTS),
        ('database', aodh.storage.OPTS),
        ('service_credentials', aodh.service.CLI_OPTS),
    ]
