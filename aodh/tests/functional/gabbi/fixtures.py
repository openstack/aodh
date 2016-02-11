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
import mock
from oslo_config import cfg
from oslo_config import fixture as fixture_config
from oslo_policy import opts
from six.moves.urllib import parse as urlparse

from aodh import service
from aodh import storage


# TODO(chdent): For now only MongoDB is supported, because of easy
# database name handling and intentional focus on the API, not the
# data store.
ENGINES = ['mongodb']


class ConfigFixture(fixture.GabbiFixture):
    """Establish the relevant configuration for a test run."""

    def start_fixture(self):
        """Set up config."""

        self.conf = None

        # Determine the database connection.
        db_url = os.environ.get(
            'AODH_TEST_STORAGE_URL',
            os.environ.get(
                "OVERTEST_URL", 'sqlite://').replace(
                    "mysql://", "mysql+pymysql://"))
        if not db_url:
            raise case.SkipTest('No database connection configured')

        engine = urlparse.urlparse(db_url).scheme
        if engine not in ENGINES:
            raise case.SkipTest('Database engine not supported')

        conf = service.prepare_service([], config_files=[])
        # NOTE(jd): prepare_service() is called twice: first by load_app() for
        # Pecan, then Pecan calls pastedeploy, which starts the app, which has
        # no way to pass the conf object so that Paste apps calls again
        # prepare_service. In real life, that's not a problem, but here we want
        # to be sure that the second time the same conf object is returned
        # since we tweaked it. To that, once we called prepare_service() we
        # mock it so it returns the same conf object.
        self.prepare_service = service.prepare_service
        service.prepare_service = mock.Mock()
        service.prepare_service.return_value = conf
        conf = fixture_config.Config(conf).conf
        self.conf = conf
        opts.set_defaults(self.conf)

        conf.set_override('policy_file',
                          os.path.abspath(
                              'aodh/tests/open-policy.json'),
                          group='oslo_policy',
                          enforce_type=True)
        conf.set_override(
            'paste_config',
            os.path.abspath('aodh/tests/functional/gabbi/gabbi_paste.ini'),
            group='api',
        )

        database_name = '%s-%s' % (db_url, str(uuid.uuid4()))
        conf.set_override('connection', database_name, group='database',
                          enforce_type=True)

        conf.set_override('pecan_debug', True, group='api',
                          enforce_type=True)

    def stop_fixture(self):
        """Reset the config and remove data."""
        if self.conf:
            storage.get_connection_from_config(self.conf).clear()
            self.conf.reset()
        service.prepare_service = self.prepare_service


class CORSConfigFixture(fixture.GabbiFixture):
    """Inject mock configuration for the CORS middleware."""

    def start_fixture(self):
        # Here we monkeypatch GroupAttr.__getattr__, necessary because the
        # paste.ini method of initializing this middleware creates its own
        # ConfigOpts instance, bypassing the regular config fixture.

        def _mock_getattr(instance, key):
            if key != 'allowed_origin':
                return self._original_call_method(instance, key)
            return "http://valid.example.com"

        self._original_call_method = cfg.ConfigOpts.GroupAttr.__getattr__
        cfg.ConfigOpts.GroupAttr.__getattr__ = _mock_getattr

    def stop_fixture(self):
        """Remove the monkeypatch."""
        cfg.ConfigOpts.GroupAttr.__getattr__ = self._original_call_method
