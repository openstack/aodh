#
# Copyright 2012 New Dream Network (DreamHost)
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
"""Test base classes.
"""

import fixtures
import functools
import os.path
import unittest
import warnings

import oslo_messaging.conffixture
from oslo_utils import timeutils
from oslotest import base
from sqlalchemy import exc as sqla_exc
import webtest

import aodh
from aodh import messaging


class WarningsFixture(fixtures.Fixture):
    """Filters out warnings during test runs."""

    def setUp(self):
        super().setUp()

        self._original_warning_filters = warnings.filters[:]

        warnings.simplefilter('once', DeprecationWarning)

        # FIXME(stephenfin): Determine if we need to replace use of best_match
        warnings.filterwarnings(
            'ignore',
            module='webob',
            message='The behavior of AcceptValidHeader.best_match is ',
            category=DeprecationWarning,
        )

        # FIXME(stephenfin): Determine if we need to replace use of best_match
        warnings.filterwarnings(
            'ignore',
            module='webob',
            message='The behavior of .best_match for the Accept classes is ',
            category=DeprecationWarning,
        )

        # FIXME(stephenfin): Update tests to resolve these issues
        warnings.filterwarnings(
            'ignore',
            module='oslo_policy',
            message='Policy ".*": ".*" failed scope check. ',
            category=UserWarning,
        )

        # Enable deprecation warnings for aodh itself to capture upcoming
        # SQLAlchemy changes

        warnings.filterwarnings(
            'ignore',
            category=sqla_exc.SADeprecationWarning,
        )

        warnings.filterwarnings(
            'error',
            module='aodh',
            category=sqla_exc.SADeprecationWarning,
        )

        # Enable general SQLAlchemy warnings also to ensure we're not doing
        # silly stuff. It's possible that we'll need to filter things out here
        # with future SQLAlchemy versions, but that's a good thing

        warnings.filterwarnings(
            'error',
            module='aodh',
            category=sqla_exc.SAWarning,
        )

        self.addCleanup(self._reset_warning_filters)

    def _reset_warning_filters(self):
        warnings.filters[:] = self._original_warning_filters


class BaseTestCase(base.BaseTestCase):
    def setup_messaging(self, conf, exchange=None):
        self.useFixture(oslo_messaging.conffixture.ConfFixture(conf))
        self.useFixture(WarningsFixture())
        conf.set_override("notification_driver", ["messaging"])
        if not exchange:
            exchange = 'aodh'
        conf.set_override("control_exchange", exchange)

        # NOTE(sileht): Ensure a new oslo.messaging driver is loaded
        # between each tests
        self.transport = messaging.get_transport(conf, "fake://", cache=False)
        self.useFixture(fixtures.MockPatch(
            'aodh.messaging.get_transport',
            return_value=self.transport))

    def assertTimestampEqual(self, first, second, msg=None):
        """Checks that two timestamps are equals.

        This relies on assertAlmostEqual to avoid rounding problem, and only
        checks up the first microsecond values.

        """
        return self.assertAlmostEqual(
            timeutils.delta_seconds(first, second),
            0.0,
            places=5)

    def assertIsEmpty(self, obj):
        try:
            if len(obj) != 0:
                self.fail("%s is not empty" % type(obj))
        except (TypeError, AttributeError):
            self.fail("%s doesn't have length" % type(obj))

    def assertIsNotEmpty(self, obj):
        try:
            if len(obj) == 0:
                self.fail("%s is empty" % type(obj))
        except (TypeError, AttributeError):
            self.fail("%s doesn't have length" % type(obj))

    def assertDictContains(self, parent, child):
        """Checks whether child dict is a subset of parent.

        assertDictContainsSubset() in standard Python 2.7 has been deprecated
        since Python 3.2
        """
        self.assertEqual(parent, dict(parent, **child))

    @staticmethod
    def path_get(project_file=None):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                            '..',
                                            '..',
                                            )
                               )
        if project_file:
            return os.path.join(root, project_file)
        else:
            return root

    def assert_single_item(self, items, **filters):
        return self.assert_multiple_items(items, 1, **filters)[0]

    def assert_multiple_items(self, items, count, **filters):
        def _matches(item, **props):
            for prop_name, prop_val in props.items():
                v = (item[prop_name] if isinstance(item, dict)
                     else getattr(item, prop_name))
                if v != prop_val:
                    return False
            return True

        filtered_items = list(
            [item for item in items if _matches(item, **filters)]
        )
        found = len(filtered_items)

        if found != count:
            self.fail("Wrong number of items found [filters=%s, "
                      "expected=%s, found=%s]" % (filters, count, found))

        return filtered_items


def _skip_decorator(func):
    @functools.wraps(func)
    def skip_if_not_implemented(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except aodh.NotImplementedError as e:
            raise unittest.SkipTest(str(e))
        except webtest.app.AppError as e:
            if 'not implemented' in str(e):
                raise unittest.SkipTest(str(e))
            raise
    return skip_if_not_implemented


class SkipNotImplementedMeta(type):
    def __new__(cls, name, bases, local):
        for attr in local:
            value = local[attr]
            if callable(value) and (
                    attr.startswith('test_') or attr == 'setUp'):
                local[attr] = _skip_decorator(value)
        return type.__new__(cls, name, bases, local)
