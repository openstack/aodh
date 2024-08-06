#
# Copyright 2024 Red Hat, Inc
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


import collections
from oslo_log import log
import pecan
from pecan import rest
import wsmeext.pecan as wsme_pecan

from aodh.api.controllers.v2 import base
from aodh.api import rbac
from aodh import evaluator
from aodh.i18n import _
from aodh import profiler

LOG = log.getLogger(__name__)


class EvaluationResultOutput(base.Base):
    """A class for representing evaluation result data"""
    alarm_id = str
    project_id = str
    state_counters = {str: int}

    @classmethod
    def sample(cls):
        return cls(
            alarm_id="b8e17f58-089a-43fc-a96b-e9bcac4d4b53",
            project_id="2dd8edd6c8c24f49bf04670534f6b357",
            state_counters={
                "ok": 20,
                "insufficient data": 5,
                "alarm": 10,
            }
        )


class MetricsOutput(base.Base):
    """A class for representing data from metrics API endpoint"""

    evaluation_results = [EvaluationResultOutput]
    "The evaluation result counters"

    # This could be extended for other metrics in the future

    @classmethod
    def sample(cls):
        return cls(evaluation_results=[{
            "alarm_id": "b8e17f58-089a-43fc-a96b-e9bcac4d4b53",
            "project_id": "2dd8edd6c8c24f49bf04670534f6b357",
            "state_counters": {
                "ok": 20,
                "insufficient data": 5,
                "alarm": 10,
            }
        }])


@profiler.trace_cls('api')
class MetricsController(rest.RestController):
    """Manages the metrics api endpoint"""

    @staticmethod
    def group_counters(counters):
        result = collections.defaultdict(lambda: collections.defaultdict(dict))
        for c in counters:
            result[c.project_id][c.alarm_id][c.state] = c.value
        return result

    @wsme_pecan.wsexpose(MetricsOutput)
    def get_all(self):
        """Return all metrics"""
        if not pecan.request.cfg.enable_evaluation_results_metrics:
            raise base.ClientSideError(_(
                "metrics endpoint is disabled"
            ), 403)

        project_id = pecan.request.headers.get('X-Project-Id')
        target = {"project_id": project_id}

        rbac.enforce('get_metrics', pecan.request.headers,
                     pecan.request.enforcer, target)

        content = MetricsOutput()
        alarm_states = [evaluator.UNKNOWN, evaluator.OK, evaluator.ALARM]

        LOG.debug('Getting evaluation result counters from database')
        grouped_counters = self.group_counters(
            pecan.request.storage.get_alarm_counters(project_id=project_id)
        )
        evaluation_results = []
        for project, alarms in grouped_counters.items():
            for alarm, states in alarms.items():
                evaluation_results.append(
                    EvaluationResultOutput(
                        project_id=project,
                        alarm_id=alarm,
                        state_counters={
                            state: states.get(state.replace(" ", "_"), 0)
                            for state in alarm_states
                        }
                    )
                )

        content.evaluation_results = evaluation_results

        return content
