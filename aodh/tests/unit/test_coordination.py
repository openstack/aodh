#
# Copyright 2014 Red Hat, Inc.
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

import mock
from oslo_config import fixture as fixture_config
import tooz.coordination

from aodh import coordination
from aodh import service
from aodh.tests import base


class MockToozCoordinator(object):
    def __init__(self, member_id, shared_storage):
        self._member_id = member_id
        self._groups = shared_storage
        self.is_started = False

    def start(self):
        self.is_started = True

    def stop(self):
        pass

    def heartbeat(self):
        pass

    def create_group(self, group_id):
        if group_id in self._groups:
            return MockAsyncError(
                tooz.coordination.GroupAlreadyExist(group_id))
        self._groups[group_id] = {}
        return MockAsyncResult(None)

    def join_group(self, group_id, capabilities=b''):
        if group_id not in self._groups:
            return MockAsyncError(
                tooz.coordination.GroupNotCreated(group_id))
        if self._member_id in self._groups[group_id]:
            return MockAsyncError(
                tooz.coordination.MemberAlreadyExist(group_id,
                                                     self._member_id))
        self._groups[group_id][self._member_id] = {
            "capabilities": capabilities,
        }
        return MockAsyncResult(None)

    def leave_group(self, group_id):
        return MockAsyncResult(None)

    def get_members(self, group_id):
        if group_id not in self._groups:
            return MockAsyncError(
                tooz.coordination.GroupNotCreated(group_id))
        return MockAsyncResult(self._groups[group_id])


class MockToozCoordExceptionRaiser(MockToozCoordinator):
    def start(self):
        raise tooz.coordination.ToozError('error')

    def heartbeat(self):
        raise tooz.coordination.ToozError('error')

    def join_group(self, group_id, capabilities=b''):
        raise tooz.coordination.ToozError('error')

    def get_members(self, group_id):
        raise tooz.coordination.ToozError('error')


class MockAsyncResult(tooz.coordination.CoordAsyncResult):
    def __init__(self, result):
        self.result = result

    def get(self, timeout=0):
        return self.result

    @staticmethod
    def done():
        return True


class MockAsyncError(tooz.coordination.CoordAsyncResult):
    def __init__(self, error):
        self.error = error

    def get(self, timeout=0):
        raise self.error

    @staticmethod
    def done():
        return True


class TestHashRing(base.BaseTestCase):
    def test_hash_ring(self):
        num_nodes = 10
        num_keys = 1000

        nodes = [str(x) for x in range(num_nodes)]
        hr = coordination.HashRing(nodes)

        buckets = [0] * num_nodes
        assignments = [-1] * num_keys
        for k in range(num_keys):
            n = int(hr.get_node(str(k)))
            self.assertLessEqual(0, n)
            self.assertLessEqual(n, num_nodes)
            buckets[n] += 1
            assignments[k] = n

        # at least something in each bucket
        self.assertTrue(all((c > 0 for c in buckets)))

        # approximately even distribution
        diff = max(buckets) - min(buckets)
        self.assertLess(diff, 0.3 * (num_keys / num_nodes))

        # consistency
        num_nodes += 1
        nodes.append(str(num_nodes + 1))
        hr = coordination.HashRing(nodes)
        for k in range(num_keys):
            n = int(hr.get_node(str(k)))
            assignments[k] -= n
        reassigned = len([c for c in assignments if c != 0])
        self.assertLess(reassigned, num_keys / num_nodes)


class TestPartitioning(base.BaseTestCase):

    def setUp(self):
        super(TestPartitioning, self).setUp()
        conf = service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf
        self.shared_storage = {}

    def _get_new_started_coordinator(self, shared_storage, agent_id=None,
                                     coordinator_cls=None):
        coordinator_cls = coordinator_cls or MockToozCoordinator
        self.CONF.set_override('backend_url', 'xxx://yyy',
                               group='coordination')
        with mock.patch('tooz.coordination.get_coordinator',
                        lambda _, member_id:
                        coordinator_cls(member_id, shared_storage)):
            pc = coordination.PartitionCoordinator(self.CONF, agent_id)
            pc.start()
            return pc

    def _usage_simulation(self, *agents_kwargs):
        partition_coordinators = []
        for kwargs in agents_kwargs:
            partition_coordinator = self._get_new_started_coordinator(
                self.shared_storage, kwargs['agent_id'], kwargs.get(
                    'coordinator_cls'))
            partition_coordinator.join_group(kwargs['group_id'])
            partition_coordinators.append(partition_coordinator)

        for i, kwargs in enumerate(agents_kwargs):
            all_resources = kwargs.get('all_resources', [])
            expected_resources = kwargs.get('expected_resources', [])
            actual_resources = partition_coordinators[i].extract_my_subset(
                kwargs['group_id'], all_resources)
            self.assertEqual(expected_resources, actual_resources)

    def test_single_group(self):
        agents = [dict(agent_id='agent1', group_id='group'),
                  dict(agent_id='agent2', group_id='group')]
        self._usage_simulation(*agents)

        self.assertEqual(['group'], sorted(self.shared_storage.keys()))
        self.assertEqual(['agent1', 'agent2'],
                         sorted(self.shared_storage['group'].keys()))

    def test_multiple_groups(self):
        agents = [dict(agent_id='agent1', group_id='group1'),
                  dict(agent_id='agent2', group_id='group2')]
        self._usage_simulation(*agents)

        self.assertEqual(['group1', 'group2'],
                         sorted(self.shared_storage.keys()))

    def test_partitioning(self):
        all_resources = ['resource_%s' % i for i in range(1000)]
        agents = ['agent_%s' % i for i in range(10)]

        expected_resources = [list() for _ in range(len(agents))]
        hr = coordination.HashRing(agents)
        for r in all_resources:
            key = agents.index(hr.get_node(r))
            expected_resources[key].append(r)

        agents_kwargs = []
        for i, agent in enumerate(agents):
            agents_kwargs.append(dict(agent_id=agent,
                                 group_id='group',
                                 all_resources=all_resources,
                                 expected_resources=expected_resources[i]))
        self._usage_simulation(*agents_kwargs)

    @mock.patch.object(coordination.LOG, 'exception')
    def test_coordination_backend_offline(self, mocked_exception):
        agents = [dict(agent_id='agent1',
                       group_id='group',
                       all_resources=['res1', 'res2'],
                       expected_resources=[],
                       coordinator_cls=MockToozCoordExceptionRaiser)]
        self._usage_simulation(*agents)
        called = [mock.call(u'Error connecting to coordination backend.'),
                  mock.call(u'Error getting group membership info from '
                            u'coordination backend.')]
        self.assertEqual(called, mocked_exception.call_args_list)

    @mock.patch.object(coordination.LOG, 'exception')
    @mock.patch.object(coordination.LOG, 'info')
    def test_reconnect(self, mock_info, mocked_exception):
        coord = self._get_new_started_coordinator({}, 'a',
                                                  MockToozCoordExceptionRaiser)
        with mock.patch('tooz.coordination.get_coordinator',
                        return_value=MockToozCoordExceptionRaiser('a', {})):
            coord.heartbeat()
        called = [mock.call(u'Error connecting to coordination backend.'),
                  mock.call(u'Error connecting to coordination backend.'),
                  mock.call(u'Error sending a heartbeat to coordination '
                            u'backend.')]
        self.assertEqual(called, mocked_exception.call_args_list)
        with mock.patch('tooz.coordination.get_coordinator',
                        return_value=MockToozCoordinator('a', {})):
            coord.heartbeat()
        mock_info.assert_called_with(u'Coordination backend started '
                                     u'successfully.')

    def test_group_id_none(self):
        coord = self._get_new_started_coordinator({}, 'a')
        self.assertTrue(coord._coordinator.is_started)

        with mock.patch.object(coord._coordinator, 'join_group') as mocked:
            coord.join_group(None)
            self.assertEqual(0, mocked.call_count)
        with mock.patch.object(coord._coordinator, 'leave_group') as mocked:
            coord.leave_group(None)
            self.assertEqual(0, mocked.call_count)

    def test_stop(self):
        coord = self._get_new_started_coordinator({}, 'a')
        self.assertTrue(coord._coordinator.is_started)
        coord.join_group("123")
        coord.stop()
        self.assertIsEmpty(coord._groups)
        self.assertIsNone(coord._coordinator)
