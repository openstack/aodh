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
from unittest import mock

from oslo_db.sqlalchemy import enginefacade
from oslo_db.sqlalchemy import test_migrations

from aodh.storage.sqlalchemy import models
from aodh.tests import base
from aodh.tests.functional import db as tests_db


class ABCSkip(base.SkipNotImplementedMeta, abc.ABCMeta):
    pass


class ModelsMigrationsSync(tests_db.TestBase,
                           test_migrations.ModelsMigrationsSync,
                           metaclass=ABCSkip):

    def setUp(self):
        super(ModelsMigrationsSync, self).setUp()
        self.db = mock.Mock()

    @staticmethod
    def get_metadata():
        return models.Base.metadata

    def get_engine(self):
        return enginefacade.writer.get_engine()

    def db_sync(self, engine):
        pass
