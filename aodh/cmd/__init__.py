# -*- encoding: utf-8 -*-
#
# Copyright 2017 Red Hat, Inc.
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
import sys


def config_generator():
    try:
        from oslo_config import generator
        generator.main(
            ['--config-file',
             '%s/aodh-config-generator.conf' % os.path.dirname(__file__)]
            + sys.argv[1:])
    except Exception as e:
        print("Unable to build sample configuration file: %s" % e)
        return 1
