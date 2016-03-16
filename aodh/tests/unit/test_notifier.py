#
# Copyright 2013-2015 eNovance
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

import mock
from oslo_config import fixture as fixture_config
from oslo_serialization import jsonutils
from oslotest import mockpatch
import requests
import six.moves.urllib.parse as urlparse

from aodh import notifier
from aodh import service
from aodh.tests import base as tests_base


DATA_JSON = jsonutils.loads(
    '{"current": "ALARM", "alarm_id": "foobar", "alarm_name": "testalarm",'
    ' "severity": "critical", "reason": "what ?",'
    ' "reason_data": {"test": "test"}, "previous": "OK"}'
)
NOTIFICATION = dict(alarm_id='foobar',
                    alarm_name='testalarm',
                    severity='critical',
                    condition=dict(threshold=42),
                    reason='what ?',
                    reason_data={'test': 'test'},
                    previous='OK',
                    current='ALARM')


class TestAlarmNotifierService(tests_base.BaseTestCase):

    def setUp(self):
        super(TestAlarmNotifierService, self).setUp()
        conf = service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf
        self.setup_messaging(self.CONF)

    def test_init_host_rpc(self):
        self.CONF.set_override('ipc_protocol', 'rpc')
        self.service = notifier.AlarmNotifierService(self.CONF)
        self.service.start()
        self.service.stop()

    def test_init_host_queue(self):
        self.service = notifier.AlarmNotifierService(self.CONF)
        self.service.start()
        self.service.stop()


class TestAlarmNotifier(tests_base.BaseTestCase):

    def setUp(self):
        super(TestAlarmNotifier, self).setUp()
        conf = service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf
        self.setup_messaging(self.CONF)
        self.zaqar = FakeZaqarClient(self)
        self.useFixture(mockpatch.Patch(
            'aodh.notifier.zaqar.ZaqarAlarmNotifier.get_zaqar_client',
            return_value=self.zaqar))
        self.service = notifier.AlarmNotifierService(self.CONF)
        self.useFixture(mockpatch.Patch(
            'oslo_context.context.generate_request_id',
            self._fake_generate_request_id))

    def test_notify_alarm(self):
        data = {
            'actions': ['test://'],
            'alarm_id': 'foobar',
            'alarm_name': 'testalarm',
            'severity': 'critical',
            'previous': 'OK',
            'current': 'ALARM',
            'reason': 'Everything is on fire',
            'reason_data': {'fire': 'everywhere'}
        }
        self.service.notify_alarm({}, data)
        notifications = self.service.notifiers['test'].obj.notifications
        self.assertEqual(1, len(notifications))
        self.assertEqual((urlparse.urlsplit(data['actions'][0]),
                          data['alarm_id'],
                          data['alarm_name'],
                          data['severity'],
                          data['previous'],
                          data['current'],
                          data['reason'],
                          data['reason_data']),
                         notifications[0])

    def test_notify_alarm_no_action(self):
        self.service.notify_alarm({}, {})

    def test_notify_alarm_log_action(self):
        self.service.notify_alarm({},
                                  {
                                      'actions': ['log://'],
                                      'alarm_id': 'foobar',
                                      'condition': {'threshold': 42}})

    @staticmethod
    def _notification(action):
        notification = {}
        notification.update(NOTIFICATION)
        notification['actions'] = [action]
        return notification

    HTTP_HEADERS = {'x-openstack-request-id': 'fake_request_id',
                    'content-type': 'application/json'}

    def _fake_generate_request_id(self):
        return self.HTTP_HEADERS['x-openstack-request-id']

    def test_notify_alarm_rest_action_ok(self):
        action = 'http://host/action'

        with mock.patch.object(requests.Session, 'post') as poster:
            self.service.notify_alarm({},
                                      self._notification(action))
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY)
            args, kwargs = poster.call_args
            self.assertEqual(self.HTTP_HEADERS, kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_client_cert(self):
        action = 'https://host/action'
        certificate = "/etc/ssl/cert/whatever.pem"

        self.CONF.set_override("rest_notifier_certificate_file", certificate)

        with mock.patch.object(requests.Session, 'post') as poster:
            self.service.notify_alarm({},
                                      self._notification(action))
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY,
                                      cert=certificate, verify=True)
            args, kwargs = poster.call_args
            self.assertEqual(self.HTTP_HEADERS, kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_client_cert_and_key(self):
        action = 'https://host/action'
        certificate = "/etc/ssl/cert/whatever.pem"
        key = "/etc/ssl/cert/whatever.key"

        self.CONF.set_override("rest_notifier_certificate_file", certificate)
        self.CONF.set_override("rest_notifier_certificate_key", key)

        with mock.patch.object(requests.Session, 'post') as poster:
            self.service.notify_alarm({},
                                      self._notification(action))
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY,
                                      cert=(certificate, key), verify=True)
            args, kwargs = poster.call_args
            self.assertEqual(self.HTTP_HEADERS, kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_verify_disable_by_cfg(self):
        action = 'https://host/action'

        self.CONF.set_override("rest_notifier_ssl_verify", False)

        with mock.patch.object(requests.Session, 'post') as poster:
            self.service.notify_alarm({},
                                      self._notification(action))
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY,
                                      verify=False)
            args, kwargs = poster.call_args
            self.assertEqual(self.HTTP_HEADERS, kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_verify_disable(self):
        action = 'https://host/action?aodh-alarm-ssl-verify=0'

        with mock.patch.object(requests.Session, 'post') as poster:
            self.service.notify_alarm({},
                                      self._notification(action))
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY,
                                      verify=False)
            args, kwargs = poster.call_args
            self.assertEqual(self.HTTP_HEADERS, kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_verify_enable_by_user(self):
        action = 'https://host/action?aodh-alarm-ssl-verify=1'

        self.CONF.set_override("rest_notifier_ssl_verify", False)

        with mock.patch.object(requests.Session, 'post') as poster:
            self.service.notify_alarm({},
                                      self._notification(action))
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY,
                                      verify=True)
            args, kwargs = poster.call_args
            self.assertEqual(self.HTTP_HEADERS, kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    @staticmethod
    def _fake_urlsplit(*args, **kwargs):
        raise Exception("Evil urlsplit!")

    def test_notify_alarm_invalid_url(self):
        with mock.patch('oslo_utils.netutils.urlsplit',
                        self._fake_urlsplit):
            LOG = mock.MagicMock()
            with mock.patch('aodh.notifier.LOG', LOG):
                self.service.notify_alarm(
                    {},
                    {
                        'actions': ['no-such-action-i-am-sure'],
                        'alarm_id': 'foobar',
                        'condition': {'threshold': 42},
                    })
                self.assertTrue(LOG.error.called)

    def test_notify_alarm_invalid_action(self):
        LOG = mock.MagicMock()
        with mock.patch('aodh.notifier.LOG', LOG):
            self.service.notify_alarm(
                {},
                {
                    'actions': ['no-such-action-i-am-sure://'],
                    'alarm_id': 'foobar',
                    'condition': {'threshold': 42},
                })
            self.assertTrue(LOG.error.called)

    def test_notify_alarm_trust_action(self):
        action = 'trust+http://trust-1234@host/action'
        url = 'http://host/action'

        client = mock.MagicMock()
        client.session.auth.get_access.return_value.auth_token = 'token_1234'
        headers = {'X-Auth-Token': 'token_1234'}
        headers.update(self.HTTP_HEADERS)

        self.useFixture(mockpatch.Patch('keystoneclient.v3.client.Client',
                                        lambda **kwargs: client))

        with mock.patch.object(requests.Session, 'post') as poster:
            self.service.notify_alarm({},
                                      self._notification(action))
            headers = {'X-Auth-Token': 'token_1234'}
            headers.update(self.HTTP_HEADERS)
            poster.assert_called_with(
                url, data=mock.ANY, headers=mock.ANY)
            args, kwargs = poster.call_args
            self.assertEqual(headers, kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    def test_zaqar_notifier_action(self):
        action = 'zaqar://?topic=critical&subscriber=http://example.com/data' \
                 '&subscriber=mailto:foo@example.com&ttl=7200'
        self.service.notify_alarm({},
                                  self._notification(action))
        self.assertEqual(self.zaqar,
                         self.service.notifiers['zaqar'].obj.client)


class FakeZaqarClient(object):

    def __init__(self, testcase):
        self.client = testcase

    def queue(self, queue_name, **kwargs):
        self.client.assertEqual('foobar-critical', queue_name)
        self.client.assertEqual(dict(force_create=True), kwargs)
        return FakeZaqarQueue(self.client)

    def subscription(self, queue_name, **kwargs):
        self.client.assertEqual('foobar-critical', queue_name)
        subscribers = ['http://example.com/data', 'mailto:foo@example.com']
        self.client.assertIn(kwargs['subscriber'], subscribers)
        self.client.assertEqual('7200', kwargs['ttl'])


class FakeZaqarQueue(object):

    def __init__(self, testcase):
        self.queue = testcase

    def post(self, message):
        expected_message = {'body': {'alarm_name': 'testalarm',
                                     'reason_data': {'test': 'test'},
                                     'current': 'ALARM',
                                     'alarm_id': 'foobar',
                                     'reason': 'what ?',
                                     'severity': 'critical',
                                     'previous': 'OK'}}
        self.queue.assertEqual(expected_message, message)
