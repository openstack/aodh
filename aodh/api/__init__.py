#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
import os

from oslo_config import cfg

# Register options for the service
OPTS = [
    cfg.StrOpt('paste_config',
               default=os.path.abspath(
                   os.path.join(
                       os.path.dirname(__file__), "api-paste.ini")),
               help="Configuration file for WSGI definition of API."),
    cfg.StrOpt(
        'auth_mode',
        default="keystone",
        help="Authentication mode to use. Unset to disable authentication"),
]
