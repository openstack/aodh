#
# Copyright 2015 Huawei Technologies Co., Ltd.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import abc

import mock
from oslo_config import fixture as fixture_config
from oslo_db.sqlalchemy import test_migrations
import six
import six.moves.urllib.parse as urlparse

from aodh import service
from aodh.storage import impl_sqlalchemy
from aodh.storage.sqlalchemy import models
from aodh.tests import base


class ABCSkip(base.SkipNotImplementedMeta, abc.ABCMeta):
    pass


class ModelsMigrationsSync(
        six.with_metaclass(ABCSkip,
                           base.BaseTestCase,
                           test_migrations.ModelsMigrationsSync)):

    def setUp(self):
        super(ModelsMigrationsSync, self).setUp()
        self.db = mock.Mock()
        conf = service.prepare_service([])
        self.conf = self.useFixture(fixture_config.Config(conf)).conf
        db_url = self.conf.database.connection
        if not db_url:
            self.skipTest("The db connection option should be specified.")
        connection_scheme = urlparse.urlparse(db_url).scheme
        engine_name = connection_scheme.split('+')[0]
        if engine_name not in ('postgresql', 'mysql', 'sqlite'):
            self.skipTest("This test only works with PostgreSQL or MySQL or"
                          " SQLite")
        self.conn = impl_sqlalchemy.Connection(self.conf,
                                               self.conf.database.connection)

    @staticmethod
    def get_metadata():
        return models.Base.metadata

    def get_engine(self):
        return self.conn._engine_facade.get_engine()

    def db_sync(self, engine):
        self.conn.upgrade(nocreate=True)
