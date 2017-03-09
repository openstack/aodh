#
# Copyright 2013 eNovance <licensing@enovance.com>
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
import fixtures
import mock
from oslo_config import fixture
from oslotest import base

from aodh import service


class TestEvaluatorBase(base.BaseTestCase):
    def setUp(self):
        super(TestEvaluatorBase, self).setUp()
        conf = service.prepare_service(argv=[], config_files=[])
        self.conf = self.useFixture(fixture.Config(conf)).conf
        self.api_client = mock.Mock()
        self.useFixture(
            fixtures.MockPatch('ceilometerclient.client.get_client',
                               return_value=self.api_client))
        self.evaluator = self.EVALUATOR(self.conf)
        self.notifier = mock.MagicMock()
        self.evaluator.notifier = self.notifier
        self.storage_conn = mock.MagicMock()
        self.evaluator.storage_conn = self.storage_conn
        self.evaluator._ks_client = mock.Mock(user_id='fake_user_id',
                                              project_id='fake_project_id',
                                              auth_token='fake_token')
        self.prepare_alarms()

    def prepare_alarms(self):
        self.alarms = []

    def _evaluate_all_alarms(self):
        for alarm in self.alarms:
            self.evaluator.evaluate(alarm)

    def _set_all_alarms(self, state):
        for alarm in self.alarms:
            alarm.state = state

    def _assert_all_alarms(self, state):
        for alarm in self.alarms:
            self.assertEqual(state, alarm.state)
