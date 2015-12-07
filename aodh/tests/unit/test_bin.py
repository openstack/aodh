#!/usr/bin/env python
#
# Copyright 2012-2015 eNovance <licensing@enovance.com>
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
import random
import subprocess
import time

from oslo_utils import fileutils
import requests
import six

from aodh.tests import base


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
                                                    prefix='aodh',
                                                    suffix='.conf')

    def tearDown(self):
        super(BinTestCase, self).tearDown()
        os.remove(self.tempfile)

    def test_dbsync_run(self):
        subp = subprocess.Popen(['aodh-dbsync',
                                 "--config-file=%s" % self.tempfile])
        self.assertEqual(0, subp.wait())

    def test_run_expirer_ttl_disabled(self):
        subp = subprocess.Popen(['aodh-expirer',
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
                                                    prefix='aodh',
                                                    suffix='.conf')
        subp = subprocess.Popen(['aodh-expirer',
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
                   "paste.app_factory = aodh.api.app:app_factory\n")
        if six.PY3:
            content = content.encode('utf-8')
        self.paste = fileutils.write_to_tempfile(content=content,
                                                 prefix='api_paste',
                                                 suffix='.ini')

        # create aodh.conf file
        self.api_port = random.randint(10000, 11000)
        self.pipeline_cfg_file = self.path_get('etc/aodh/pipeline.yaml')
        self.policy_file = self.path_get('aodh/tests/open-policy.json')

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
                r = requests.get(url)
            except requests.exceptions.ConnectionError:
                time.sleep(.5)
                self.assertIsNone(self.subp.poll())
            else:
                return r
        return None

    def run_api(self, content, err_pipe=None):
        if six.PY3:
            content = content.encode('utf-8')

        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='aodh',
                                                    suffix='.conf')
        if err_pipe:
            return subprocess.Popen(['aodh-api',
                                    "--config-file=%s" % self.tempfile],
                                    stderr=subprocess.PIPE)
        else:
            return subprocess.Popen(['aodh-api',
                                    "--config-file=%s" % self.tempfile])

    def test_v2(self):
        content = ("[DEFAULT]\n"
                   "rpc_backend=fake\n"
                   "auth_strategy=noauth\n"
                   "debug=true\n"
                   "pipeline_cfg_file={0}\n"
                   "[api]\n"
                   "paste_config={2}\n"
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

        response = self.get_response('v2/alarms')
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())


class BinEvaluatorTestCase(base.BaseTestCase):
    def setUp(self):
        super(BinEvaluatorTestCase, self).setUp()
        content = ("[DEFAULT]\n"
                   "rpc_backend=fake\n"
                   "[database]\n"
                   "connection=log://localhost\n")
        if six.PY3:
            content = content.encode('utf-8')
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='aodh',
                                                    suffix='.conf')
        self.subp = None

    def tearDown(self):
        super(BinEvaluatorTestCase, self).tearDown()
        if self.subp:
            self.subp.kill()
        os.remove(self.tempfile)

    def test_starting_evaluator(self):
        self.subp = subprocess.Popen(['aodh-evaluator',
                                      "--config-file=%s" % self.tempfile],
                                     stderr=subprocess.PIPE)
        self.assertIsNone(self.subp.poll())


class BinNotifierTestCase(BinEvaluatorTestCase):
    def test_starting_notifier(self):
        self.subp = subprocess.Popen(['aodh-notifier',
                                      "--config-file=%s" % self.tempfile],
                                     stderr=subprocess.PIPE)
        self.assertIsNone(self.subp.poll())
