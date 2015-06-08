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
"""HBase storage backend migrations
"""


from aodh.storage.hbase import utils as hbase_utils


def migrate_alarm_history_table(conn, table):
    """Migrate table 'alarm_h' in HBase.

    Change row format from ""%s_%s" % alarm_id, rts,
    to new separator format "%s:%s" % alarm_id, rts
    """
    alarm_h_table = conn.table(table)
    alarm_h_filter = "RowFilter(=, 'regexstring:\\w*_\\d{19}')"
    gen = alarm_h_table.scan(filter=alarm_h_filter)
    for row, data in gen:
        row_parts = row.rsplit('_', 1)
        alarm_h_table.put(hbase_utils.prepare_key(*row_parts), data)
        alarm_h_table.delete(row)


TABLE_MIGRATION_FUNCS = {'alarm_h': migrate_alarm_history_table}


def migrate_tables(conn, tables):
    if type(tables) is not list:
        tables = [tables]
    for table in tables:
        if table in TABLE_MIGRATION_FUNCS:
            TABLE_MIGRATION_FUNCS.get(table)(conn, table)
