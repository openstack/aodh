# Copyright 2019 Catalyst Cloud Ltd.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from oslo_config import fixture
from oslotest import base

from aodh import service


class TestNotifierBase(base.BaseTestCase):
    def setUp(self):
        super().setUp()

        conf = service.prepare_service(argv=[], config_files=[])

        self.conf = self.useFixture(fixture.Config(conf)).conf
