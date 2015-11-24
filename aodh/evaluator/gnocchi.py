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

from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils
import requests

from aodh.evaluator import threshold
from aodh.i18n import _

LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('gnocchi_url',
               deprecated_group="alarm",
               default="http://localhost:8041",
               help='URL to Gnocchi.'),
]


class GnocchiThresholdEvaluator(threshold.ThresholdEvaluator):

    def __init__(self, conf):
        super(threshold.ThresholdEvaluator, self).__init__(conf)
        self.gnocchi_url = conf.gnocchi_url

    def _get_headers(self, content_type="application/json"):
        return {
            'Content-Type': content_type,
            'X-Auth-Token': self.ks_client.auth_token,
        }

    def _statistics(self, alarm, start, end):
        """Retrieve statistics over the current window."""
        method = 'get'
        req = {
            'url': self.gnocchi_url + "/v1",
            'headers': self._get_headers(),
            'params': {
                'aggregation': alarm.rule['aggregation_method'],
                'start': start,
                'end': end,
            }
        }

        if alarm.type == 'gnocchi_aggregation_by_resources_threshold':
            method = 'post'
            req['url'] += "/aggregation/resource/%s/metric/%s" % (
                alarm.rule['resource_type'], alarm.rule['metric'])
            req['data'] = alarm.rule['query']
            # FIXME(sileht): In case of a heat autoscaling stack decide to
            # delete an instance, the gnocchi metrics associated to this
            # instance will be no more updated and when the alarm will ask
            # for the aggregation, gnocchi will raise a 'No overlap' exception.
            # So temporary set 'needed_overlap' to 0 to disable the
            # gnocchi checks about missing points. For more detail see:
            #   https://bugs.launchpad.net/gnocchi/+bug/1479429
            req['params']['needed_overlap'] = 0

        elif alarm.type == 'gnocchi_aggregation_by_metrics_threshold':
            req['url'] += "/aggregation/metric"
            req['params']['metric'] = alarm.rule['metrics']

        elif alarm.type == 'gnocchi_resources_threshold':
            req['url'] += "/resource/%s/%s/metric/%s/measures" % (
                alarm.rule['resource_type'],
                alarm.rule['resource_id'], alarm.rule['metric'])

        LOG.debug('stats query %s', req['url'])
        try:
            r = getattr(requests, method)(**req)
        except Exception:
            LOG.exception(_('alarm stats retrieval failed'))
            return []
        if int(r.status_code / 100) != 2:
            LOG.exception(_('alarm stats retrieval failed: %s') % r.text)
            return []
        else:
            return jsonutils.loads(r.text)

    @staticmethod
    def _sanitize(alarm, statistics):
        """Return the datapoints that correspond to the alarm granularity"""
        # TODO(sileht): if there's no direct match, but there is an archive
        # policy with granularity that's an even divisor or the period,
        # we could potentially do a mean-of-means (or max-of-maxes or whatever,
        # but not a stddev-of-stddevs).
        # TODO(sileht): support alarm['exclude_outliers']
        LOG.debug('sanitize stats %s', statistics)
        statistics = [stats[2] for stats in statistics
                      if stats[1] == alarm.rule['granularity']]
        statistics = statistics[-alarm.rule['evaluation_periods']:]
        LOG.debug('pruned statistics to %d', len(statistics))
        return statistics
