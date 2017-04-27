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

import fixtures
from oslo_config import fixture as fixture_config
from oslo_utils import uuidutils
import six
from six.moves.urllib import parse as urlparse

from aodh import service
from aodh import storage
from aodh.tests import base as test_base


class SQLManager(fixtures.Fixture):
    def __init__(self, conf):
        self.conf = conf
        db_name = 'aodh_%s' % uuidutils.generate_uuid(dashed=False)
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


class SQLiteManager(fixtures.Fixture):

    def __init__(self, conf):
        self.url = "sqlite://"


@six.add_metaclass(test_base.SkipNotImplementedMeta)
class TestBase(test_base.BaseTestCase):

    DRIVER_MANAGERS = {
        'mysql': MySQLManager,
        'postgresql': PgSQLManager,
        'sqlite': SQLiteManager,
    }

    def setUp(self):
        super(TestBase, self).setUp()
        db_url = os.environ.get(
            'AODH_TEST_STORAGE_URL',
            'sqlite://').replace(
                "mysql://", "mysql+pymysql://")
        engine = urlparse.urlparse(db_url).scheme
        # In case some drivers have additional specification, for example:
        # PyMySQL will have scheme mysql+pymysql.
        self.engine = engine.split('+')[0]

        conf = service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf
        self.CONF.set_override('connection', db_url, group="database")

        manager = self.DRIVER_MANAGERS.get(self.engine)
        if not manager:
            self.skipTest("missing driver manager: %s" % self.engine)

        self.db_manager = manager(self.CONF)

        self.useFixture(self.db_manager)

        self.CONF.set_override('connection', self.db_manager.url,
                               group="database")

        self.alarm_conn = storage.get_connection_from_config(self.CONF)
        self.alarm_conn.upgrade()

        self.useFixture(fixtures.MockPatch(
            'aodh.storage.get_connection_from_config',
            side_effect=self._get_connection))

    def tearDown(self):
        self.alarm_conn.clear()
        self.alarm_conn = None
        super(TestBase, self).tearDown()

    def _get_connection(self, conf):
        return self.alarm_conn
