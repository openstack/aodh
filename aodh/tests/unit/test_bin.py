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
import subprocess

from oslo_utils import fileutils
import six

from aodh.tests import base


class BinTestCase(base.BaseTestCase):
    def setUp(self):
        super(BinTestCase, self).setUp()
        content = ("[database]\n"
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
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, __ = subp.communicate()
        self.assertEqual(0, subp.poll())
        self.assertIn(b"Nothing to clean, database alarm history "
                      b"time to live is disabled", out)

    def test_run_expirer_ttl_enabled(self):
        content = ("[database]\n"
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
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, __ = subp.communicate()
        self.assertEqual(0, subp.poll())
        msg = "Dropping alarm history data with TTL 1"
        if six.PY3:
            msg = msg.encode('utf-8')
        self.assertIn(msg, out)


class BinEvaluatorTestCase(base.BaseTestCase):
    def setUp(self):
        super(BinEvaluatorTestCase, self).setUp()
        content = ("[database]\n"
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
