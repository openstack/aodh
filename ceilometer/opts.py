# Copyright 2014 eNovance
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

import ceilometer.alarm.notifier.rest
import ceilometer.alarm.rpc
import ceilometer.alarm.service
import ceilometer.api
import ceilometer.api.app
import ceilometer.api.controllers.v2.alarms
import ceilometer.coordination
import ceilometer.service
import ceilometer.storage


def list_opts():
    return [
        ('DEFAULT',
         itertools.chain(ceilometer.api.app.OPTS,
                         ceilometer.service.OPTS,
                         ceilometer.storage.OLD_OPTS,)),
        ('alarm',
         itertools.chain(ceilometer.alarm.notifier.rest.OPTS,
                         ceilometer.alarm.service.OPTS,
                         ceilometer.alarm.rpc.OPTS,
                         ceilometer.alarm.evaluator.gnocchi.OPTS,
                         ceilometer.api.controllers.v2.alarms.ALARM_API_OPTS)),
        ('api',
         itertools.chain(ceilometer.api.OPTS,
                         ceilometer.api.app.API_OPTS,)),
        ('coordination', ceilometer.coordination.OPTS),
        ('database', ceilometer.storage.OPTS),
        ('service_credentials', ceilometer.service.CLI_OPTS),
    ]
