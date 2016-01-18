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
from oslo_serialization import jsonutils
import pecan
import wsme
from wsme import types as wtypes

from aodh.api.controllers.v2 import base
from aodh.api.controllers.v2 import utils as v2_utils
from aodh import keystone_client


class GnocchiUnavailable(Exception):
    code = 503


class AlarmGnocchiThresholdRule(base.AlarmRule):
    comparison_operator = base.AdvEnum('comparison_operator', str,
                                       'lt', 'le', 'eq', 'ne', 'ge', 'gt',
                                       default='eq')
    "The comparison against the alarm threshold"

    threshold = wsme.wsattr(float, mandatory=True)
    "The threshold of the alarm"

    aggregation_method = wsme.wsattr(wtypes.text, mandatory=True)
    "The aggregation_method to compare to the threshold"

    evaluation_periods = wsme.wsattr(wtypes.IntegerType(minimum=1), default=1)
    "The number of historical periods to evaluate the threshold"

    granularity = wsme.wsattr(wtypes.IntegerType(minimum=1), default=60)
    "The time range in seconds over which query"

    @classmethod
    def validate_alarm(cls, alarm):
        alarm_rule = getattr(alarm, "%s_rule" % alarm.type)
        aggregation_method = alarm_rule.aggregation_method
        if aggregation_method not in cls._get_aggregation_methods():
            raise base.ClientSideError(
                'aggregation_method should be in %s not %s' % (
                    cls._get_aggregation_methods(), aggregation_method))

    # NOTE(sileht): once cachetools is in the requirements
    # enable it
    # @cachetools.ttl_cache(maxsize=1, ttl=600)
    @staticmethod
    def _get_aggregation_methods():
        conf = pecan.request.cfg
        gnocchi_client = client.Client(
            '1', keystone_client.get_session(conf),
            interface=conf.service_credentials.interface,
            region_name=conf.service_credentials.region_name,
            endpoint_override=conf.gnocchi_url)

        try:
            return gnocchi_client.capabilities.list().get(
                'aggregation_methods', [])
        except exceptions.ClientException as e:
            raise base.ClientSideError(e.message, status_code=e.code)
        except Exception as e:
            raise GnocchiUnavailable(e)


class MetricOfResourceRule(AlarmGnocchiThresholdRule):
    metric = wsme.wsattr(wtypes.text, mandatory=True)
    "The name of the metric"

    resource_id = wsme.wsattr(wtypes.text, mandatory=True)
    "The id of a resource"

    resource_type = wsme.wsattr(wtypes.text, mandatory=True)
    "The resource type"

    def as_dict(self):
        rule = self.as_dict_from_keys(['granularity', 'comparison_operator',
                                       'threshold', 'aggregation_method',
                                       'evaluation_periods',
                                       'metric',
                                       'resource_id',
                                       'resource_type'])
        return rule

    @classmethod
    def validate_alarm(cls, alarm):
        super(MetricOfResourceRule,
              cls).validate_alarm(alarm)

        conf = pecan.request.cfg
        gnocchi_client = client.Client(
            '1', keystone_client.get_session(conf),
            interface=conf.service_credentials.interface,
            region_name=conf.service_credentials.region_name,
            endpoint_override=conf.gnocchi_url)

        rule = alarm.gnocchi_resources_threshold_rule
        try:
            gnocchi_client.resource.get(rule.resource_type,
                                        rule.resource_id)
        except exceptions.ClientException as e:
            raise base.ClientSideError(e.message, status_code=e.code)
        except Exception as e:
            raise GnocchiUnavailable(e)


class AggregationMetricByResourcesLookupRule(AlarmGnocchiThresholdRule):
    metric = wsme.wsattr(wtypes.text, mandatory=True)
    "The name of the metric"

    query = wsme.wsattr(wtypes.text, mandatory=True)
    ('The query to filter the metric, Don\'t forget to filter out '
     'deleted resources (example: {"and": [{"=": {"ended_at": null}}, ...]}), '
     'Otherwise Gnocchi will try to create the aggregate against obsolete '
     'resources')

    resource_type = wsme.wsattr(wtypes.text, mandatory=True)
    "The resource type"

    def as_dict(self):
        rule = self.as_dict_from_keys(['granularity', 'comparison_operator',
                                       'threshold', 'aggregation_method',
                                       'evaluation_periods',
                                       'metric',
                                       'query',
                                       'resource_type'])
        return rule

    @classmethod
    def validate_alarm(cls, alarm):
        super(AggregationMetricByResourcesLookupRule,
              cls).validate_alarm(alarm)

        rule = alarm.gnocchi_aggregation_by_resources_threshold_rule

        # check the query string is a valid json
        try:
            query = jsonutils.loads(rule.query)
        except ValueError:
            raise wsme.exc.InvalidInput('rule/query', rule.query)

        # Scope the alarm to the project id if needed
        auth_project = v2_utils.get_auth_project(alarm.project_id)
        if auth_project:
            query = {"and": [{"=": {"created_by_project_id": auth_project}},
                             query]}
            rule.query = jsonutils.dumps(query)

        conf = pecan.request.cfg
        gnocchi_client = client.Client(
            '1', keystone_client.get_session(conf),
            interface=conf.service_credentials.interface,
            region_name=conf.service_credentials.region_name,
            endpoint_override=conf.gnocchi_url)

        try:
            gnocchi_client.metric.aggregation(
                metrics=rule.metric,
                query=query,
                aggregation=rule.aggregation_method,
                needed_overlap=0,
                resource_type=rule.resource_type)
        except exceptions.ClientException as e:
            raise base.ClientSideError(e.message, status_code=e.code)
        except Exception as e:
            raise GnocchiUnavailable(e)


class AggregationMetricsByIdLookupRule(AlarmGnocchiThresholdRule):
    metrics = wsme.wsattr([wtypes.text], mandatory=True)
    "A list of metric Ids"

    def as_dict(self):
        rule = self.as_dict_from_keys(['granularity', 'comparison_operator',
                                       'threshold', 'aggregation_method',
                                       'evaluation_periods',
                                       'metrics'])
        return rule
