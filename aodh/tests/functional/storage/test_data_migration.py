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
import datetime
import uuid

import mock
from oslo_config import fixture as fixture_config

from aodh.cmd import data_migration
from aodh import service
from aodh import storage
from aodh.storage import models as alarm_models
from aodh.tests.functional import db as tests_db
from aodh.tests.functional.storage import test_storage_scenarios


@tests_db.run_with('hbase', 'mongodb')
class TestDataMigration(test_storage_scenarios.AlarmTestBase):

    def setUp(self):
        sql_conf = service.prepare_service(argv=[], config_files=[])
        self.sql_conf = self.useFixture(fixture_config.Config(sql_conf)).conf
        # using sqlite to represent the type of SQL dbs
        self.sql_conf.set_override('connection', "sqlite://",
                                   group="database", enforce_type=True)
        self.sql_namager = tests_db.SQLiteManager(self.sql_conf)
        self.useFixture(self.sql_namager)
        self.sql_conf.set_override('connection', self.sql_namager.url,
                                   group="database", enforce_type=True)
        self.sql_alarm_conn = storage.get_connection_from_config(self.sql_conf)
        self.sql_alarm_conn.upgrade()
        super(TestDataMigration, self).setUp()
        self.add_some_alarms()
        self._add_some_alarm_changes()

    def tearDown(self):
        self.sql_alarm_conn.clear()
        self.sql_alarm_conn = None
        super(TestDataMigration, self).tearDown()

    def _add_some_alarm_changes(self):
        alarms = list(self.alarm_conn.get_alarms())
        i = 0
        for alarm in alarms:
            for change_type in [alarm_models.AlarmChange.CREATION,
                                alarm_models.AlarmChange.RULE_CHANGE,
                                alarm_models.AlarmChange.STATE_TRANSITION,
                                alarm_models.AlarmChange.STATE_TRANSITION,
                                alarm_models.AlarmChange.STATE_TRANSITION]:
                alarm_change = {
                    "event_id": str(uuid.uuid4()),
                    "alarm_id": alarm.alarm_id,
                    "type": change_type,
                    "detail": "detail %s" % alarm.name,
                    "user_id": alarm.user_id,
                    "project_id": alarm.project_id,
                    "on_behalf_of": alarm.project_id,
                    "timestamp": datetime.datetime(2014, 4, 7, 7, 30 + i)
                }
                self.alarm_conn.record_alarm_change(alarm_change=alarm_change)
                i += 1

    def test_data_migration_without_history_data(self):
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))
        alarms_sql = list(self.sql_alarm_conn.get_alarms())
        self.assertEqual(0, len(alarms_sql))
        test_args = data_migration.get_parser().parse_args(
            ['--sql-conn', 'sqlite://', '--nosql-conn',
             self.CONF.database.connection, '--migrate-history', False])
        with mock.patch('argparse.ArgumentParser.parse_args') as args_parser:
            # because get_connection_from_config has been mocked in
            # aodh.tests.functional.db.TestBase#setUp, here re-mocked it that
            # this test can get nosql and sql storage connections
            with mock.patch('aodh.storage.get_connection_from_config') as conn:
                conn.side_effect = [self.alarm_conn, self.sql_alarm_conn]
                args_parser.return_value = test_args
                data_migration.main()
        alarms_sql = list(self.sql_alarm_conn.get_alarms())
        alarm_changes = list(self.sql_alarm_conn.query_alarm_history())
        self.assertEqual(0, len(alarm_changes))
        self.assertEqual(3, len(alarms_sql))
        self.assertEqual(sorted([a.alarm_id for a in alarms]),
                         sorted([a.alarm_id for a in alarms_sql]))

    def test_data_migration_with_history_data(self):
        test_args = data_migration.get_parser().parse_args(
            ['--sql-conn', 'sqlite://', '--nosql-conn',
             self.CONF.database.connection])
        with mock.patch('argparse.ArgumentParser.parse_args') as args_parser:
            # because get_connection_from_config has been mocked in
            # aodh.tests.functional.db.TestBase#setUp, here re-mocked it that
            # this test can get nosql and sql storage connections
            with mock.patch('aodh.storage.get_connection_from_config') as conn:
                conn.side_effect = [self.alarm_conn, self.sql_alarm_conn]
                args_parser.return_value = test_args
                data_migration.main()
        alarms_sql = list(self.sql_alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms_sql))
        for alarm in alarms_sql:
            changes = list(self.sql_alarm_conn.get_alarm_changes(
                alarm.alarm_id, alarm.project_id))
            self.assertEqual(5, len(changes))
