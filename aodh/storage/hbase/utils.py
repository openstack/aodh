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
""" Various HBase helpers
"""
import copy
import datetime
import json

import bson.json_util
from happybase.hbase import ttypes
from oslo_log import log
import six

from aodh.i18n import _

LOG = log.getLogger(__name__)

OP_SIGN = {'eq': '=', 'lt': '<', 'le': '<=', 'ne': '!=', 'gt': '>', 'ge': '>='}
# We need this additional dictionary because we have reverted timestamp in
# row-keys for stored metrics
OP_SIGN_REV = {'eq': '=', 'lt': '>', 'le': '>=', 'ne': '!=', 'gt': '<',
               'ge': '<='}


def timestamp(dt, reverse=True):
    """Timestamp is count of milliseconds since start of epoch.

    If reverse=True then timestamp will be reversed. Such a technique is used
    in HBase rowkey design when period queries are required. Because of the
    fact that rows are sorted lexicographically it's possible to vary whether
    the 'oldest' entries will be on top of the table or it should be the newest
    ones (reversed timestamp case).

    :param dt: datetime which is translated to timestamp
    :param reverse: a boolean parameter for reverse or straight count of
      timestamp in milliseconds
    :return: count or reversed count of milliseconds since start of epoch
    """
    epoch = datetime.datetime(1970, 1, 1)
    td = dt - epoch
    ts = td.microseconds + td.seconds * 1000000 + td.days * 86400000000
    return 0x7fffffffffffffff - ts if reverse else ts


def make_timestamp_query(func, start=None, start_op=None, end=None,
                         end_op=None, bounds_only=False, **kwargs):
    """Return a filter start and stop row for filtering and a query.

    Query is based on the fact that CF-name is 'rts'.
    :param start: Optional start timestamp
    :param start_op: Optional start timestamp operator, like gt, ge
    :param end: Optional end timestamp
    :param end_op: Optional end timestamp operator, like lt, le
    :param bounds_only: if True than query will not be returned
    :param func: a function that provide a format of row
    :param kwargs: kwargs for :param func
    """
    # We don't need to dump here because get_start_end_rts returns strings
    rts_start, rts_end = get_start_end_rts(start, end)
    start_row, end_row = func(rts_start, rts_end, **kwargs)

    if bounds_only:
        return start_row, end_row

    q = []
    start_op = start_op or 'ge'
    end_op = end_op or 'lt'
    if rts_start:
        q.append("SingleColumnValueFilter ('f', 'rts', %s, 'binary:%s')" %
                 (OP_SIGN_REV[start_op], rts_start))
    if rts_end:
        q.append("SingleColumnValueFilter ('f', 'rts', %s, 'binary:%s')" %
                 (OP_SIGN_REV[end_op], rts_end))

    res_q = None
    if len(q):
        res_q = " AND ".join(q)

    return start_row, end_row, res_q


def get_start_end_rts(start, end):

    rts_start = str(timestamp(start)) if start else ""
    rts_end = str(timestamp(end)) if end else ""
    return rts_start, rts_end


def make_query(**kwargs):
    """Return a filter query string based on the selected parameters.

    :param kwargs: key-value pairs to filter on. Key should be a real
      column name in db
    """
    q = []

    # Note: we use extended constructor for SingleColumnValueFilter here.
    # It is explicitly specified that entry should not be returned if CF is not
    # found in table.
    for key, value in sorted(kwargs.items()):
        if value is not None:
            if key == 'source':
                q.append("SingleColumnValueFilter "
                         "('f', 's_%s', =, 'binary:%s', true, true)" %
                         (value, dump('1')))
            elif key == 'trait_type':
                q.append("ColumnPrefixFilter('%s')" % value)
            elif key == 'event_id':
                q.append("RowFilter ( = , 'regexstring:\d*:%s')" % value)
            elif key == 'exclude':
                for k, v in six.iteritems(value):
                    q.append("SingleColumnValueFilter "
                             "('f', '%(k)s', !=, 'binary:%(v)s', true, true)" %
                             {'k': quote(k), 'v': dump(v)})
            else:
                q.append("SingleColumnValueFilter "
                         "('f', '%s', =, 'binary:%s', true, true)" %
                         (quote(key), dump(value)))
    if len(q):
        return " AND ".join(q)


def make_general_rowkey_scan(rts_start=None, rts_end=None, some_id=None):
    """If it's filter on some_id without start and end.

    start_row = some_id while end_row = some_id + MAX_BYTE.
    """
    if some_id is None:
        return None, None
    if not rts_start:
        # NOTE(idegtiarov): Here we could not use chr > 122 because chr >= 123
        # will be quoted and character will be turn in a composition that is
        # started with '%' (chr(37)) that lexicographically is less then chr
        # of number
        rts_start = chr(122)
    end_row = prepare_key(some_id, rts_start)
    start_row = prepare_key(some_id, rts_end)

    return start_row, end_row


def prepare_key(*args):
    """Prepares names for rows and columns with correct separator.

    :param args: strings or numbers that we want our key construct of
    :return: key with quoted args that are separated with character ":"
    """
    key_quote = []
    for key in args:
        if isinstance(key, six.integer_types):
            key = str(key)
        key_quote.append(quote(key))
    return ":".join(key_quote)


def deserialize_entry(entry):
    """Return a list of flatten results.

    Result contains a dict of simple structures such as 'resource_id':1

    :param entry: entry from HBase, without row name and timestamp
    """
    flatten_result = {}
    for k, v in entry.items():
        if ':' in k[2:]:
            key = tuple([unquote(i) for i in k[2:].split(':')])
        else:
            key = unquote(k[2:])
        flatten_result[key] = load(v)

    return flatten_result


def serialize_entry(data=None, **kwargs):
    """Return a dict that is ready to be stored to HBase

    :param data: dict to be serialized
    :param kwargs: additional args
    """
    data = data or {}
    entry_dict = copy.copy(data)
    entry_dict.update(**kwargs)

    result = {}
    for k, v in entry_dict.items():
        result['f:' + quote(k, ':')] = dump(v)
    return result


def dump(data):
    return json.dumps(data, default=bson.json_util.default)


def load(data):
    return json.loads(data, object_hook=object_hook)


# We don't want to have tzinfo in decoded json.This object_hook is
# overwritten json_util.object_hook for $date
def object_hook(dct):
    if "$date" in dct:
        dt = bson.json_util.object_hook(dct)
        return dt.replace(tzinfo=None)
    return bson.json_util.object_hook(dct)


def create_tables(conn, tables, column_families):
    for table in tables:
        try:
            conn.create_table(table, column_families)
        except ttypes.AlreadyExists:
            if conn.table_prefix:
                table = ("%(table_prefix)s"
                         "%(separator)s"
                         "%(table_name)s" %
                         dict(table_prefix=conn.table_prefix,
                              separator=conn.table_prefix_separator,
                              table_name=table))

            LOG.warning(_("Cannot create table %(table_name)s   "
                        "it already exists. Ignoring error")
                        % {'table_name': table})


def quote(s, *args):
    """Return quoted string even if it is unicode one.

    :param s: string that should be quoted
    :param args: any symbol we want to stay unquoted
    """
    s_en = s.encode('utf8')
    return six.moves.urllib.parse.quote(s_en, *args)


def unquote(s):
    """Return unquoted and decoded string.

    :param s: string that should be unquoted
    """
    s_de = six.moves.urllib.parse.unquote(s)
    return s_de.decode('utf8')
