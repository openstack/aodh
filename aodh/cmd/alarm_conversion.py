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

"""A tool for converting combination alarms to composite alarms.
"""

import datetime
from six import moves
import uuid

import argparse
from oslo_log import log

from aodh.i18n import _LI, _LW
from aodh import service
from aodh import storage
from aodh.storage import models

LOG = log.getLogger(__name__)


class DependentAlarmNotFound(Exception):
    """The dependent alarm is not found."""

    def __init__(self, com_alarm_id, dependent_alarm_id):
        self.com_alarm_id = com_alarm_id
        self.dependent_alarm_id = dependent_alarm_id


class UnsupportedSubAlarmType(Exception):
    """Unsupported sub-alarm type."""

    def __init__(self, sub_alarm_id, sub_alarm_type):
        self.sub_alarm_id = sub_alarm_id
        self.sub_alarm_type = sub_alarm_type


def _generate_composite_rule(conn, combin_alarm):
    alarm_ids = combin_alarm.rule['alarm_ids']
    com_op = combin_alarm.rule['operator']
    LOG.info(_LI('Start converting combination alarm %(alarm)s, it depends on '
                 'alarms: %(alarm_ids)s'),
             {'alarm': combin_alarm.alarm_id, 'alarm_ids': str(alarm_ids)})
    threshold_rules = []
    for alarm_id in alarm_ids:
        try:
            sub_alarm = list(conn.get_alarms(alarm_id=alarm_id))[0]
        except IndexError:
            raise DependentAlarmNotFound(combin_alarm.alarm_id, alarm_id)
        if sub_alarm.type in ('threshold', 'gnocchi_resources_threshold',
                              'gnocchi_aggregation_by_metrics_threshold',
                              'gnocchi_aggregation_by_resources_threshold'):
            sub_alarm.rule.update(type=sub_alarm.type)
            threshold_rules.append(sub_alarm.rule)
        elif sub_alarm.type == 'combination':
            threshold_rules.append(_generate_composite_rule(conn, sub_alarm))
        else:
            raise UnsupportedSubAlarmType(alarm_id, sub_alarm.type)
    else:
        return {com_op: threshold_rules}


def get_parser():
    parser = argparse.ArgumentParser(
        description='for converting combination alarms to composite alarms.')
    parser.add_argument(
        '--delete-combination-alarm',
        default=False,
        type=bool,
        help='Delete the combination alarm when conversion is done.',
    )
    parser.add_argument(
        '--alarm-id',
        default=None,
        type=str,
        help='Only convert the alarm specified by this option.',
    )
    return parser


def conversion():
    confirm = moves.input("This tool is used for converting the combination "
                          "alarms to composite alarms, please type 'yes' to "
                          "confirm: ")
    if confirm != 'yes':
        print("Alarm conversion aborted!")
        return
    args = get_parser().parse_args()
    conf = service.prepare_service()
    conn = storage.get_connection_from_config(conf)
    combination_alarms = list(conn.get_alarms(alarm_type='combination',
                                              alarm_id=args.alarm_id or None))
    count = 0
    for alarm in combination_alarms:
        new_name = 'From-combination: %s' % alarm.alarm_id
        n_alarm = list(conn.get_alarms(name=new_name, alarm_type='composite'))
        if n_alarm:
            LOG.warning(_LW('Alarm %(alarm)s has been already converted as '
                            'composite alarm: %(n_alarm_id)s, skipped.'),
                        {'alarm': alarm.alarm_id,
                         'n_alarm_id': n_alarm[0].alarm_id})
            continue
        try:
            composite_rule = _generate_composite_rule(conn, alarm)
        except DependentAlarmNotFound as e:
            LOG.warning(_LW('The dependent alarm %(dep_alarm)s of alarm %'
                            '(com_alarm)s not found, skipped.'),
                        {'com_alarm': e.com_alarm_id,
                         'dep_alarm': e.dependent_alarm_id})
            continue
        except UnsupportedSubAlarmType as e:
            LOG.warning(_LW('Alarm conversion from combination to composite '
                            'only support combination alarms depending '
                            'threshold alarms, the type of alarm %(alarm)s '
                            'is: %(type)s, skipped.'),
                        {'alarm': e.sub_alarm_id, 'type': e.sub_alarm_type})
            continue
        new_alarm = models.Alarm(**alarm.as_dict())
        new_alarm.alarm_id = str(uuid.uuid4())
        new_alarm.name = new_name
        new_alarm.type = 'composite'
        new_alarm.description = ('composite alarm converted from combination '
                                 'alarm: %s' % alarm.alarm_id)
        new_alarm.rule = composite_rule
        new_alarm.timestamp = datetime.datetime.now()
        conn.create_alarm(new_alarm)
        LOG.info(_LI('End Converting combination alarm %(s_alarm)s to '
                     'composite alarm %(d_alarm)s'),
                 {'s_alarm': alarm.alarm_id, 'd_alarm': new_alarm.alarm_id})
        count += 1
    if args.delete_combination_alarm:
        for alarm in combination_alarms:
            LOG.info(_LI('Deleting the combination alarm %s...'),
                     alarm.alarm_id)
            conn.delete_alarm(alarm.alarm_id)
    LOG.info(_LI('%s combination alarms have been converted to composite '
                 'alarms.'), count)
