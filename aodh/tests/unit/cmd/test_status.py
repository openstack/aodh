# Copyright (c) 2018 NEC, Corp.
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

from oslo_config import cfg
from oslo_upgradecheck.upgradecheck import Code

from aodh.cmd import status
from aodh.tests import base


class TestUpgradeChecks(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.cmd = status.Checks()
        cfg.CONF(args=[], project='aodh')

    def test_checks(self):
        for name, func in self.cmd._upgrade_checks:
            if isinstance(func, tuple):
                func_name, kwargs = func
                result = func_name(self, **kwargs)
            else:
                result = func(self)
            self.assertEqual(Code.SUCCESS, result.code)
