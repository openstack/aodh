#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 IBM Corp.
# Copyright 2013 eNovance <licensing@enovance.com>
# Copyright Ericsson AB 2013. All rights reserved
# Copyright 2014 Hewlett-Packard Company
# Copyright 2015 Huawei Technologies Co., Ltd.
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

import datetime
import itertools
import json

import croniter
from oslo_config import cfg
from oslo_log import log
from oslo_utils import netutils
from oslo_utils import timeutils
from oslo_utils import uuidutils
import pecan
from pecan import rest
import pytz
import six
from six.moves.urllib import parse as urlparse
from stevedore import extension
import wsme
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

import aodh
from aodh.api.controllers.v2 import base
from aodh.api.controllers.v2 import utils as v2_utils
from aodh.api import rbac
from aodh.i18n import _
from aodh import keystone_client
from aodh import messaging
from aodh import notifier
from aodh.storage import models

LOG = log.getLogger(__name__)


ALARM_API_OPTS = [
    cfg.IntOpt('user_alarm_quota',
               deprecated_group='DEFAULT',
               help='Maximum number of alarms defined for a user.'
               ),
    cfg.IntOpt('project_alarm_quota',
               deprecated_group='DEFAULT',
               help='Maximum number of alarms defined for a project.'
               ),
    cfg.IntOpt('alarm_max_actions',
               default=-1,
               deprecated_group='DEFAULT',
               help='Maximum count of actions for each state of an alarm, '
                    'non-positive number means no limit.'),
]

state_kind = ["ok", "alarm", "insufficient data"]
state_kind_enum = wtypes.Enum(str, *state_kind)
severity_kind = ["low", "moderate", "critical"]
severity_kind_enum = wtypes.Enum(str, *severity_kind)

ALARM_REASON_DEFAULT = "Not evaluated yet"
ALARM_REASON_MANUAL = "Manually set via API"


class OverQuota(base.ClientSideError):
    def __init__(self, data):
        d = {
            'u': data.user_id,
            'p': data.project_id
        }
        super(OverQuota, self).__init__(
            _("Alarm quota exceeded for user %(u)s on project %(p)s") % d,
            status_code=403)


def is_over_quota(conn, project_id, user_id):
    """Returns False if an alarm is within the set quotas, True otherwise.

    :param conn: a backend connection object
    :param project_id: the ID of the project setting the alarm
    :param user_id: the ID of the user setting the alarm
    """

    over_quota = False

    # Start by checking for user quota
    user_alarm_quota = pecan.request.cfg.api.user_alarm_quota
    if user_alarm_quota is not None:
        user_alarms = list(conn.get_alarms(user=user_id))
        over_quota = len(user_alarms) >= user_alarm_quota

    # If the user quota isn't reached, we check for the project quota
    if not over_quota:
        project_alarm_quota = pecan.request.cfg.api.project_alarm_quota
        if project_alarm_quota is not None:
            project_alarms = list(conn.get_alarms(project=project_id))
            over_quota = len(project_alarms) >= project_alarm_quota

    return over_quota


class CronType(wtypes.UserType):
    """A user type that represents a cron format."""
    basetype = six.string_types
    name = 'cron'

    @staticmethod
    def validate(value):
        # raises ValueError if invalid
        croniter.croniter(value)
        return value


class AlarmTimeConstraint(base.Base):
    """Representation of a time constraint on an alarm."""

    name = wsme.wsattr(wtypes.text, mandatory=True)
    "The name of the constraint"

    _description = None  # provide a default

    def get_description(self):
        if not self._description:
            return ('Time constraint at %s lasting for %s seconds'
                    % (self.start, self.duration))
        return self._description

    def set_description(self, value):
        self._description = value

    description = wsme.wsproperty(wtypes.text, get_description,
                                  set_description)
    "The description of the constraint"

    start = wsme.wsattr(CronType(), mandatory=True)
    "Start point of the time constraint, in cron format"

    duration = wsme.wsattr(wtypes.IntegerType(minimum=0), mandatory=True)
    "How long the constraint should last, in seconds"

    timezone = wsme.wsattr(wtypes.text, default="")
    "Timezone of the constraint"

    def as_dict(self):
        return self.as_dict_from_keys(['name', 'description', 'start',
                                       'duration', 'timezone'])

    @staticmethod
    def validate(tc):
        if tc.timezone:
            try:
                pytz.timezone(tc.timezone)
            except Exception:
                raise base.ClientSideError(_("Timezone %s is not valid")
                                           % tc.timezone)
        return tc

    @classmethod
    def sample(cls):
        return cls(name='SampleConstraint',
                   description='nightly build every night at 23h for 3 hours',
                   start='0 23 * * *',
                   duration=10800,
                   timezone='Europe/Ljubljana')


ALARMS_RULES = extension.ExtensionManager("aodh.alarm.rule")
LOG.debug("alarm rules plugin loaded: %s" % ",".join(ALARMS_RULES.names()))

ACTIONS_SCHEMA = extension.ExtensionManager(
    notifier.AlarmNotifierService.NOTIFIER_EXTENSIONS_NAMESPACE).names()


class Alarm(base.Base):
    """Representation of an alarm."""

    alarm_id = wtypes.text
    "The UUID of the alarm"

    name = wsme.wsattr(wtypes.text, mandatory=True)
    "The name for the alarm"

    _description = None  # provide a default

    def get_description(self):
        rule = getattr(self, '%s_rule' % self.type, None)
        if not self._description:
            if hasattr(rule, 'default_description'):
                return six.text_type(rule.default_description)
            return "%s alarm rule" % self.type
        return self._description

    def set_description(self, value):
        self._description = value

    description = wsme.wsproperty(wtypes.text, get_description,
                                  set_description)
    "The description of the alarm"

    enabled = wsme.wsattr(bool, default=True)
    "This alarm is enabled?"

    ok_actions = wsme.wsattr([wtypes.text], default=[])
    "The actions to do when alarm state change to ok"

    alarm_actions = wsme.wsattr([wtypes.text], default=[])
    "The actions to do when alarm state change to alarm"

    insufficient_data_actions = wsme.wsattr([wtypes.text], default=[])
    "The actions to do when alarm state change to insufficient data"

    repeat_actions = wsme.wsattr(bool, default=False)
    "The actions should be re-triggered on each evaluation cycle"

    type = base.AdvEnum('type', str, *ALARMS_RULES.names(),
                        mandatory=True)
    "Explicit type specifier to select which rule to follow below."

    time_constraints = wtypes.wsattr([AlarmTimeConstraint], default=[])
    """Describe time constraints for the alarm"""

    # These settings are ignored in the PUT or POST operations, but are
    # filled in for GET
    project_id = wtypes.text
    "The ID of the project or tenant that owns the alarm"

    user_id = wtypes.text
    "The ID of the user who created the alarm"

    timestamp = datetime.datetime
    "The date of the last alarm definition update"

    state = base.AdvEnum('state', str, *state_kind,
                         default='insufficient data')
    "The state offset the alarm"

    state_timestamp = datetime.datetime
    "The date of the last alarm state changed"

    state_reason = wsme.wsattr(wtypes.text, default=ALARM_REASON_DEFAULT)
    "The reason of the current state"

    severity = base.AdvEnum('severity', str, *severity_kind,
                            default='low')
    "The severity of the alarm"

    def __init__(self, rule=None, time_constraints=None, **kwargs):
        super(Alarm, self).__init__(**kwargs)

        if rule:
            setattr(self, '%s_rule' % self.type,
                    ALARMS_RULES[self.type].plugin(**rule))

        if time_constraints:
            self.time_constraints = [AlarmTimeConstraint(**tc)
                                     for tc in time_constraints]

    @classmethod
    def from_db_model_scrubbed(cls, m):
        # Return an Alarm from a DB model with trust IDs scrubbed from actions
        data = m.as_dict()

        for field in ('ok_actions', 'alarm_actions',
                      'insufficient_data_actions'):
            if data.get(field) is not None:
                data[field] = [cls._scrub_action_url(action)
                               for action in data[field]]

        return cls(**data)

    @staticmethod
    def validate(alarm):
        Alarm.check_rule(alarm)
        Alarm.check_alarm_actions(alarm)

        ALARMS_RULES[alarm.type].plugin.validate_alarm(alarm)

        if alarm.time_constraints:
            tc_names = [tc.name for tc in alarm.time_constraints]
            if len(tc_names) > len(set(tc_names)):
                error = _("Time constraint names must be "
                          "unique for a given alarm.")
                raise base.ClientSideError(error)

        return alarm

    @staticmethod
    def check_rule(alarm):
        rule = '%s_rule' % alarm.type
        if getattr(alarm, rule) in (wtypes.Unset, None):
            error = _("%(rule)s must be set for %(type)s"
                      " type alarm") % {"rule": rule, "type": alarm.type}
            raise base.ClientSideError(error)

        rule_set = None
        for ext in ALARMS_RULES:
            name = "%s_rule" % ext.name
            if getattr(alarm, name):
                if rule_set is None:
                    rule_set = name
                else:
                    error = _("%(rule1)s and %(rule2)s cannot be set at the "
                              "same time") % {'rule1': rule_set, 'rule2': name}
                    raise base.ClientSideError(error)

    @staticmethod
    def check_alarm_actions(alarm):
        max_actions = pecan.request.cfg.api.alarm_max_actions
        for state in state_kind:
            actions_name = state.replace(" ", "_") + '_actions'
            actions = getattr(alarm, actions_name)
            if not actions:
                continue

            action_set = set(actions)
            if len(actions) != len(action_set):
                LOG.info('duplicate actions are found: %s, '
                         'remove duplicate ones', actions)
                actions = list(action_set)
                setattr(alarm, actions_name, actions)

            if 0 < max_actions < len(actions):
                error = _('%(name)s count exceeds maximum value '
                          '%(maximum)d') % {"name": actions_name,
                                            "maximum": max_actions}
                raise base.ClientSideError(error)

            limited = rbac.get_limited_to_project(pecan.request.headers,
                                                  pecan.request.enforcer)

            for action in actions:
                try:
                    url = netutils.urlsplit(action)
                except Exception:
                    error = _("Unable to parse action %s") % action
                    raise base.ClientSideError(error)
                if url.scheme not in ACTIONS_SCHEMA:
                    error = _("Unsupported action %s") % action
                    raise base.ClientSideError(error)
                if limited and url.scheme in ('log', 'test'):
                    error = _('You are not authorized to create '
                              'action: %s') % action
                    raise base.ClientSideError(error, status_code=401)

    @classmethod
    def sample(cls):
        return cls(alarm_id=None,
                   name="SwiftObjectAlarm",
                   description="An alarm",
                   type='gnocchi_aggregation_by_metrics_threshold',
                   time_constraints=[AlarmTimeConstraint.sample().as_dict()],
                   user_id="c96c887c216949acbdfbd8b494863567",
                   project_id="c96c887c216949acbdfbd8b494863567",
                   enabled=True,
                   timestamp=datetime.datetime(2015, 1, 1, 12, 0, 0, 0),
                   state="ok",
                   severity="moderate",
                   state_reason="threshold over 90%",
                   state_timestamp=datetime.datetime(2015, 1, 1, 12, 0, 0, 0),
                   ok_actions=["http://site:8000/ok"],
                   alarm_actions=["http://site:8000/alarm"],
                   insufficient_data_actions=["http://site:8000/nodata"],
                   repeat_actions=False,
                   )

    def as_dict(self, db_model):
        d = super(Alarm, self).as_dict(db_model)
        for k in d:
            if k.endswith('_rule'):
                del d[k]
        rule = getattr(self, "%s_rule" % self.type)
        d['rule'] = rule if isinstance(rule, dict) else rule.as_dict()
        if self.time_constraints:
            d['time_constraints'] = [tc.as_dict()
                                     for tc in self.time_constraints]
        return d

    @staticmethod
    def _is_trust_url(url):
        return url.scheme.startswith('trust+')

    @staticmethod
    def _scrub_action_url(action):
        """Remove trust ID from a URL."""
        url = netutils.urlsplit(action)
        if Alarm._is_trust_url(url):
            netloc = url.netloc.rsplit('@', 1)[-1]
            url = urlparse.SplitResult(url.scheme, netloc,
                                       url.path, url.query,
                                       url.fragment)
        return url.geturl()

    def _get_existing_trust_ids(self):
        for action in itertools.chain(self.ok_actions or [],
                                      self.alarm_actions or [],
                                      self.insufficient_data_actions or []):
            url = netutils.urlsplit(action)
            if self._is_trust_url(url):
                trust_id = url.username
                if trust_id and url.password == 'delete':
                    yield trust_id

    def update_actions(self, old_alarm=None):
        trustor_user_id = pecan.request.headers.get('X-User-Id')
        trustor_project_id = pecan.request.headers.get('X-Project-Id')
        roles = pecan.request.headers.get('X-Roles', '')
        if roles:
            roles = roles.split(',')
        else:
            roles = []
        auth_plugin = pecan.request.environ.get('keystone.token_auth')

        if old_alarm:
            prev_trust_ids = set(old_alarm._get_existing_trust_ids())
        else:
            prev_trust_ids = set()
        trust_id = prev_trust_ids.pop() if prev_trust_ids else None
        trust_id_used = False

        for actions in (self.ok_actions, self.alarm_actions,
                        self.insufficient_data_actions):
            if actions is not None:
                for index, action in enumerate(actions[:]):
                    url = netutils.urlsplit(action)
                    if self._is_trust_url(url):
                        if '@' in url.netloc:
                            errmsg = _("trust URL cannot contain a trust ID.")
                            raise base.ClientSideError(errmsg)
                        if trust_id is None:
                            # We have a trust action without a trust ID,
                            # create it
                            trust_id = keystone_client.create_trust_id(
                                pecan.request.cfg,
                                trustor_user_id, trustor_project_id, roles,
                                auth_plugin)
                        if trust_id_used:
                            pw = ''
                        else:
                            pw = ':delete'
                            trust_id_used = True
                        netloc = '%s%s@%s' % (trust_id, pw, url.netloc)
                        url = urlparse.SplitResult(url.scheme, netloc,
                                                   url.path, url.query,
                                                   url.fragment)
                        actions[index] = url.geturl()
        if trust_id is not None and not trust_id_used:
            prev_trust_ids.add(trust_id)
        for old_trust_id in prev_trust_ids:
            keystone_client.delete_trust_id(old_trust_id, auth_plugin)

    def delete_actions(self):
        auth_plugin = pecan.request.environ.get('keystone.token_auth')
        for trust_id in self._get_existing_trust_ids():
            keystone_client.delete_trust_id(trust_id, auth_plugin)


Alarm.add_attributes(**{"%s_rule" % ext.name: ext.plugin
                        for ext in ALARMS_RULES})


class AlarmChange(base.Base):
    """Representation of an event in an alarm's history."""

    event_id = wtypes.text
    "The UUID of the change event"

    alarm_id = wtypes.text
    "The UUID of the alarm"

    type = wtypes.Enum(str,
                       'creation',
                       'rule change',
                       'state transition',
                       'deletion')
    "The type of change"

    detail = wtypes.text
    "JSON fragment describing change"

    project_id = wtypes.text
    "The project ID of the initiating identity"

    user_id = wtypes.text
    "The user ID of the initiating identity"

    on_behalf_of = wtypes.text
    "The tenant on behalf of which the change is being made"

    timestamp = datetime.datetime
    "The time/date of the alarm change"

    @classmethod
    def sample(cls):
        return cls(alarm_id='e8ff32f772a44a478182c3fe1f7cad6a',
                   type='rule change',
                   detail='{"threshold": 42.0, "evaluation_periods": 4}',
                   user_id="3e5d11fda79448ac99ccefb20be187ca",
                   project_id="b6f16144010811e387e4de429e99ee8c",
                   on_behalf_of="92159030020611e3b26dde429e99ee8c",
                   timestamp=datetime.datetime(2015, 1, 1, 12, 0, 0, 0),
                   )


def _send_notification(event, payload):
    notification = event.replace(" ", "_")
    notification = "alarm.%s" % notification
    transport = messaging.get_transport(pecan.request.cfg)
    notifier = messaging.get_notifier(transport, publisher_id="aodh.api")
    # FIXME(sileht): perhaps we need to copy some infos from the
    # pecan request headers like nova does
    notifier.info({}, notification, payload)


def stringify_timestamps(data):
    """Stringify any datetimes in given dict."""
    return dict((k, v.isoformat()
                 if isinstance(v, datetime.datetime) else v)
                for (k, v) in six.iteritems(data))


class AlarmController(rest.RestController):
    """Manages operations on a single alarm."""

    _custom_actions = {
        'history': ['GET'],
        'state': ['PUT', 'GET'],
    }

    def __init__(self, alarm_id):
        pecan.request.context['alarm_id'] = alarm_id
        self._id = alarm_id

    def _enforce_rbac(self, rbac_directive):
        # TODO(sileht): We should be able to relax this since we
        # pass the alarm object to the enforcer.
        auth_project = rbac.get_limited_to_project(pecan.request.headers,
                                                   pecan.request.enforcer)
        alarms = list(pecan.request.storage.get_alarms(alarm_id=self._id,
                                                       project=auth_project))
        if not alarms:
            raise base.AlarmNotFound(alarm=self._id, auth_project=auth_project)
        alarm = alarms[0]
        target = {'user_id': alarm.user_id,
                  'project_id': alarm.project_id}
        rbac.enforce(rbac_directive, pecan.request.headers,
                     pecan.request.enforcer, target)
        return alarm

    def _record_change(self, data, now, on_behalf_of=None, type=None):
        if not pecan.request.cfg.record_history:
            return
        if not data:
            return
        type = type or models.AlarmChange.RULE_CHANGE
        scrubbed_data = stringify_timestamps(data)
        detail = json.dumps(scrubbed_data)
        user_id = pecan.request.headers.get('X-User-Id')
        project_id = pecan.request.headers.get('X-Project-Id')
        on_behalf_of = on_behalf_of or project_id
        severity = scrubbed_data.get('severity')
        payload = dict(event_id=uuidutils.generate_uuid(),
                       alarm_id=self._id,
                       type=type,
                       detail=detail,
                       user_id=user_id,
                       project_id=project_id,
                       on_behalf_of=on_behalf_of,
                       timestamp=now,
                       severity=severity)

        try:
            pecan.request.storage.record_alarm_change(payload)
        except aodh.NotImplementedError:
            pass

        # Revert to the pre-json'ed details ...
        payload['detail'] = scrubbed_data
        _send_notification(type, payload)

    def _record_delete(self, alarm):
        if not alarm:
            return
        type = models.AlarmChange.DELETION
        detail = {'state': alarm.state}
        user_id = pecan.request.headers.get('X-User-Id')
        project_id = pecan.request.headers.get('X-Project-Id')
        payload = dict(event_id=uuidutils.generate_uuid(),
                       alarm_id=self._id,
                       type=type,
                       detail=detail,
                       user_id=user_id,
                       project_id=project_id,
                       on_behalf_of=project_id,
                       timestamp=timeutils.utcnow(),
                       severity=alarm.severity)

        pecan.request.storage.delete_alarm(alarm.alarm_id)
        _send_notification(type, payload)

    @wsme_pecan.wsexpose(Alarm)
    def get(self):
        """Return this alarm."""
        return Alarm.from_db_model_scrubbed(self._enforce_rbac('get_alarm'))

    @wsme_pecan.wsexpose(Alarm, body=Alarm)
    def put(self, data):
        """Modify this alarm.

        :param data: an alarm within the request body.
        """

        # Ensure alarm exists
        alarm_in = self._enforce_rbac('change_alarm')

        now = timeutils.utcnow()

        data.alarm_id = self._id

        user, project = rbac.get_limited_to(pecan.request.headers,
                                            pecan.request.enforcer)
        if user:
            data.user_id = user
        elif data.user_id == wtypes.Unset:
            data.user_id = alarm_in.user_id
        if project:
            data.project_id = project
        elif data.project_id == wtypes.Unset:
            data.project_id = alarm_in.project_id
        data.timestamp = now
        if alarm_in.state != data.state:
            data.state_timestamp = now
            data.state_reason = ALARM_REASON_MANUAL
        else:
            data.state_timestamp = alarm_in.state_timestamp
            data.state_reason = alarm_in.state_reason

        ALARMS_RULES[data.type].plugin.update_hook(data)

        old_data = Alarm.from_db_model(alarm_in)
        old_alarm = old_data.as_dict(models.Alarm)
        data.update_actions(old_data)
        updated_alarm = data.as_dict(models.Alarm)
        try:
            alarm_in = models.Alarm(**updated_alarm)
        except Exception:
            LOG.exception("Error while putting alarm: %s", updated_alarm)
            raise base.ClientSideError(_("Alarm incorrect"))

        alarm = pecan.request.storage.update_alarm(alarm_in)

        change = dict((k, v) for k, v in updated_alarm.items()
                      if v != old_alarm[k] and k not in
                      ['timestamp', 'state_timestamp'])
        self._record_change(change, now, on_behalf_of=alarm.project_id)
        return Alarm.from_db_model_scrubbed(alarm)

    @wsme_pecan.wsexpose(None, status_code=204)
    def delete(self):
        """Delete this alarm."""

        # ensure alarm exists before deleting
        alarm = self._enforce_rbac('delete_alarm')
        self._record_delete(alarm)
        alarm_object = Alarm.from_db_model(alarm)
        alarm_object.delete_actions()

    @wsme_pecan.wsexpose([AlarmChange], [base.Query], [str], int, str)
    def history(self, q=None, sort=None, limit=None, marker=None):
        """Assembles the alarm history requested.

        :param q: Filter rules for the changes to be described.
        :param sort: A list of pairs of sort key and sort dir.
        :param limit: The maximum number of items to be return.
        :param marker: The pagination query marker.
        """

        # Ensure alarm exists
        self._enforce_rbac('alarm_history')

        q = q or []
        # allow history to be returned for deleted alarms, but scope changes
        # returned to those carried out on behalf of the auth'd tenant, to
        # avoid inappropriate cross-tenant visibility of alarm history
        auth_project = rbac.get_limited_to_project(pecan.request.headers,
                                                   pecan.request.enforcer)
        conn = pecan.request.storage
        kwargs = v2_utils.query_to_kwargs(
            q, conn.get_alarm_changes, ['on_behalf_of', 'alarm_id'])
        if sort or limit or marker:
            kwargs['pagination'] = v2_utils.get_pagination_options(
                sort, limit, marker, models.AlarmChange)
        return [AlarmChange.from_db_model(ac)
                for ac in conn.get_alarm_changes(self._id, auth_project,
                                                 **kwargs)]

    @wsme.validate(state_kind_enum)
    @wsme_pecan.wsexpose(state_kind_enum, body=state_kind_enum)
    def put_state(self, state):
        """Set the state of this alarm.

        :param state: an alarm state within the request body.
        """

        alarm = self._enforce_rbac('change_alarm_state')

        # note(sileht): body are not validated by wsme
        # Workaround for https://bugs.launchpad.net/wsme/+bug/1227229
        if state not in state_kind:
            raise base.ClientSideError(_("state invalid"))
        now = timeutils.utcnow()
        alarm.state = state
        alarm.state_timestamp = now
        alarm.state_reason = ALARM_REASON_MANUAL
        alarm = pecan.request.storage.update_alarm(alarm)
        change = {'state': alarm.state,
                  'state_reason': alarm.state_reason}
        self._record_change(change, now, on_behalf_of=alarm.project_id,
                            type=models.AlarmChange.STATE_TRANSITION)
        return alarm.state

    @wsme_pecan.wsexpose(state_kind_enum)
    def get_state(self):
        """Get the state of this alarm."""
        return self._enforce_rbac('get_alarm_state').state


class AlarmsController(rest.RestController):
    """Manages operations on the alarms collection."""

    @pecan.expose()
    def _lookup(self, alarm_id, *remainder):
        return AlarmController(alarm_id), remainder

    @staticmethod
    def _record_creation(conn, data, alarm_id, now):
        if not pecan.request.cfg.record_history:
            return
        type = models.AlarmChange.CREATION
        scrubbed_data = stringify_timestamps(data)
        detail = json.dumps(scrubbed_data)
        user_id = pecan.request.headers.get('X-User-Id')
        project_id = pecan.request.headers.get('X-Project-Id')
        severity = scrubbed_data.get('severity')
        payload = dict(event_id=uuidutils.generate_uuid(),
                       alarm_id=alarm_id,
                       type=type,
                       detail=detail,
                       user_id=user_id,
                       project_id=project_id,
                       on_behalf_of=project_id,
                       timestamp=now,
                       severity=severity)

        try:
            conn.record_alarm_change(payload)
        except aodh.NotImplementedError:
            pass

        # Revert to the pre-json'ed details ...
        payload['detail'] = scrubbed_data
        _send_notification(type, payload)

    @wsme_pecan.wsexpose(Alarm, body=Alarm, status_code=201)
    def post(self, data):
        """Create a new alarm.

        :param data: an alarm within the request body.
        """
        rbac.enforce('create_alarm', pecan.request.headers,
                     pecan.request.enforcer, {})

        conn = pecan.request.storage
        now = timeutils.utcnow()

        data.alarm_id = uuidutils.generate_uuid()
        user_limit, project_limit = rbac.get_limited_to(pecan.request.headers,
                                                        pecan.request.enforcer)

        def _set_ownership(aspect, owner_limitation, header):
            attr = '%s_id' % aspect
            requested_owner = getattr(data, attr)
            explicit_owner = requested_owner != wtypes.Unset
            caller = pecan.request.headers.get(header)
            if (owner_limitation and explicit_owner
                    and requested_owner != caller):
                raise base.ProjectNotAuthorized(requested_owner, aspect)

            actual_owner = (owner_limitation or
                            requested_owner if explicit_owner else caller)
            setattr(data, attr, actual_owner)

        _set_ownership('user', user_limit, 'X-User-Id')
        _set_ownership('project', project_limit, 'X-Project-Id')

        # Check if there's room for one more alarm
        if is_over_quota(conn, data.project_id, data.user_id):
            raise OverQuota(data)

        data.timestamp = now
        data.state_timestamp = now
        data.state_reason = ALARM_REASON_DEFAULT

        ALARMS_RULES[data.type].plugin.create_hook(data)

        change = data.as_dict(models.Alarm)

        data.update_actions()

        try:
            alarm_in = models.Alarm(**change)
        except Exception:
            LOG.exception("Error while posting alarm: %s", change)
            raise base.ClientSideError(_("Alarm incorrect"))

        alarm = conn.create_alarm(alarm_in)
        self._record_creation(conn, change, alarm.alarm_id, now)
        v2_utils.set_resp_location_hdr("/alarms/" + alarm.alarm_id)
        return Alarm.from_db_model_scrubbed(alarm)

    @wsme_pecan.wsexpose([Alarm], [base.Query], [str], int, str)
    def get_all(self, q=None, sort=None, limit=None, marker=None):
        """Return all alarms, based on the query provided.

        :param q: Filter rules for the alarms to be returned.
        :param sort: A list of pairs of sort key and sort dir.
        :param limit: The maximum number of items to be return.
        :param marker: The pagination query marker.
        """
        target = rbac.target_from_segregation_rule(
            pecan.request.headers, pecan.request.enforcer)
        rbac.enforce('get_alarms', pecan.request.headers,
                     pecan.request.enforcer, target)

        q = q or []
        # Timestamp is not supported field for Simple Alarm queries
        kwargs = v2_utils.query_to_kwargs(
            q, pecan.request.storage.get_alarms,
            allow_timestamps=False)
        if sort or limit or marker:
            kwargs['pagination'] = v2_utils.get_pagination_options(
                sort, limit, marker, models.Alarm)
        return [Alarm.from_db_model_scrubbed(m)
                for m in pecan.request.storage.get_alarms(**kwargs)]
