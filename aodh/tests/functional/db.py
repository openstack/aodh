#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 eNovance
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

"""Base classes for API tests."""
import os
import uuid

import fixtures
import mock
from oslo_config import fixture as fixture_config
from oslotest import mockpatch
import six
from six.moves.urllib import parse as urlparse
from testtools import testcase

from aodh import service
from aodh import storage
from aodh.tests import base as test_base
try:
    from aodh.tests import mocks
except ImportError:
    mocks = None   # happybase module is not Python 3 compatible yet


class MongoDbManager(fixtures.Fixture):

    def __init__(self, conf):
        self.url = '%(url)s_%(db)s' % {
            'url': conf.database.connection,
            'db': uuid.uuid4().hex,
        }


class SQLManager(fixtures.Fixture):
    def __init__(self, conf):
        self.conf = conf
        db_name = 'aodh_%s' % uuid.uuid4().hex
        import sqlalchemy
        self._engine = sqlalchemy.create_engine(conf.database.connection)
        self._conn = self._engine.connect()
        self._create_db(self._conn, db_name)
        self._conn.close()
        self._engine.dispose()
        parsed = list(urlparse.urlparse(conf.database.connection))
        # NOTE(jd) We need to set an host otherwise urlunparse() will not
        # construct a proper URL
        if parsed[1] == '':
            parsed[1] = 'localhost'
        parsed[2] = '/' + db_name
        self.url = urlparse.urlunparse(parsed)


class PgSQLManager(SQLManager):

    @staticmethod
    def _create_db(conn, db_name):
        conn.connection.set_isolation_level(0)
        conn.execute('CREATE DATABASE %s WITH TEMPLATE template0;' % db_name)
        conn.connection.set_isolation_level(1)


class MySQLManager(SQLManager):

    @staticmethod
    def _create_db(conn, db_name):
        conn.execute('CREATE DATABASE %s;' % db_name)


class HBaseManager(fixtures.Fixture):
    def __init__(self, conf):
        self.url = '%s?table_prefix=%s' % (
            conf.database.connection,
            os.getenv("AODH_TEST_HBASE_TABLE_PREFIX", "test")
        )

    def setUp(self):
        super(HBaseManager, self).setUp()
        # Unique prefix for each test to keep data is distinguished because
        # all test data is stored in one table
        data_prefix = str(uuid.uuid4().hex)

        def table(conn, name):
            return mocks.MockHBaseTable(name, conn, data_prefix)

        # Mock only real HBase connection, MConnection "table" method
        # stays origin.
        mock.patch('happybase.Connection.table', new=table).start()
        # We shouldn't delete data and tables after each test,
        # because it last for too long.
        # All tests tables will be deleted in setup-test-env.sh
        mock.patch("happybase.Connection.disable_table",
                   new=mock.MagicMock()).start()
        mock.patch("happybase.Connection.delete_table",
                   new=mock.MagicMock()).start()
        mock.patch("happybase.Connection.create_table",
                   new=mock.MagicMock()).start()


class SQLiteManager(fixtures.Fixture):

    def __init__(self, conf):
        self.url = "sqlite://"


@six.add_metaclass(test_base.SkipNotImplementedMeta)
class TestBase(test_base.BaseTestCase):

    DRIVER_MANAGERS = {
        'mongodb': MongoDbManager,
        'mysql': MySQLManager,
        'postgresql': PgSQLManager,
        'sqlite': SQLiteManager,
    }
    if mocks is not None:
        DRIVER_MANAGERS['hbase'] = HBaseManager

    def setUp(self):
        super(TestBase, self).setUp()
        db_url = os.environ.get(
            'AODH_TEST_STORAGE_URL',
            'sqlite://').replace(
                "mysql://", "mysql+pymysql://")
        engine = urlparse.urlparse(db_url).scheme
        # In case some drivers have additional specification, for example:
        # PyMySQL will have scheme mysql+pymysql.
        engine = engine.split('+')[0]

        # NOTE(Alexei_987) Shortcut to skip expensive db setUp
        test_method = self._get_test_method()
        if (hasattr(test_method, '_run_with')
                and engine not in test_method._run_with):
            raise testcase.TestSkipped(
                'Test is not applicable for %s' % engine)

        conf = service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf
        self.CONF.set_override('connection', db_url, group="database",
                               enforce_type=True)

        manager = self.DRIVER_MANAGERS.get(engine)
        if not manager:
            self.skipTest("missing driver manager: %s" % engine)

        self.db_manager = manager(self.CONF)

        self.useFixture(self.db_manager)

        self.CONF.set_override('connection', self.db_manager.url,
                               group="database", enforce_type=True)

        self.alarm_conn = storage.get_connection_from_config(self.CONF)
        self.alarm_conn.upgrade()

        self.useFixture(mockpatch.Patch(
            'aodh.storage.get_connection_from_config',
            side_effect=self._get_connection))

    def tearDown(self):
        self.alarm_conn.clear()
        self.alarm_conn = None
        super(TestBase, self).tearDown()

    def _get_connection(self, conf):
        return self.alarm_conn


def run_with(*drivers):
    """Used to mark tests that are only applicable for certain db driver.

    Skips test if driver is not available.
    """
    def decorator(test):
        if isinstance(test, type) and issubclass(test, TestBase):
            # Decorate all test methods
            for attr in dir(test):
                if attr.startswith('test_'):
                    value = getattr(test, attr)
                    if callable(value):
                        if six.PY3:
                            value._run_with = drivers
                        else:
                            value.__func__._run_with = drivers
        else:
            test._run_with = drivers
        return test
    return decorator
