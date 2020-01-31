# Copyright 2020 Catalyst Cloud LTD.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
from oslo_log import log
import pecan
from pecan import rest
import wsme
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from aodh.api.controllers.v2 import base
from aodh.api import rbac

LOG = log.getLogger(__name__)
ALLOWED_RESOURCES = ('alarms',)


class Quota(base.Base):
    resource = wtypes.wsattr(wtypes.Enum(str, *ALLOWED_RESOURCES),
                             mandatory=True)
    limit = wsme.wsattr(wtypes.IntegerType(minimum=-1), mandatory=True)


class Quotas(base.Base):
    project_id = wsme.wsattr(wtypes.text, mandatory=True)
    quotas = [Quota]


class QuotasController(rest.RestController):
    """Quota API controller."""

    @wsme_pecan.wsexpose(Quotas, str, ignore_extra_args=True)
    def get_all(self, project_id=None):
        """Get resource quotas of a project.

        - If no project given, get requested user's quota.
        - Admin user can get resource quotas of any project.
        """
        request_project = pecan.request.headers.get('X-Project-Id')
        project_id = project_id if project_id else request_project
        is_admin = rbac.is_admin(pecan.request.headers)

        if project_id != request_project and not is_admin:
            raise base.ProjectNotAuthorized(project_id)

        LOG.debug('Getting resource quotas for project %s', project_id)

        db_quotas = pecan.request.storage.get_quotas(project_id=project_id)

        if len(db_quotas) == 0:
            project_alarm_quota = pecan.request.cfg.api.project_alarm_quota
            quotas = [{'resource': 'alarms', 'limit': project_alarm_quota}]
            db_quotas = pecan.request.storage.set_quotas(project_id, quotas)

        quotas = [Quota.from_db_model(i) for i in db_quotas]
        return Quotas(project_id=project_id, quotas=quotas)

    @wsme_pecan.wsexpose(Quotas, body=Quotas, status_code=201)
    def post(self, body):
        """Create or update quota."""
        rbac.enforce('update_quotas', pecan.request.headers,
                     pecan.request.enforcer, {})

        params = body.to_dict()
        project_id = params['project_id']

        input_quotas = []
        for i in params.get('quotas', []):
            input_quotas.append(i.to_dict())

        db_quotas = pecan.request.storage.set_quotas(project_id, input_quotas)
        quotas = [Quota.from_db_model(i) for i in db_quotas]

        return Quotas(project_id=project_id, quotas=quotas)

    @wsme_pecan.wsexpose(None, str, status_code=204)
    def delete(self, project_id):
        """Delete quotas for the given project."""
        rbac.enforce('delete_quotas', pecan.request.headers,
                     pecan.request.enforcer, {})
        pecan.request.storage.delete_quotas(project_id)
