#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
"""Tests for aodh/storage/
"""
import mock
from oslo_config import fixture as fixture_config
from oslotest import base

from aodh import service
from aodh import storage
from aodh.storage import impl_log

import six


class EngineTest(base.BaseTestCase):
    def setUp(self):
        super(EngineTest, self).setUp()
        conf = service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf

    def test_get_connection(self):
        self.CONF.set_override('connection', 'log://localhost',
                               group='database')
        engine = storage.get_connection_from_config(self.CONF)
        self.assertIsInstance(engine, impl_log.Connection)

    def test_get_connection_no_such_engine(self):
        self.CONF.set_override('connection', 'no-such-engine://localhost',
                               group='database')
        self.CONF.set_override('max_retries', 0, 'database')
        try:
            storage.get_connection_from_config(self.CONF)
        except RuntimeError as err:
            self.assertIn('no-such-engine', six.text_type(err))


class ConnectionRetryTest(base.BaseTestCase):
    def setUp(self):
        super(ConnectionRetryTest, self).setUp()
        conf = service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf

    def test_retries(self):
        max_retries = 5
        with mock.patch.object(
                storage.impl_log.Connection, '__init__') as log_init:

            class ConnectionError(Exception):
                pass

            def x(a, b):
                raise ConnectionError

            log_init.side_effect = x
            self.CONF.set_override("connection", "log://", "database")
            self.CONF.set_override("retry_interval", 0.00001, "database")
            self.CONF.set_override("max_retries", max_retries, "database")
            self.assertRaises(ConnectionError,
                              storage.get_connection_from_config,
                              self.CONF)
            self.assertEqual(max_retries, log_init.call_count)


class ConnectionConfigTest(base.BaseTestCase):
    def setUp(self):
        super(ConnectionConfigTest, self).setUp()
        conf = service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf

    def test_only_default_url(self):
        self.CONF.set_override("connection", "log://", group="database")
        conn = storage.get_connection_from_config(self.CONF)
        self.assertIsInstance(conn, impl_log.Connection)
