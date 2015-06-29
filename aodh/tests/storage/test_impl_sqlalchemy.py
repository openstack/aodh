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
"""Tests for aodh/storage/impl_sqlalchemy.py

.. note::
  In order to run the tests against real SQL server set the environment
  variable aodh_TEST_SQL_URL to point to a SQL server before running
  the tests.

"""

from aodh.storage import impl_sqlalchemy as impl_sqla_alarm
from aodh.tests import base as test_base


class CapabilitiesTest(test_base.BaseTestCase):
    def test_alarm_capabilities(self):
        expected_capabilities = {
            'alarms': {'query': {'simple': True,
                                 'complex': True},
                       'history': {'query': {'simple': True,
                                             'complex': True}}},
        }

        actual_capabilities = impl_sqla_alarm.Connection.get_capabilities()
        self.assertEqual(expected_capabilities, actual_capabilities)
