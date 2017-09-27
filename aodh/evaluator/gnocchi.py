#
# Copyright 2015 eNovance
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

from gnocchiclient import client
from gnocchiclient import exceptions
from oslo_log import log
from oslo_serialization import jsonutils

from aodh.evaluator import threshold
from aodh import keystone_client

LOG = log.getLogger(__name__)

# The list of points that Gnocchi API returned is composed
# of tuples with (timestamp, granularity, value)
GRANULARITY = 1
VALUE = 2


class GnocchiBase(threshold.ThresholdEvaluator):
    def __init__(self, conf):
        super(GnocchiBase, self).__init__(conf)
        self._gnocchi_client = client.Client(
            '1', keystone_client.get_session(conf),
            adapter_options={
                'interface': conf.service_credentials.interface,
                'region_name': conf.service_credentials.region_name})

    @staticmethod
    def _sanitize(rule, statistics):
        """Return the datapoints that correspond to the alarm granularity"""
        # TODO(sileht): if there's no direct match, but there is an archive
        # policy with granularity that's an even divisor or the period,
        # we could potentially do a mean-of-means (or max-of-maxes or whatever,
        # but not a stddev-of-stddevs).
        # TODO(sileht): support alarm['exclude_outliers']
        LOG.debug('sanitize stats %s', statistics)
        statistics = [stats[VALUE] for stats in statistics
                      if stats[GRANULARITY] == rule['granularity']]
        if not statistics:
            raise threshold.InsufficientDataError(
                "No datapoint for granularity %s" % rule['granularity'], [])
        statistics = statistics[-rule['evaluation_periods']:]
        LOG.debug('pruned statistics to %d', len(statistics))
        return statistics


class GnocchiResourceThresholdEvaluator(GnocchiBase):
    def _statistics(self, rule, start, end):
        try:
            return self._gnocchi_client.metric.get_measures(
                metric=rule['metric'],
                granularity=rule['granularity'],
                start=start, stop=end,
                resource_id=rule['resource_id'],
                aggregation=rule['aggregation_method'])
        except exceptions.MetricNotFound:
            raise threshold.InsufficientDataError(
                'metric %s for resource %s does not exists' %
                (rule['metric'], rule['resource_id']), [])
        except exceptions.ResourceNotFound:
            raise threshold.InsufficientDataError(
                'resource %s does not exists' % rule['resource_id'], [])
        except exceptions.NotFound:
            # TODO(sileht): gnocchiclient should raise a explicit
            # exception for AggregationNotFound, this API endpoint
            # can only raise 3 different 404, so we are safe to
            # assume this is an AggregationNotFound for now.
            raise threshold.InsufficientDataError(
                'aggregation %s does not exist for '
                'metric %s of resource %s' % (rule['aggregation_method'],
                                              rule['metric'],
                                              rule['resource_id']),
                [])
        except Exception as e:
            msg = 'alarm statistics retrieval failed: %s' % e
            LOG.warning(msg)
            raise threshold.InsufficientDataError(msg, [])


class GnocchiAggregationMetricsThresholdEvaluator(GnocchiBase):
    def _statistics(self, rule, start, end):
        try:
            # FIXME(sileht): In case of a heat autoscaling stack decide to
            # delete an instance, the gnocchi metrics associated to this
            # instance will be no more updated and when the alarm will ask
            # for the aggregation, gnocchi will raise a 'No overlap'
            # exception.
            # So temporary set 'needed_overlap' to 0 to disable the
            # gnocchi checks about missing points. For more detail see:
            #   https://bugs.launchpad.net/gnocchi/+bug/1479429
            return self._gnocchi_client.metric.aggregation(
                metrics=rule['metrics'],
                granularity=rule['granularity'],
                start=start, stop=end,
                aggregation=rule['aggregation_method'],
                needed_overlap=0)
        except exceptions.MetricNotFound:
            raise threshold.InsufficientDataError(
                'At least of metrics in %s does not exist' %
                rule['metrics'], [])
        except exceptions.NotFound:
            # TODO(sileht): gnocchiclient should raise a explicit
            # exception for AggregationNotFound, this API endpoint
            # can only raise 3 different 404, so we are safe to
            # assume this is an AggregationNotFound for now.
            raise threshold.InsufficientDataError(
                'aggregation %s does not exist for at least one '
                'metrics in %s' % (rule['aggregation_method'],
                                   rule['metrics']), [])
        except Exception as e:
            msg = 'alarm statistics retrieval failed: %s' % e
            LOG.warning(msg)
            raise threshold.InsufficientDataError(msg, [])


class GnocchiAggregationResourcesThresholdEvaluator(GnocchiBase):
    def _statistics(self, rule, start, end):
        # FIXME(sileht): In case of a heat autoscaling stack decide to
        # delete an instance, the gnocchi metrics associated to this
        # instance will be no more updated and when the alarm will ask
        # for the aggregation, gnocchi will raise a 'No overlap'
        # exception.
        # So temporary set 'needed_overlap' to 0 to disable the
        # gnocchi checks about missing points. For more detail see:
        #   https://bugs.launchpad.net/gnocchi/+bug/1479429
        try:
            return self._gnocchi_client.metric.aggregation(
                metrics=rule['metric'],
                granularity=rule['granularity'],
                query=jsonutils.loads(rule['query']),
                resource_type=rule["resource_type"],
                start=start, stop=end,
                aggregation=rule['aggregation_method'],
                needed_overlap=0,
            )
        except exceptions.MetricNotFound:
            raise threshold.InsufficientDataError(
                'metric %s does not exists' % rule['metric'], [])
        except exceptions.NotFound:
            # TODO(sileht): gnocchiclient should raise a explicit
            # exception for AggregationNotFound, this API endpoint
            # can only raise 3 different 404, so we are safe to
            # assume this is an AggregationNotFound for now.
            raise threshold.InsufficientDataError(
                'aggregation %s does not exist for at least one '
                'metric of the query' % rule['aggregation_method'], [])
        except Exception as e:
            msg = 'alarm statistics retrieval failed: %s' % e
            LOG.warning(msg)
            raise threshold.InsufficientDataError(msg, [])
