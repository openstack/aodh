#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
"""Storage backend management
"""
import datetime

from oslo_config import cfg
from oslo_log import log
from oslo_utils import timeutils
import retrying
import six.moves.urllib.parse as urlparse
from stevedore import driver
import warnings

_NAMESPACE = 'aodh.storage'


LOG = log.getLogger(__name__)


OPTS = [
    cfg.IntOpt('alarm_history_time_to_live',
               default=-1,
               help=("Number of seconds that alarm histories are kept "
                     "in the database for (<= 0 means forever).")),
    cfg.StrOpt('alarm_connection',
               secret=True,
               deprecated_for_removal=True,
               help='The connection string used to connect '
               'to the alarm database - rather use ${database.connection}'),
]


class StorageBadVersion(Exception):
    """Error raised when the storage backend version is not good enough."""


def get_connection_from_config(conf):
    retries = conf.database.max_retries
    if conf.database.alarm_connection is None:
        url = conf.database.connection
    else:
        url = conf.database.alarm_connection
    connection_scheme = urlparse.urlparse(url).scheme
    if connection_scheme not in ('mysql', 'mysql+pymysql', 'postgresql',
                                 'sqlite'):
        msg = ('Storage backend %s is deprecated, and all the NoSQL backends '
               'will be removed in Aodh 4.0, please use SQL backend.' %
               connection_scheme)
        warnings.warn(msg)
    LOG.debug('looking for %(name)r driver in %(namespace)r',
              {'name': connection_scheme, 'namespace': _NAMESPACE})
    mgr = driver.DriverManager(_NAMESPACE, connection_scheme)

    # Convert retry_interval secs to msecs for retry decorator
    @retrying.retry(wait_fixed=conf.database.retry_interval * 1000,
                    stop_max_attempt_number=retries if retries >= 0 else None)
    def _get_connection():
        """Return an open connection to the database."""
        return mgr.driver(conf, url)

    return _get_connection()


class SampleFilter(object):
    """Holds the properties for building a query from a meter/sample filter.

    :param user: The sample owner.
    :param project: The sample project.
    :param start_timestamp: Earliest time point in the request.
    :param start_timestamp_op: Earliest timestamp operation in the request.
    :param end_timestamp: Latest time point in the request.
    :param end_timestamp_op: Latest timestamp operation in the request.
    :param resource: Optional filter for resource id.
    :param meter: Optional filter for meter type using the meter name.
    :param source: Optional source filter.
    :param message_id: Optional sample_id filter.
    :param metaquery: Optional filter on the metadata
    """
    def __init__(self, user=None, project=None,
                 start_timestamp=None, start_timestamp_op=None,
                 end_timestamp=None, end_timestamp_op=None,
                 resource=None, meter=None,
                 source=None, message_id=None,
                 metaquery=None):
        self.user = user
        self.project = project
        self.start_timestamp = self.sanitize_timestamp(start_timestamp)
        self.start_timestamp_op = start_timestamp_op
        self.end_timestamp = self.sanitize_timestamp(end_timestamp)
        self.end_timestamp_op = end_timestamp_op
        self.resource = resource
        self.meter = meter
        self.source = source
        self.metaquery = metaquery or {}
        self.message_id = message_id

    @staticmethod
    def sanitize_timestamp(timestamp):
        """Return a naive utc datetime object."""
        if not timestamp:
            return timestamp
        if not isinstance(timestamp, datetime.datetime):
            timestamp = timeutils.parse_isotime(timestamp)
        return timeutils.normalize_time(timestamp)

    def __repr__(self):
        return ("<SampleFilter(user: %s,"
                " project: %s,"
                " start_timestamp: %s,"
                " start_timestamp_op: %s,"
                " end_timestamp: %s,"
                " end_timestamp_op: %s,"
                " resource: %s,"
                " meter: %s,"
                " source: %s,"
                " metaquery: %s,"
                " message_id: %s)>" %
                (self.user,
                 self.project,
                 self.start_timestamp,
                 self.start_timestamp_op,
                 self.end_timestamp,
                 self.end_timestamp_op,
                 self.resource,
                 self.meter,
                 self.source,
                 self.metaquery,
                 self.message_id))
