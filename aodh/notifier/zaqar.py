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

from aodh.i18n import _LE, _LI
from aodh import keystone_client
from aodh import notifier

LOG = log.getLogger(__name__)


SERVICE_OPTS = [
    cfg.StrOpt('zaqar',
               default='messaging',
               help='Message queue service type.'),
]

cfg.CONF.register_opts(SERVICE_OPTS, group='service_types')


class ZaqarAlarmNotifier(notifier.AlarmNotifier):
    """Zaqar notifier."""

    def __init__(self, conf):
        super(ZaqarAlarmNotifier, self).__init__(conf)
        self.conf = conf
        self._zclient = None

    def _get_endpoint(self):
        try:
            ks_client = keystone_client.get_client(self.conf)
            return ks_client.service_catalog.url_for(
                service_type=cfg.CONF.service_types.zaqar,
                endpoint_type=self.conf.service_credentials.os_endpoint_type)
        except Exception:
            LOG.error(_LE("Aodh was configured to use zaqar:// action,"
                          " but Zaqar endpoint could not be found in Keystone"
                          " service catalog."))

    def get_zaqar_client(self):
        conf = self.conf.service_credentials
        params = {
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
        try:
            from zaqarclient.queues import client as zaqar_client
            return zaqar_client.Client(self._get_endpoint(),
                                       version=1.1, conf=params)
        except Exception:
            LOG.error(_LE("Failed to connect to Zaqar service "),
                      exc_info=True)

    def notify(self, action, alarm_id, alarm_name, severity, previous,
               current, reason, reason_data, headers=None):
        LOG.info(_LI(
            "Notifying alarm %(alarm_name)s %(alarm_id)s of %(severity)s "
            "priority from %(previous)s to %(current)s with action %(action)s"
            " because %(reason)s.") % ({'alarm_name': alarm_name,
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
        self.notify_zaqar(action, message)

    @property
    def client(self):
        if self._zclient is None:
            self._zclient = self.get_zaqar_client()
        return self._zclient

    def notify_zaqar(self, action, message):
        queue_info = urlparse.parse_qs(action.query)

        try:
            # queue_name is a combination of <alarm-id>-<topic>
            queue_name = "%s-%s" % (message['body']['alarm_id'],
                                    queue_info.get('topic')[-1])
            # create a queue in zaqar
            queue = self.client.queue(queue_name, force_create=True)
            subscriber_list = queue_info.get('subscriber', [])
            ttl = queue_info.get('ttl', [3600])[-1]
            for subscriber in subscriber_list:
                # add subscriber to the zaqar queue
                subscription_data = dict(subscriber=subscriber,
                                         ttl=ttl)
                self.client.subscription(queue_name,
                                         **subscription_data)
            # post the message to the queue
            queue.post(message)
        except IndexError:
            LOG.error(_LE("Required topic query option missing in action %s")
                      % action)
        except Exception:
            LOG.error(_LE("Unknown error occurred; Failed to post message to"
                          " Zaqar queue"),
                      exc_info=True)
