#
# Copyright 2013-2014 eNovance
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
"""Rest alarm notifier."""

from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import uuidutils
import requests
import six.moves.urllib.parse as urlparse

from aodh import notifier

LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('rest_notifier_certificate_file',
               default='',
               help='SSL Client certificate file for REST notifier.'
               ),
    cfg.StrOpt('rest_notifier_certificate_key',
               default='',
               help='SSL Client private key file for REST notifier.'
               ),
    cfg.StrOpt('rest_notifier_ca_bundle_certificate_path',
               help='SSL CA_BUNDLE certificate for REST notifier',
               ),
    cfg.BoolOpt('rest_notifier_ssl_verify',
                default=True,
                help='Whether to verify the SSL Server certificate when '
                'calling alarm action.'
                ),
    cfg.IntOpt('rest_notifier_max_retries',
               default=0,
               help='Number of retries for REST notifier',
               ),

]


class RestAlarmNotifier(notifier.AlarmNotifier):
    """Rest alarm notifier."""

    def __init__(self, conf):
        super(RestAlarmNotifier, self).__init__(conf)
        self.conf = conf

    def notify(self, action, alarm_id, alarm_name, severity, previous,
               current, reason, reason_data, headers=None):
        headers = headers or {}
        if 'x-openstack-request-id' not in headers:
            headers['x-openstack-request-id'] = b'req-' + \
                uuidutils.generate_uuid().encode('ascii')

        LOG.info(
            "Notifying alarm %(alarm_name)s %(alarm_id)s with severity"
            " %(severity)s from %(previous)s to %(current)s with action "
            "%(action)s because %(reason)s. request-id: %(request_id)s " %
            ({'alarm_name': alarm_name, 'alarm_id': alarm_id,
              'severity': severity, 'previous': previous,
              'current': current, 'action': action, 'reason': reason,
              'request_id': headers['x-openstack-request-id']}))
        body = {'alarm_name': alarm_name, 'alarm_id': alarm_id,
                'severity': severity, 'previous': previous,
                'current': current, 'reason': reason,
                'reason_data': reason_data}
        headers['content-type'] = 'application/json'
        kwargs = {'data': jsonutils.dumps(body),
                  'headers': headers}

        if action.scheme == 'https':
            default_verify = int(self.conf.rest_notifier_ssl_verify)
            options = urlparse.parse_qs(action.query)
            verify = bool(int(options.get('aodh-alarm-ssl-verify',
                                          [default_verify])[-1]))
            if verify and self.conf.rest_notifier_ca_bundle_certificate_path:
                verify = self.conf.rest_notifier_ca_bundle_certificate_path
            kwargs['verify'] = verify

            cert = self.conf.rest_notifier_certificate_file
            key = self.conf.rest_notifier_certificate_key
            if cert:
                kwargs['cert'] = (cert, key) if key else cert

        # FIXME(rhonjo): Retries are automatically done by urllib3 in requests
        # library. However, there's no interval between retries in urllib3
        # implementation. It will be better to put some interval between
        # retries (future work).
        max_retries = self.conf.rest_notifier_max_retries
        session = requests.Session()
        session.mount(action.geturl(),
                      requests.adapters.HTTPAdapter(max_retries=max_retries))
        resp = session.post(action.geturl(), **kwargs)
        LOG.info('Notifying alarm <%(id)s> gets response: %(status_code)s '
                 '%(reason)s.', {'id': alarm_id,
                                 'status_code': resp.status_code,
                                 'reason': resp.reason})
