#
# Copyright 2015 Red Hat. All Rights Reserved.
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

"""Fixtures used during Gabbi-based test runs."""

import os
from unittest import case
import uuid

from gabbi import fixture
from oslo_config import fixture as fixture_config
from oslo_policy import opts

from ceilometer import service
from ceilometer import storage


# TODO(chdent): For now only MongoDB is supported, because of easy
# database name handling and intentional focus on the API, not the
# data store.
ENGINES = ['MONGODB']


class ConfigFixture(fixture.GabbiFixture):
    """Establish the relevant configuration for a test run."""

    def start_fixture(self):
        """Set up config."""

        self.conf = None

        # Determine the database connection.
        db_url = None
        for engine in ENGINES:
            try:
                db_url = os.environ['CEILOMETER_TEST_%s_URL' % engine]
            except KeyError:
                pass
        if db_url is None:
            raise case.SkipTest('No database connection configured')

        service.prepare_service([])
        conf = fixture_config.Config().conf
        self.conf = conf
        opts.set_defaults(self.conf)
        conf.set_override('policy_file',
                          os.path.abspath('etc/ceilometer/policy.json'),
                          group='oslo_policy')

        database_name = '%s-%s' % (db_url, str(uuid.uuid4()))
        conf.set_override('alarm_connection', database_name, group='database')

        conf.set_override('pecan_debug', True, group='api')

    def stop_fixture(self):
        """Reset the config and remove data."""
        if self.conf:
            storage.get_connection_from_config(self.conf).clear()
            self.conf.reset()
