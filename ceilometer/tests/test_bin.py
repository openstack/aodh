#!/usr/bin/env python
#
# Copyright 2012 eNovance <licensing@enovance.com>
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

import json
import os
import random
import socket
import subprocess
import time

import httplib2
import six

from ceilometer.openstack.common import fileutils
from ceilometer.tests import base


class BinTestCase(base.BaseTestCase):
    def setUp(self):
        super(BinTestCase, self).setUp()
        content = ("[DEFAULT]\n"
                   "rpc_backend=fake\n"
                   "[database]\n"
                   "connection=log://localhost\n")
        if six.PY3:
            content = content.encode('utf-8')
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')

    def tearDown(self):
        super(BinTestCase, self).tearDown()
        os.remove(self.tempfile)

    def test_dbsync_run(self):
        subp = subprocess.Popen(['ceilometer-dbsync',
                                 "--config-file=%s" % self.tempfile])
        self.assertEqual(0, subp.wait())

    def test_run_expirer_ttl_disabled(self):
        subp = subprocess.Popen(['ceilometer-expirer',
                                 '-d',
                                 "--config-file=%s" % self.tempfile],
                                stderr=subprocess.PIPE)
        __, err = subp.communicate()
        self.assertEqual(0, subp.poll())
        self.assertIn(b"Nothing to clean, database alarm history "
                      b"time to live is disabled", err)

    def test_run_expirer_ttl_enabled(self):
        content = ("[DEFAULT]\n"
                   "rpc_backend=fake\n"
                   "[database]\n"
                   "alarm_history_time_to_live=1\n"
                   "connection=log://localhost\n")
        if six.PY3:
            content = content.encode('utf-8')
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')
        subp = subprocess.Popen(['ceilometer-expirer',
                                 '-d',
                                 "--config-file=%s" % self.tempfile],
                                stderr=subprocess.PIPE)
        __, err = subp.communicate()
        self.assertEqual(0, subp.poll())
        msg = "Dropping alarm history data with TTL 1"
        if six.PY3:
            msg = msg.encode('utf-8')
        self.assertIn(msg, err)


class BinApiTestCase(base.BaseTestCase):

    def setUp(self):
        super(BinApiTestCase, self).setUp()
        # create api_paste.ini file without authentication
        content = ("[pipeline:main]\n"
                   "pipeline = api-server\n"
                   "[app:api-server]\n"
                   "paste.app_factory = ceilometer.api.app:app_factory\n")
        if six.PY3:
            content = content.encode('utf-8')
        self.paste = fileutils.write_to_tempfile(content=content,
                                                 prefix='api_paste',
                                                 suffix='.ini')

        # create ceilometer.conf file
        self.api_port = random.randint(10000, 11000)
        self.http = httplib2.Http(proxy_info=None)
        self.pipeline_cfg_file = self.path_get('etc/ceilometer/pipeline.yaml')
        self.policy_file = self.path_get('etc/ceilometer/policy.json')

    def tearDown(self):
        super(BinApiTestCase, self).tearDown()
        try:
            self.subp.kill()
            self.subp.wait()
        except OSError:
            pass
        os.remove(self.tempfile)

    def get_response(self, path):
        url = 'http://%s:%d/%s' % ('127.0.0.1', self.api_port, path)

        for x in range(10):
            try:
                r, c = self.http.request(url, 'GET')
            except socket.error:
                time.sleep(.5)
                self.assertIsNone(self.subp.poll())
            else:
                return r, c
        return None, None

    def run_api(self, content, err_pipe=None):
        if six.PY3:
            content = content.encode('utf-8')

        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')
        if err_pipe:
            return subprocess.Popen(['ceilometer-api',
                                    "--config-file=%s" % self.tempfile],
                                    stderr=subprocess.PIPE)
        else:
            return subprocess.Popen(['ceilometer-api',
                                    "--config-file=%s" % self.tempfile])

    def test_v2(self):
        content = ("[DEFAULT]\n"
                   "rpc_backend=fake\n"
                   "auth_strategy=noauth\n"
                   "debug=true\n"
                   "pipeline_cfg_file={0}\n"
                   "api_paste_config={2}\n"
                   "[api]\n"
                   "port={3}\n"
                   "[oslo_policy]\n"
                   "policy_file={1}\n"
                   "[database]\n"
                   "connection=log://localhost\n".
                   format(self.pipeline_cfg_file,
                          self.policy_file,
                          self.paste,
                          self.api_port))

        self.subp = self.run_api(content)

        response, content = self.get_response('v2/alarms')
        self.assertEqual(200, response.status)
        if six.PY3:
            content = content.decode('utf-8')
        self.assertEqual([], json.loads(content))
