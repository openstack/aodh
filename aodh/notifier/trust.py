#
# Copyright 2014 eNovance
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
"""Rest alarm notifier with trusted authentication."""

from six.moves.urllib import parse

from aodh import keystone_client
from aodh.notifier import rest


class TrustAlarmNotifierMixin(object):
    """Mixin class to add Keystone trust support to an AlarmNotifier.

    Provides a notify() method that interprets the trust ID and then calls
    the parent class's notify(), passing the necessary authentication data in
    the headers.
    """

    def notify(self, action, alarm_id, alarm_name, severity, previous, current,
               reason, reason_data):
        trust_id = action.username

        client = keystone_client.get_trusted_client(self.conf, trust_id)

        # Remove the fake user
        netloc = action.netloc.split("@")[1]
        # Remove the trust prefix
        scheme = action.scheme[6:]

        action = parse.SplitResult(scheme, netloc, action.path, action.query,
                                   action.fragment)

        headers = {'X-Auth-Token': keystone_client.get_auth_token(client)}
        super(TrustAlarmNotifierMixin, self).notify(
            action, alarm_id, alarm_name, severity, previous, current, reason,
            reason_data, headers)


class TrustRestAlarmNotifier(TrustAlarmNotifierMixin, rest.RestAlarmNotifier):
    """Notifier supporting keystone trust authentication.

    This alarm notifier is intended to be used to call an endpoint using
    keystone authentication. It uses the aodh service user to
    authenticate using the trust ID provided.

    The URL must be in the form ``trust+http://host/action``.
    """
