#
# Copyright 2014 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import bisect
import hashlib
import struct

from oslo_config import cfg
from oslo_log import log
from oslo_utils import uuidutils
import six
import tenacity
import tooz.coordination


LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('backend_url',
               help='The backend URL to use for distributed coordination. If '
                    'left empty, per-deployment central agent and per-host '
                    'compute agent won\'t do workload '
                    'partitioning and will only function correctly if a '
                    'single instance of that service is running.'),
    cfg.FloatOpt('heartbeat',
                 default=1.0,
                 help='Number of seconds between heartbeats for distributed '
                      'coordination.'),
    cfg.FloatOpt('check_watchers',
                 default=10.0,
                 help='Number of seconds between checks to see if group '
                      'membership has changed'),
    cfg.IntOpt('retry_backoff',
               default=1,
               help='Retry backoff factor when retrying to connect with'
                    ' coordination backend'),
    cfg.IntOpt('max_retry_interval',
               default=30,
               help='Maximum number of seconds between retry to join '
                    'partitioning group')
]


class ErrorJoiningPartitioningGroup(Exception):
    def __init__(self):
        super(ErrorJoiningPartitioningGroup, self).__init__((
            'Error occurred when joining partitioning group'))


class MemberNotInGroupError(Exception):
    def __init__(self, group_id, members, my_id):
        super(MemberNotInGroupError, self).__init__((
            'Group ID: %(group_id)s, Members: %(members)s, Me: %(me)s: '
            'Current agent is not part of group and cannot take tasks') %
            {'group_id': group_id, 'members': members, 'me': my_id})


class HashRing(object):

    def __init__(self, nodes, replicas=100):
        self._ring = dict()
        self._sorted_keys = []

        for node in nodes:
            for r in six.moves.range(replicas):
                hashed_key = self._hash('%s-%s' % (node, r))
                self._ring[hashed_key] = node
                self._sorted_keys.append(hashed_key)
        self._sorted_keys.sort()

    @staticmethod
    def _hash(key):
        return struct.unpack_from('>I',
                                  hashlib.md5(str(key).encode()).digest())[0]

    def _get_position_on_ring(self, key):
        hashed_key = self._hash(key)
        position = bisect.bisect(self._sorted_keys, hashed_key)
        return position if position < len(self._sorted_keys) else 0

    def get_node(self, key):
        if not self._ring:
            return None
        pos = self._get_position_on_ring(key)
        return self._ring[self._sorted_keys[pos]]


class PartitionCoordinator(object):
    """Workload partitioning coordinator.

    This class uses the `tooz` library to manage group membership.

    To ensure that the other agents know this agent is still alive,
    the `heartbeat` method should be called periodically.

    Coordination errors and reconnects are handled under the hood, so the
    service using the partition coordinator need not care whether the
    coordination backend is down. The `extract_my_subset` will simply return an
    empty iterable in this case.
    """

    def __init__(self, conf, my_id=None):
        self.conf = conf
        self.backend_url = self.conf.coordination.backend_url
        self._coordinator = None
        self._groups = set()
        self._my_id = my_id or uuidutils.generate_uuid()

    def start(self):
        if self.backend_url:
            try:
                self._coordinator = tooz.coordination.get_coordinator(
                    self.backend_url, self._my_id)
                self._coordinator.start()
                LOG.info('Coordination backend started successfully.')
            except tooz.coordination.ToozError:
                LOG.exception('Error connecting to coordination backend.')

    def stop(self):
        if not self._coordinator:
            return

        for group in list(self._groups):
            self.leave_group(group)

        try:
            self._coordinator.stop()
        except tooz.coordination.ToozError:
            LOG.exception('Error connecting to coordination backend.')
        finally:
            self._coordinator = None

    def is_active(self):
        return self._coordinator is not None

    def heartbeat(self):
        if self._coordinator:
            if not self._coordinator.is_started:
                # re-connect
                self.start()
            try:
                self._coordinator.heartbeat()
            except tooz.coordination.ToozError:
                LOG.exception('Error sending a heartbeat to coordination '
                              'backend.')

    def join_group(self, group_id):
        if (not self._coordinator or not self._coordinator.is_started
                or not group_id):
            return

        @tenacity.retry(
            wait=tenacity.wait_exponential(
                multiplier=self.conf.coordination.retry_backoff,
                max=self.conf.coordination.max_retry_interval),
            retry=tenacity.retry_if_exception_type(
                ErrorJoiningPartitioningGroup))
        def _inner():
            try:
                join_req = self._coordinator.join_group(group_id)
                join_req.get()
                LOG.info('Joined partitioning group %s', group_id)
            except tooz.coordination.MemberAlreadyExist:
                return
            except tooz.coordination.GroupNotCreated:
                create_grp_req = self._coordinator.create_group(group_id)
                try:
                    create_grp_req.get()
                except tooz.coordination.GroupAlreadyExist:
                    pass
                raise ErrorJoiningPartitioningGroup()
            except tooz.coordination.ToozError:
                LOG.exception('Error joining partitioning group %s,'
                              ' re-trying', group_id)
                raise ErrorJoiningPartitioningGroup()
            self._groups.add(group_id)

        return _inner()

    def leave_group(self, group_id):
        if group_id not in self._groups:
            return
        if self._coordinator:
            self._coordinator.leave_group(group_id)
            self._groups.remove(group_id)
            LOG.info('Left partitioning group %s', group_id)

    def _get_members(self, group_id):
        if not self._coordinator:
            return [self._my_id]

        while True:
            get_members_req = self._coordinator.get_members(group_id)
            try:
                return get_members_req.get()
            except tooz.coordination.GroupNotCreated:
                self.join_group(group_id)

    @tenacity.retry(
        wait=tenacity.wait_random(max=2),
        stop=tenacity.stop_after_attempt(5),
        retry=tenacity.retry_if_exception_type(MemberNotInGroupError),
        reraise=True)
    def extract_my_subset(self, group_id, universal_set):
        """Filters an iterable, returning only objects assigned to this agent.

        We have a list of objects and get a list of active group members from
        `tooz`. We then hash all the objects into buckets and return only
        the ones that hashed into *our* bucket.
        """
        if not group_id:
            return universal_set
        if group_id not in self._groups:
            self.join_group(group_id)
        try:
            members = self._get_members(group_id)
            LOG.debug('Members of group: %s, Me: %s', members, self._my_id)
            if self._my_id not in members:
                LOG.warning('Cannot extract tasks because agent failed to '
                            'join group properly. Rejoining group.')
                self.join_group(group_id)
                members = self._get_members(group_id)
                if self._my_id not in members:
                    raise MemberNotInGroupError(group_id, members, self._my_id)
                LOG.debug('Members of group: %s, Me: %s', members, self._my_id)
            hr = HashRing(members)
            LOG.debug('Universal set: %s', universal_set)
            my_subset = [v for v in universal_set
                         if hr.get_node(str(v)) == self._my_id]
            LOG.debug('My subset: %s', my_subset)
            return my_subset
        except tooz.coordination.ToozError:
            LOG.exception('Error getting group membership info from '
                          'coordination backend.')
            return []
