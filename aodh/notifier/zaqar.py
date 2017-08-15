#
# Copyright 2015 Red Hat, Inc.
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

"""Zaqar alarm notifier."""

from oslo_config import cfg
from oslo_log import log
import six.moves.urllib.parse as urlparse

from aodh import keystone_client
from aodh import notifier
from aodh.notifier import trust

LOG = log.getLogger(__name__)


SERVICE_OPTS = [
    cfg.StrOpt('zaqar',
               default='messaging',
               help='Message queue service type.'),
]


class ZaqarAlarmNotifier(notifier.AlarmNotifier):
    """Zaqar notifier.

    This notifier posts alarm notifications either to a Zaqar subscription or
    to an existing Zaqar queue with a pre-signed URL.

    To create a new subscription in the service project, use a notification URL
    of the form::

        zaqar://?topic=example&subscriber=mailto%3A//test%40example.com&ttl=3600

    Multiple subscribers are allowed. ``ttl`` is the time to live of the
    subscription. The queue will be created automatically, in the service
    project, with a name based on the topic and the alarm ID.

    To use a pre-signed URL for an existing queue, use a notification URL with
    the scheme ``zaqar://`` and the pre-signing data from Zaqar in the query
    string::

        zaqar://?queue_name=example&project_id=foo&
                 paths=/messages&methods=POST&expires=1970-01-01T00:00Z&
                 signature=abcdefg
    """

    def __init__(self, conf):
        super(ZaqarAlarmNotifier, self).__init__(conf)
        self.conf = conf
        self._zclient = None
        self._zendpoint = None

    def _get_endpoint(self):
        if self._zendpoint is None:
            try:
                ks_client = keystone_client.get_client(self.conf)
                z_srv = ks_client.services.find(
                    type=self.conf.service_types.zaqar)
                endpoint_type = self.conf.service_credentials.interface
                z_endpoint = ks_client.endpoints.find(service_id=z_srv.id,
                                                      interface=endpoint_type)
                self._zendpoint = z_endpoint.url
            except Exception:
                LOG.error("Aodh was configured to use zaqar:// action,"
                          " but Zaqar endpoint could not be found in"
                          " Keystone service catalog.")
        return self._zendpoint

    def _get_client_conf(self):
        conf = self.conf.service_credentials
        return {
            'auth_opts': {
                'backend': 'keystone',
                'options': {
                    'os_username': conf.os_username,
                    'os_password': conf.os_password,
                    'os_project_name': conf.os_tenant_name,
                    'os_auth_url': conf.os_auth_url,
                    'insecure': ''
                }
            }
        }

    def get_zaqar_client(self, conf):
        try:
            from zaqarclient.queues import client as zaqar_client
            return zaqar_client.Client(self._get_endpoint(),
                                       version=2, conf=conf)
        except Exception:
            LOG.error("Failed to connect to Zaqar service ",
                      exc_info=True)

    def _get_presigned_client_conf(self, queue_info):
        queue_name = queue_info.get('queue_name', [''])[0]
        if not queue_name:
            return None, None

        signature = queue_info.get('signature', [''])[0]
        expires = queue_info.get('expires', [''])[0]
        paths = queue_info.get('paths', [''])[0].split(',')
        methods = queue_info.get('methods', [''])[0].split(',')
        project_id = queue_info.get('project_id', [''])[0]
        conf = {
            'auth_opts': {
                'backend': 'signed-url',
                'options': {
                    'signature': signature,
                    'expires': expires,
                    'methods': methods,
                    'paths': paths,
                    'os_project_id': project_id
                }
            }
        }
        return conf, queue_name

    def notify(self, action, alarm_id, alarm_name, severity, previous,
               current, reason, reason_data, headers=None):
        LOG.info(
            "Notifying alarm %(alarm_name)s %(alarm_id)s of %(severity)s "
            "priority from %(previous)s to %(current)s with action %(action)s"
            " because %(reason)s." % ({'alarm_name': alarm_name,
                                       'alarm_id': alarm_id,
                                       'severity': severity,
                                       'previous': previous,
                                       'current': current,
                                       'action': action,
                                       'reason': reason}))
        body = {'alarm_name': alarm_name, 'alarm_id': alarm_id,
                'severity': severity, 'previous': previous,
                'current': current, 'reason': reason,
                'reason_data': reason_data}
        message = dict(body=body)
        self.notify_zaqar(action, message, headers)

    @property
    def client(self):
        if self._zclient is None:
            self._zclient = self.get_zaqar_client(self._get_client_conf())
        return self._zclient

    def notify_zaqar(self, action, message, headers=None):
        queue_info = urlparse.parse_qs(action.query)
        try:
            # NOTE(flwang): Try to get build a pre-signed client if user has
            # provide enough information about that. Otherwise, go to build
            # a client with service account and queue name for this alarm.
            conf, queue_name = self._get_presigned_client_conf(queue_info)
            if conf is not None:
                zaqar_client = self.get_zaqar_client(conf)

            if conf is None or queue_name is None or zaqar_client is None:
                zaqar_client = self.client
                # queue_name is a combination of <alarm-id>-<topic>
                queue_name = "%s-%s" % (message['body']['alarm_id'],
                                        queue_info.get('topic')[-1])

            # create a queue in zaqar
            queue = zaqar_client.queue(queue_name)

            subscriber_list = queue_info.get('subscriber', [])
            ttl = int(queue_info.get('ttl', ['3600'])[-1])
            for subscriber in subscriber_list:
                # add subscriber to the zaqar queue
                subscription_data = dict(subscriber=subscriber,
                                         ttl=ttl)
                zaqar_client.subscription(queue_name, **subscription_data)
            # post the message to the queue
            queue.post(message)
        except IndexError:
            LOG.error("Required query option missing in action %s",
                      action)
        except Exception:
            LOG.error("Unknown error occurred; Failed to post message to"
                      " Zaqar queue",
                      exc_info=True)


class TrustZaqarAlarmNotifier(trust.TrustAlarmNotifierMixin,
                              ZaqarAlarmNotifier):
    """Zaqar notifier using a Keystone trust to post to user-defined queues.

    The URL must be in the form ``trust+zaqar://?queue_name=example``.
    """

    def _get_client_conf(self, auth_token):
        return {
            'auth_opts': {
                'backend': 'keystone',
                'options': {
                    'os_auth_token': auth_token,
                }
            }
        }

    def notify_zaqar(self, action, message, headers):
        queue_info = urlparse.parse_qs(action.query)
        try:
            queue_name = queue_info.get('queue_name')[-1]
        except IndexError:
            LOG.error("Required 'queue_name' query option missing in"
                      " action %s",
                      action)
            return

        try:
            conf = self._get_client_conf(headers['X-Auth-Token'])
            client = self.get_zaqar_client(conf)
            queue = client.queue(queue_name)
            queue.post(message)
        except Exception:
            LOG.error("Unknown error occurred; Failed to post message to"
                      " Zaqar queue",
                      exc_info=True)
