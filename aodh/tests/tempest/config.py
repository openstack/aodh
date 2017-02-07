#
# Copyright 2012 OpenStack Foundation
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

from oslo_config import cfg

service_option = [
    cfg.BoolOpt("aodh_plugin",
                default=True,
                help="Whether or not Aodh is expected to be available"),
]

alarming_group = cfg.OptGroup(name='alarming_plugin',
                              title='Alarming Service Options')

AlarmingGroup = [
    cfg.StrOpt('catalog_type',
               default='alarming',
               help="Catalog type of the Alarming service."),
    cfg.StrOpt('endpoint_type',
               default='publicURL',
               choices=['public', 'admin', 'internal',
                        'publicURL', 'adminURL', 'internalURL'],
               help="The endpoint type to use for the alarming service."),
]
