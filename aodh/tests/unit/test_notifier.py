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
import fixtures
import time

import mock
from oslo_config import fixture as fixture_config
import oslo_messaging
from oslo_serialization import jsonutils
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

    def test_init_host_queue(self):
        self.service = notifier.AlarmNotifierService(0, self.CONF)
        self.service.terminate()


class TestAlarmNotifier(tests_base.BaseTestCase):
    def setUp(self):
        super(TestAlarmNotifier, self).setUp()
        conf = service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf
        self.setup_messaging(self.CONF)
        self._msg_notifier = oslo_messaging.Notifier(
            self.transport, topics=['alarming'], driver='messaging',
            publisher_id='testpublisher')
        self.zaqar = FakeZaqarClient(self)
        self.useFixture(fixtures.MockPatch(
            'aodh.notifier.zaqar.ZaqarAlarmNotifier.get_zaqar_client',
            return_value=self.zaqar))
        self.service = notifier.AlarmNotifierService(0, self.CONF)
        self.addCleanup(self.service.terminate)

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
        self._msg_notifier.sample({}, 'alarm.update', data)
        time.sleep(1)
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

    @mock.patch('aodh.notifier.LOG.debug')
    def test_notify_alarm_with_batch_listener(self, logger):
        data1 = {
            'actions': ['test://'],
            'alarm_id': 'foobar',
            'alarm_name': 'testalarm',
            'severity': 'critical',
            'previous': 'OK',
            'current': 'ALARM',
            'reason': 'Everything is on fire',
            'reason_data': {'fire': 'everywhere'}
        }
        data2 = {
            'actions': ['test://'],
            'alarm_id': 'foobar2',
            'alarm_name': 'testalarm2',
            'severity': 'low',
            'previous': 'ALARM',
            'current': 'OK',
            'reason': 'Everything is fine',
            'reason_data': {'fine': 'fine'}
        }
        self.service.terminate()
        self.CONF.set_override("batch_size", 2, 'notifier')
        # Init a new service with new configuration
        self.svc = notifier.AlarmNotifierService(0, self.CONF)
        self.addCleanup(self.svc.terminate)
        self._msg_notifier.sample({}, 'alarm.update', data1)
        self._msg_notifier.sample({}, 'alarm.update', data2)
        time.sleep(1)
        notifications = self.svc.notifiers['test'].obj.notifications
        self.assertEqual(2, len(notifications))
        self.assertEqual((urlparse.urlsplit(data1['actions'][0]),
                          data1['alarm_id'],
                          data1['alarm_name'],
                          data1['severity'],
                          data1['previous'],
                          data1['current'],
                          data1['reason'],
                          data1['reason_data']),
                         notifications[0])
        self.assertEqual((urlparse.urlsplit(data2['actions'][0]),
                          data2['alarm_id'],
                          data2['alarm_name'],
                          data2['severity'],
                          data2['previous'],
                          data2['current'],
                          data2['reason'],
                          data2['reason_data']),
                         notifications[1])
        self.assertEqual(mock.call('Received %s messages in batch.', 2),
                         logger.call_args_list[0])

    @staticmethod
    def _notification(action):
        notification = {}
        notification.update(NOTIFICATION)
        notification['actions'] = [action]
        return notification

    @mock.patch('aodh.notifier.rest.LOG')
    def test_notify_alarm_rest_action_ok(self, m_log):
        action = 'http://host/action'

        with mock.patch.object(requests.Session, 'post') as poster:
            self._msg_notifier.sample({},
                                      'alarm.update',
                                      self._notification(action))
            time.sleep(1)
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY)
            args, kwargs = poster.call_args
            self.assertEqual(
                {
                    'x-openstack-request-id':
                    kwargs['headers']['x-openstack-request-id'],
                    'content-type': 'application/json'
                },
                kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))
            self.assertEqual(2, len(m_log.info.call_args_list))
            expected = mock.call('Notifying alarm <%(id)s> gets response: '
                                 '%(status_code)s %(reason)s.',
                                 mock.ANY)
            self.assertEqual(expected, m_log.info.call_args_list[1])

    def test_notify_alarm_rest_action_with_ssl_client_cert(self):
        action = 'https://host/action'
        certificate = "/etc/ssl/cert/whatever.pem"

        self.CONF.set_override("rest_notifier_certificate_file", certificate)

        with mock.patch.object(requests.Session, 'post') as poster:
            self._msg_notifier.sample({},
                                      'alarm.update',
                                      self._notification(action))
            time.sleep(1)
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY,
                                      cert=certificate, verify=True)
            args, kwargs = poster.call_args
            self.assertEqual(
                {
                    'x-openstack-request-id':
                    kwargs['headers']['x-openstack-request-id'],
                    'content-type': 'application/json'
                },
                kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_client_cert_and_key(self):
        action = 'https://host/action'
        certificate = "/etc/ssl/cert/whatever.pem"
        key = "/etc/ssl/cert/whatever.key"

        self.CONF.set_override("rest_notifier_certificate_file", certificate)
        self.CONF.set_override("rest_notifier_certificate_key", key)

        with mock.patch.object(requests.Session, 'post') as poster:
            self._msg_notifier.sample({},
                                      'alarm.update',
                                      self._notification(action))
            time.sleep(1)
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY,
                                      cert=(certificate, key), verify=True)
            args, kwargs = poster.call_args
            self.assertEqual(
                {
                    'x-openstack-request-id':
                    kwargs['headers']['x-openstack-request-id'],
                    'content-type': 'application/json'},
                kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_verify_disable_by_cfg(self):
        action = 'https://host/action'

        self.CONF.set_override("rest_notifier_ssl_verify", False)

        with mock.patch.object(requests.Session, 'post') as poster:
            self._msg_notifier.sample({},
                                      'alarm.update',
                                      self._notification(action))
            time.sleep(1)
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY,
                                      verify=False)
            args, kwargs = poster.call_args
            self.assertEqual(
                {
                    'x-openstack-request-id':
                    kwargs['headers']['x-openstack-request-id'],
                    'content-type': 'application/json'
                },
                kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_server_verify_enable(self):
        action = 'https://host/action'
        ca_bundle = "/path/to/custom_cert.pem"

        self.CONF.set_override("rest_notifier_ca_bundle_certificate_path",
                               ca_bundle)

        with mock.patch.object(requests.Session, 'post') as poster:
            self._msg_notifier.sample({},
                                      'alarm.update',
                                      self._notification(action))
            time.sleep(1)
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY,
                                      verify=ca_bundle)
            args, kwargs = poster.call_args
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_verify_disable(self):
        action = 'https://host/action?aodh-alarm-ssl-verify=0'

        with mock.patch.object(requests.Session, 'post') as poster:
            self._msg_notifier.sample({},
                                      'alarm.update',
                                      self._notification(action))
            time.sleep(1)
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY,
                                      verify=False)
            args, kwargs = poster.call_args
            self.assertEqual(
                {
                    'x-openstack-request-id':
                    kwargs['headers']['x-openstack-request-id'],
                    'content-type': 'application/json'
                },
                kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_verify_enable_by_user(self):
        action = 'https://host/action?aodh-alarm-ssl-verify=1'

        self.CONF.set_override("rest_notifier_ssl_verify", False)

        with mock.patch.object(requests.Session, 'post') as poster:
            self._msg_notifier.sample({},
                                      'alarm.update',
                                      self._notification(action))
            time.sleep(1)
            poster.assert_called_with(action, data=mock.ANY,
                                      headers=mock.ANY,
                                      verify=True)
            args, kwargs = poster.call_args
            self.assertEqual(
                {
                    'x-openstack-request-id':
                    kwargs['headers']['x-openstack-request-id'],
                    'content-type': 'application/json'
                },
                kwargs['headers'])
            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    @staticmethod
    def _fake_urlsplit(*args, **kwargs):
        raise Exception("Evil urlsplit!")

    def test_notify_alarm_invalid_url(self):
        with mock.patch('oslo_utils.netutils.urlsplit',
                        self._fake_urlsplit):
            LOG = mock.MagicMock()
            with mock.patch('aodh.notifier.LOG', LOG):
                self._msg_notifier.sample(
                    {}, 'alarm.update',
                    {
                        'actions': ['no-such-action-i-am-sure'],
                        'alarm_id': 'foobar',
                        'condition': {'threshold': 42},
                    })
                time.sleep(1)
                self.assertTrue(LOG.error.called)

    def test_notify_alarm_invalid_action(self):
        LOG = mock.MagicMock()
        with mock.patch('aodh.notifier.LOG', LOG):
            self._msg_notifier.sample(
                {}, 'alarm.update',
                {
                    'actions': ['no-such-action-i-am-sure://'],
                    'alarm_id': 'foobar',
                    'condition': {'threshold': 42},
                })
            time.sleep(1)
            self.assertTrue(LOG.error.called)

    def test_notify_alarm_trust_action(self):
        action = 'trust+http://trust-1234@host/action'
        url = 'http://host/action'

        client = mock.MagicMock()
        client.session.auth.get_access.return_value.auth_token = 'token_1234'

        self.useFixture(
            fixtures.MockPatch('aodh.keystone_client.get_trusted_client',
                               lambda *args: client))

        with mock.patch.object(requests.Session, 'post') as poster:
            self._msg_notifier.sample({}, 'alarm.update',
                                      self._notification(action))
            time.sleep(1)
            poster.assert_called_with(
                url, data=mock.ANY, headers=mock.ANY)
            args, kwargs = poster.call_args
            self.assertEqual(
                {
                    'X-Auth-Token': 'token_1234',
                    'x-openstack-request-id':
                    kwargs['headers']['x-openstack-request-id'],
                    'content-type': 'application/json'
                },
                kwargs['headers'])

            self.assertEqual(DATA_JSON, jsonutils.loads(kwargs['data']))

    def test_zaqar_notifier_action(self):
        with mock.patch.object(notifier.zaqar.ZaqarAlarmNotifier,
                               '_get_client_conf') as get_conf:
            action = ('zaqar://?topic=critical'
                      '&subscriber=http://example.com/data'
                      '&subscriber=mailto:foo@example.com&ttl=7200')
            self._msg_notifier.sample({}, 'alarm.update',
                                      self._notification(action))
            time.sleep(1)
            get_conf.assert_called()
            self.assertEqual(self.zaqar,
                             self.service.notifiers['zaqar'].obj._zclient)
            self.assertEqual(2, self.zaqar.subscriptions)
            self.assertEqual(1, self.zaqar.posts)

    def test_presigned_zaqar_notifier_action(self):
        action = ('zaqar://?'
                  'subscriber=http://example.com/data&ttl=7200'
                  '&signature=mysignature&expires=2016-06-29T01:49:56'
                  '&paths=/v2/queues/beijing/messages'
                  '&methods=GET,PATCH,POST,PUT&queue_name=foobar-critical'
                  '&project_id=my_project_id')
        self._msg_notifier.sample({}, 'alarm.update',
                                  self._notification(action))
        time.sleep(1)
        self.assertEqual(1, self.zaqar.subscriptions)
        self.assertEqual(1, self.zaqar.posts)

    def test_trust_zaqar_notifier_action(self):
        client = mock.MagicMock()
        client.session.auth.get_access.return_value.auth_token = 'token_1234'

        self.useFixture(
            fixtures.MockPatch('aodh.keystone_client.get_trusted_client',
                               lambda *args: client))

        action = 'trust+zaqar://trust-1234:delete@?queue_name=foobar-critical'
        self._msg_notifier.sample({}, 'alarm.update',
                                  self._notification(action))
        time.sleep(1)
        self.assertEqual(0, self.zaqar.subscriptions)
        self.assertEqual(1, self.zaqar.posts)


class FakeZaqarClient(object):

    def __init__(self, testcase):
        self.testcase = testcase
        self.subscriptions = 0
        self.posts = 0

    def queue(self, queue_name, **kwargs):
        self.testcase.assertEqual('foobar-critical', queue_name)
        self.testcase.assertEqual({}, kwargs)
        return FakeZaqarQueue(self)

    def subscription(self, queue_name, **kwargs):
        self.testcase.assertEqual('foobar-critical', queue_name)
        subscribers = ['http://example.com/data', 'mailto:foo@example.com']
        self.testcase.assertIn(kwargs['subscriber'], subscribers)
        self.testcase.assertEqual(7200, kwargs['ttl'])
        self.subscriptions += 1


class FakeZaqarQueue(object):

    def __init__(self, client):
        self.client = client
        self.testcase = client.testcase

    def post(self, message):
        expected_message = {'body': {'alarm_name': 'testalarm',
                                     'reason_data': {'test': 'test'},
                                     'current': 'ALARM',
                                     'alarm_id': 'foobar',
                                     'reason': 'what ?',
                                     'severity': 'critical',
                                     'previous': 'OK'}}
        self.testcase.assertEqual(expected_message, message)
        self.client.posts += 1
