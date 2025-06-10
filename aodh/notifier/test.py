#
# Copyright 2013-2015 eNovance
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
"""Test alarm notifier."""

from aodh import notifier


class TestAlarmNotifier(notifier.AlarmNotifier):
    "Test alarm notifier."""

    def __init__(self, conf):
        super().__init__(conf)
        self.notifications = []

    def notify(self, action, alarm_id, alarm_name, severity,
               previous, current, reason, reason_data):
        self.notifications.append((action,
                                   alarm_id,
                                   alarm_name,
                                   severity,
                                   previous,
                                   current,
                                   reason,
                                   reason_data))
