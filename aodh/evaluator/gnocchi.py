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
from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils

from aodh.evaluator import threshold
from aodh.i18n import _
from aodh import keystone_client

LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('gnocchi_url',
               deprecated_group="alarm",
               deprecated_for_removal=True,
               help='URL to Gnocchi. default: autodetection'),
]


class GnocchiThresholdEvaluator(threshold.ThresholdEvaluator):

    def __init__(self, conf):
        super(threshold.ThresholdEvaluator, self).__init__(conf)
        self._gnocchi_client = client.Client(
            '1', keystone_client.get_session(conf),
            interface=conf.service_credentials.interface,
            region_name=conf.service_credentials.region_name,
            endpoint_override=conf.gnocchi_url)

    def _statistics(self, alarm, start, end):
        """Retrieve statistics over the current window."""
        try:
            if alarm.type == 'gnocchi_aggregation_by_resources_threshold':
                # FIXME(sileht): In case of a heat autoscaling stack decide to
                # delete an instance, the gnocchi metrics associated to this
                # instance will be no more updated and when the alarm will ask
                # for the aggregation, gnocchi will raise a 'No overlap'
                # exception.
                # So temporary set 'needed_overlap' to 0 to disable the
                # gnocchi checks about missing points. For more detail see:
                #   https://bugs.launchpad.net/gnocchi/+bug/1479429
                return self._gnocchi_client.metric.aggregation(
                    metrics=alarm.rule['metric'],
                    query=jsonutils.loads(alarm.rule['query']),
                    resource_type=alarm.rule["resource_type"],
                    start=start, stop=end,
                    aggregation=alarm.rule['aggregation_method'],
                    needed_overlap=0,
                )
            elif alarm.type == 'gnocchi_aggregation_by_metrics_threshold':
                return self._gnocchi_client.metric.aggregation(
                    metrics=alarm.rule['metrics'],
                    start=start, stop=end,
                    aggregation=alarm.rule['aggregation_method'])
            elif alarm.type == 'gnocchi_resources_threshold':
                return self._gnocchi_client.metric.get_measures(
                    metric=alarm.rule['metric'],
                    start=start, stop=end,
                    resource_id=alarm.rule['resource_id'],
                    aggregation=alarm.rule['aggregation_method'])
        except Exception:
            LOG.exception(_('alarm stats retrieval failed'))
            return []

    @staticmethod
    def _sanitize(alarm, statistics):
        """Return the datapoints that correspond to the alarm granularity"""
        # TODO(sileht): if there's no direct match, but there is an archive
        # policy with granularity that's an even divisor or the period,
        # we could potentially do a mean-of-means (or max-of-maxes or whatever,
        # but not a stddev-of-stddevs).
        # TODO(sileht): support alarm['exclude_outliers']
        LOG.error('sanitize (%s) stats %s', alarm.rule['granularity'],
                  statistics)
        statistics = [stats[2] for stats in statistics
                      if stats[1] == alarm.rule['granularity']]
        statistics = statistics[-alarm.rule['evaluation_periods']:]
        LOG.error('pruned statistics to %d', len(statistics))
        return statistics
