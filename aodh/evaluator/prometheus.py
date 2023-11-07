#
# Copyright 2023 Red Hat, Inc
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

from observabilityclient import client

from aodh.evaluator import threshold
from aodh import keystone_client


LOG = log.getLogger(__name__)
OPTS = [
    cfg.BoolOpt('prometheus_disable_rbac',
                default=False,
                help='Disable RBAC for Prometheus evaluator.'),
]


class PrometheusBase(threshold.ThresholdEvaluator):
    def __init__(self, conf):
        super(PrometheusBase, self).__init__(conf)
        self._set_obsclient(conf)
        self._no_rbac = conf.prometheus_disable_rbac

    def _set_obsclient(self, conf):
        session = keystone_client.get_session(conf)
        opts = {'interface': conf.service_credentials.interface,
                'region_name': conf.service_credentials.region_name}
        self._prom = client.Client('1', session, adapter_options=opts)

    def _get_metric_data(self, query):
        LOG.debug(f'Querying Prometheus instance on: {query}')
        return self._prom.query.query(query, disable_rbac=self._no_rbac)


class PrometheusEvaluator(PrometheusBase):

    def _sanitize(self, metric_data):
        sanitized = [float(m.value) for m in metric_data]
        LOG.debug(f'Sanited Prometheus metric data: {metric_data}'
                  f' to statistics: {sanitized}')
        return sanitized

    def evaluate_rule(self, alarm_rule):
        """Evaluate alarm rule.

        :returns: state, trending state, statistics, number of samples outside
        threshold and reason
        """
        metrics = self._get_metric_data(alarm_rule['query'])
        if not metrics:
            LOG.warning("Empty result fetched from Prometheus for query"
                        f" {alarm_rule['query']}")

        statistics = self._sanitize(metrics)
        if not statistics:
            raise threshold.InsufficientDataError('datapoints are unknown',
                                                  statistics)
        return self._process_statistics(alarm_rule, statistics)

    def _unknown_reason_data(self, alarm, statistics):
        LOG.warning(f'Transfering alarm {alarm} on unknown reason')
        last = None if not statistics else statistics[-1]
        return self._reason_data('unknown', len(statistics), last)
