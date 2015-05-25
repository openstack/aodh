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
"""Tests for ceilometer/storage/
"""
import mock
from oslo_config import fixture as fixture_config
from oslotest import base
import retrying

from ceilometer.alarm.storage import impl_log
from ceilometer import storage

import six


class EngineTest(base.BaseTestCase):
    def test_get_connection(self):
        engine = storage.get_connection('log://localhost',
                                        'ceilometer.alarm.storage')
        self.assertIsInstance(engine, impl_log.Connection)

    def test_get_connection_no_such_engine(self):
        try:
            storage.get_connection('no-such-engine://localhost',
                                   'ceilometer.metering.storage')
        except RuntimeError as err:
            self.assertIn('no-such-engine', six.text_type(err))


class ConnectionRetryTest(base.BaseTestCase):
    def setUp(self):
        super(ConnectionRetryTest, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf

    def test_retries(self):
        with mock.patch.object(retrying.time, 'sleep') as retry_sleep:
            try:
                self.CONF.set_override("connection", "no-such-engine://",
                                       group="database")
                storage.get_connection_from_config(self.CONF)
            except RuntimeError as err:
                self.assertIn('no-such-engine', six.text_type(err))
                self.assertEqual(9, retry_sleep.call_count)
                retry_sleep.assert_called_with(10.0)


class ConnectionConfigTest(base.BaseTestCase):
    def setUp(self):
        super(ConnectionConfigTest, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf

    def test_only_default_url(self):
        self.CONF.set_override("connection", "log://", group="database")
        conn = storage.get_connection_from_config(self.CONF, 'alarm')
        self.assertIsInstance(conn, impl_log.Connection)
