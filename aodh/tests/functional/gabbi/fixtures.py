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

from gabbi import fixture
import mock
from oslo_config import cfg
from oslo_config import fixture as fixture_config
from oslo_policy import opts
from oslo_utils import uuidutils
from six.moves.urllib import parse as urlparse
import sqlalchemy_utils

from aodh.api import app
from aodh import service
from aodh import storage


# NOTE(chdent): Hack to restore semblance of global configuration to
# pass to the WSGI app used per test suite. LOAD_APP_KWARGS are the olso
# configuration, and the pecan application configuration of
# which the critical part is a reference to the current indexer.
LOAD_APP_KWARGS = None


def setup_app():
    global LOAD_APP_KWARGS
    return app.load_app(**LOAD_APP_KWARGS)


class ConfigFixture(fixture.GabbiFixture):
    """Establish the relevant configuration for a test run."""

    def start_fixture(self):
        """Set up config."""

        global LOAD_APP_KWARGS

        self.conf = None
        self.conn = None

        # Determine the database connection.
        db_url = os.environ.get(
            'AODH_TEST_STORAGE_URL', "").replace(
                "mysql://", "mysql+pymysql://")
        if not db_url:
            self.fail('No database connection configured')

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
                          group='oslo_policy')
        conf.set_override('auth_mode', None, group='api')

        parsed_url = urlparse.urlparse(db_url)
        if parsed_url.scheme != 'sqlite':
            parsed_url = list(parsed_url)
            parsed_url[2] += '-%s' % uuidutils.generate_uuid(dashed=False)
            db_url = urlparse.urlunparse(parsed_url)

        conf.set_override('connection', db_url, group='database')

        if (parsed_url[0].startswith("mysql")
           or parsed_url[0].startswith("postgresql")):
            sqlalchemy_utils.create_database(conf.database.connection)

        self.conn = storage.get_connection_from_config(self.conf)
        self.conn.upgrade()

        LOAD_APP_KWARGS = {
            'conf': conf,
        }

    def stop_fixture(self):
        """Reset the config and remove data."""
        if self.conn:
            self.conn.clear()
        if self.conf:
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
