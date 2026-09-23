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
import json
import ssl

from oslo_config import cfg
from oslo_log import log
from oslo_utils import uuidutils
import requests
from requests.adapters import HTTPAdapter
import urllib.parse as urlparse
from urllib3.util.ssl_ import create_urllib3_context

from aodh import notifier

LOG = log.getLogger(__name__)

TLS_VERSION_CHOICES = ['1.2', '1.3']

_TLS_VERSIONS = {
    '1.2': ssl.TLSVersion.TLSv1_2,
    '1.3': ssl.TLSVersion.TLSv1_3,
}

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
    cfg.StrOpt('rest_notifier_tls_min_version',
               default=None,
               choices=TLS_VERSION_CHOICES,
               help='Minimum TLS protocol version for HTTPS REST notifier '
                    'connections. If unset, the system default applies. '
                    'Accepted values are 1.2 and 1.3, matching '
                    'keystoneauth1 tls_min_version spelling.'),
    cfg.StrOpt('rest_notifier_tls_max_version',
               default=None,
               choices=TLS_VERSION_CHOICES,
               help='Maximum TLS protocol version for HTTPS REST notifier '
                    'connections. If unset, the system default applies. '
                    'Accepted values are 1.2 and 1.3, matching '
                    'keystoneauth1 tls_max_version spelling.'),
]


class _TLSAdapter(HTTPAdapter):
    """HTTP adapter pinning TLS protocol versions on new connections."""

    def __init__(self, min_version, max_version, verify, **kwargs):
        self._min_version = min_version
        self._max_version = max_version
        # NOTE(dpawlik): requests/urllib3 set verify_mode and load the CA
        # bundle per request, but CERT_NONE on a context with check_hostname
        # enabled raises, so the context has to be built knowing whether
        # we verify.
        self._cert_reqs = None if verify else ssl.CERT_NONE
        super().__init__(**kwargs)

    def _create_ssl_context(self):
        ctx_kwargs = {}
        if self._min_version is not None:
            ctx_kwargs['ssl_minimum_version'] = self._min_version
        if self._max_version is not None:
            ctx_kwargs['ssl_maximum_version'] = self._max_version
        if self._cert_reqs is not None:
            ctx_kwargs['cert_reqs'] = self._cert_reqs
        return create_urllib3_context(**ctx_kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = self._create_ssl_context()
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        proxy_kwargs['ssl_context'] = self._create_ssl_context()
        return super().proxy_manager_for(proxy, **proxy_kwargs)


class RestAlarmNotifier(notifier.AlarmNotifier):
    """Rest alarm notifier."""

    def notify(self, action, alarm_id, alarm_name, severity, previous,
               current, reason, reason_data, headers=None):
        headers = headers or {}
        if 'x-openstack-request-id' not in headers:
            headers['x-openstack-request-id'] = b'req-' + \
                uuidutils.generate_uuid().encode('ascii')

        LOG.info(
            "Notifying alarm %(alarm_name)s %(alarm_id)s with severity"
            " %(severity)s from %(previous)s to %(current)s with action "
            "%(action)s because %(reason)s. request-id: %(request_id)s",
            {'alarm_name': alarm_name, 'alarm_id': alarm_id,
             'severity': severity, 'previous': previous,
             'current': current, 'action': action, 'reason': reason,
             'request_id': headers['x-openstack-request-id']})
        body = {'alarm_name': alarm_name, 'alarm_id': alarm_id,
                'severity': severity, 'previous': previous,
                'current': current, 'reason': reason,
                'reason_data': reason_data}
        headers['content-type'] = 'application/json'
        kwargs = {'data': json.dumps(body),
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
        adapter = self._build_adapter(
            action, kwargs.get('verify', True), max_retries)
        session.mount(action.geturl(), adapter)
        resp = session.post(action.geturl(), **kwargs)
        LOG.info('Notifying alarm <%(id)s> gets response: %(status_code)s '
                 '%(reason)s.', {'id': alarm_id,
                                 'status_code': resp.status_code,
                                 'reason': resp.reason})

    def _build_adapter(self, action, verify, max_retries):
        min_opt = self.conf.rest_notifier_tls_min_version
        max_opt = self.conf.rest_notifier_tls_max_version
        if action.scheme == 'https' and (min_opt or max_opt):
            min_version = _TLS_VERSIONS.get(min_opt)
            max_version = _TLS_VERSIONS.get(max_opt)
            if (min_version is not None and max_version is not None and
                    min_version > max_version):
                raise ValueError(
                    'rest_notifier_tls_min_version (%s) cannot be greater '
                    'than rest_notifier_tls_max_version (%s)' %
                    (min_opt, max_opt))
            return _TLSAdapter(min_version, max_version, verify,
                               max_retries=max_retries)
        return HTTPAdapter(max_retries=max_retries)
