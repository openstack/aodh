# -*- encoding: utf-8 -*-
#
# Copyright 2014 OpenStack Foundation
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

import cotyledon

from aodh import evaluator as evaluator_svc
from aodh import event as event_svc
from aodh import notifier as notifier_svc
from aodh import service


def notifier():
    conf = service.prepare_service()
    sm = cotyledon.ServiceManager()
    sm.add(notifier_svc.AlarmNotifierService,
           workers=conf.notifier.workers, args=(conf,))
    sm.run()


def evaluator():
    conf = service.prepare_service()
    sm = cotyledon.ServiceManager()
    sm.add(evaluator_svc.AlarmEvaluationService,
           workers=conf.evaluator.workers, args=(conf,))
    sm.run()


def listener():
    conf = service.prepare_service()
    sm = cotyledon.ServiceManager()
    sm.add(event_svc.EventAlarmEvaluationService,
           workers=conf.listener.workers, args=(conf,))
    sm.run()
