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

"""
A tool for migrating alarms and alarms history data from NoSQL to SQL.

NOTES:

- Users need to specify the source NoSQL connection url and the destination SQL
 connection URL with this tool, an usage example:
    aodh-data-migration --nosql-conn \
    mongodb://aodh:password@127.0.0.1:27017/aodh --sql-conn \
    mysql+pymysql://root:password@127.0.0.1/aodh?charset=utf8

- Both the alarm data and alarm history data will be migrated when running this
  tool, but the history data migration can be avoid by specifying False of
  --migrate-history option.

- It is better to ensure the db connection is OK when running this tool, and
  this tool can be run repeatedly, the duplicated data will be skipped.

- This tool depends on the NoSQL and SQL drivers of Aodh, so it is should be
  used only before the removal of NoSQL drivers.

- This tool has been tested OK in devstack environment, but users need to be
  cautious with this, because the data migration between storage backends is
  a bit dangerous.

"""

import argparse
import logging
import sys

from oslo_config import cfg
from oslo_db import exception
from oslo_db import options as db_options
from aodh.i18n import _LE, _LI, _LW
import six.moves.urllib.parse as urlparse

from aodh import storage

root_logger = logging.getLogger('')


def get_parser():
    parser = argparse.ArgumentParser(
        description='A tool for Migrating alarms and alarms history from'
                    ' NoSQL to SQL',
    )
    parser.add_argument(
        '--nosql-conn',
        required=True,
        type=str,
        help='The source NoSQL database connection.',
    )
    parser.add_argument(
        '--sql-conn',
        required=True,
        type=str,
        help='The destination SQL database connection.',
    )
    parser.add_argument(
        '--migrate-history',
        default=True,
        type=bool,
        help='Migrate history data when migrate alarms or not,'
             ' True as Default.',
    )
    parser.add_argument(
        '--debug',
        default=False,
        action='store_true',
        help='Show the debug level log messages.',
    )
    return parser


def _validate_conn_options(args):
    nosql_scheme = urlparse.urlparse(args.nosql_conn).scheme
    sql_scheme = urlparse.urlparse(args.sql_conn).scheme
    if nosql_scheme not in ('mongodb', 'hbase'):
        root_logger.error(_LE('Invalid source DB type %s, the source database '
                              'connection  should be one of: [mongodb, hbase]'
                              ), nosql_scheme)
        sys.exit(1)
    if sql_scheme not in ('mysql', 'mysql+pymysql', 'postgresql',
                          'sqlite'):
        root_logger.error(_LE('Invalid destination DB type %s, the destination'
                              ' database connection should be one of: '
                              '[mysql, postgresql, sqlite]'), sql_scheme)
        sys.exit(1)


def main():
    args = get_parser().parse_args()

    # Set up logging to use the console
    console = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    root_logger.addHandler(console)
    if args.debug:
        root_logger.setLevel(logging.DEBUG)
    else:
        root_logger.setLevel(logging.INFO)

    _validate_conn_options(args)

    nosql_conf = cfg.ConfigOpts()
    db_options.set_defaults(nosql_conf, args.nosql_conn)
    nosql_conf.register_opts(storage.OPTS, 'database')
    nosql_conn = storage.get_connection_from_config(nosql_conf)

    sql_conf = cfg.ConfigOpts()
    db_options.set_defaults(sql_conf, args.sql_conn)
    sql_conf.register_opts(storage.OPTS, 'database')
    sql_conn = storage.get_connection_from_config(sql_conf)

    root_logger.info(
        _LI("Starting to migrate alarms data from NoSQL to SQL..."))

    count = 0
    for alarm in nosql_conn.get_alarms():
        root_logger.debug("Migrating alarm %s..." % alarm.alarm_id)
        try:
            sql_conn.create_alarm(alarm)
            count += 1
        except exception.DBDuplicateEntry:
            root_logger.warning(_LW("Duplicated alarm %s found, skipped."),
                                alarm.alarm_id)
        if not args.migrate_history:
            continue

        history_count = 0
        for history in nosql_conn.get_alarm_changes(alarm.alarm_id, None):
            history_data = history.as_dict()
            root_logger.debug("    Migrating alarm history data with"
                              " event_id %s..." % history_data['event_id'])
            try:
                sql_conn.record_alarm_change(history_data)
                history_count += 1
            except exception.DBDuplicateEntry:
                root_logger.warning(
                    _LW("    Duplicated alarm history %s found, skipped."),
                    history_data['event_id'])
        root_logger.info(_LI("    Migrated %(count)s history data of alarm "
                             "%(alarm_id)s"),
                         {'count': history_count, 'alarm_id': alarm.alarm_id})

    root_logger.info(_LI("End alarms data migration from NoSQL to SQL, %s"
                         " alarms have been migrated."), count)
