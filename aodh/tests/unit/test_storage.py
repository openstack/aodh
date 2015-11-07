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
from oslotest import base

from aodh.storage import base as storage_base


class TestUtils(base.BaseTestCase):

    def test_dict_to_kv(self):
        data = {'a': 'A',
                'b': 'B',
                'nested': {'a': 'A',
                           'b': 'B',
                           },
                'nested2': [{'c': 'A'}, {'c': 'B'}]
                }
        pairs = list(storage_base.dict_to_keyval(data))
        self.assertEqual([('a', 'A'),
                          ('b', 'B'),
                         ('nested.a', 'A'),
                         ('nested.b', 'B'),
                         ('nested2[0].c', 'A'),
                         ('nested2[1].c', 'B')],
                         sorted(pairs, key=lambda x: x[0]))
