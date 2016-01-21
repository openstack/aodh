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
"""Tests for aodh/storage/impl_mongodb.py

.. note::
  In order to run the tests against another MongoDB server set the
  environment variable aodh_TEST_MONGODB_URL to point to a MongoDB
  server before running the tests.

"""
import unittest

try:
    from aodh.storage import impl_mongodb
except ImportError:
    impl_mongodb = None
from aodh.tests import base as test_base
from aodh.tests.functional import db as tests_db


@unittest.skipUnless(impl_mongodb, "pymongo not available")
@tests_db.run_with('mongodb')
class MongoDBConnection(tests_db.TestBase):
    def test_connection_pooling(self):
        test_conn = impl_mongodb.Connection(self.CONF,
                                            self.CONF.database.connection)
        self.assertEqual(self.alarm_conn.conn, test_conn.conn)

    def test_replica_set(self):
        url = self.CONF.database.connection + '?replicaSet=foobar'
        conn = impl_mongodb.Connection(self.CONF, url)
        self.assertTrue(conn.conn)


@unittest.skipUnless(impl_mongodb, "pymongo not available")
@tests_db.run_with('mongodb')
class IndexTest(tests_db.TestBase):
    def _test_ttl_index_absent(self, conn, coll_name, ttl_opt):
        # create a fake index and check it is deleted
        coll = getattr(conn.db, coll_name)
        index_name = '%s_ttl' % coll_name
        self.CONF.set_override(ttl_opt, -1, group='database',
                               enforce_type=True)
        conn.upgrade()
        self.assertNotIn(index_name, coll.index_information())

        self.CONF.set_override(ttl_opt, 456789, group='database',
                               enforce_type=True)
        conn.upgrade()
        self.assertEqual(456789,
                         coll.index_information()
                         [index_name]['expireAfterSeconds'])

    def test_alarm_history_ttl_index_absent(self):
        self._test_ttl_index_absent(self.alarm_conn, 'alarm_history',
                                    'alarm_history_time_to_live')

    def _test_ttl_index_present(self, conn, coll_name, ttl_opt):
        coll = getattr(conn.db, coll_name)
        self.CONF.set_override(ttl_opt, 456789, group='database',
                               enforce_type=True)
        conn.upgrade()
        index_name = '%s_ttl' % coll_name
        self.assertEqual(456789,
                         coll.index_information()
                         [index_name]['expireAfterSeconds'])

        self.CONF.set_override(ttl_opt, -1, group='database',
                               enforce_type=True)
        conn.upgrade()
        self.assertNotIn(index_name, coll.index_information())

    def test_alarm_history_ttl_index_present(self):
        self._test_ttl_index_present(self.alarm_conn, 'alarm_history',
                                     'alarm_history_time_to_live')


class CapabilitiesTest(test_base.BaseTestCase):
    @unittest.skipUnless(impl_mongodb, "pymongo not available")
    def test_alarm_capabilities(self):
        expected_capabilities = {
            'alarms': {'query': {'simple': True,
                                 'complex': True},
                       'history': {'query': {'simple': True,
                                             'complex': True}}},
        }

        actual_capabilities = impl_mongodb.Connection.get_capabilities()
        self.assertEqual(expected_capabilities, actual_capabilities)
