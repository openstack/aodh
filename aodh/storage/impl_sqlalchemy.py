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

"""SQLAlchemy storage backend."""
import copy
import datetime
import os.path

from alembic import command
from alembic import config
from alembic import migration
from oslo_db.sqlalchemy import enginefacade
from oslo_db.sqlalchemy import utils as oslo_sql_utils
from oslo_log import log
from oslo_utils import importutils
from oslo_utils import timeutils
import sqlalchemy
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy.engine import url as sqlalchemy_url
from sqlalchemy import func
from sqlalchemy.orm import exc

import aodh
from aodh import storage
from aodh.storage import base
from aodh.storage import models as alarm_api_models
from aodh.storage.sqlalchemy import models
from aodh.storage.sqlalchemy import utils as sql_utils


osprofiler_sqlalchemy = importutils.try_import('osprofiler.sqlalchemy')

LOG = log.getLogger(__name__)

AVAILABLE_CAPABILITIES = {
    'alarms': {'query': {'simple': True,
                         'complex': True},
               'history': {'query': {'simple': True,
                                     'complex': True}}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


def apply_filters(query, model, **filters):
    filter_dict = {}

    for key, value in filters.items():
        column_attr = getattr(model, key)

        if isinstance(value, dict):
            if 'in' in value:
                query = query.filter(column_attr.in_(value['in']))
            elif 'nin' in value:
                query = query.filter(~column_attr.in_(value['nin']))
            elif 'ne' in value:
                query = query.filter(column_attr != value['ne'])
            elif 'gt' in value:
                query = query.filter(column_attr > value['gt'])
            elif 'ge' in value:
                query = query.filter(column_attr >= value['ge'])
            elif 'lt' in value:
                query = query.filter(column_attr < value['lt'])
            elif 'le' in value:
                query = query.filter(column_attr <= value['le'])
            elif 'eq' in value:
                query = query.filter(column_attr == value['eq'])
            elif 'has' in value:
                like_pattern = '%{0}%'.format(value['has'])
                query = query.filter(column_attr.like(like_pattern))
        else:
            filter_dict[key] = value

    if filter_dict:
        query = query.filter_by(**filter_dict)

    return query


class Connection(base.Connection):
    """Put the data into a SQLAlchemy database. """
    CAPABILITIES = base.update_nested(base.Connection.CAPABILITIES,
                                      AVAILABLE_CAPABILITIES)
    STORAGE_CAPABILITIES = base.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )

    def __init__(self, conf, url):
        # Set max_retries to 0, since oslo.db in certain cases may attempt
        # to retry making the db connection retried max_retries ^ 2 times
        # in failure case and db reconnection has already been implemented
        # in storage.__init__.get_connection_from_config function
        options = dict(conf.database.items())
        options['max_retries'] = 0
        # FIXME(stephenfin): Remove this (and ideally use of
        # LegacyEngineFacade) asap since it's not compatible with SQLAlchemy
        # 2.0
        options['autocommit'] = True
        # oslo.db doesn't support options defined by Aodh
        for opt in storage.OPTS:
            options.pop(opt.name, None)
        self._engine_facade = enginefacade.LegacyEngineFacade(
            self.dress_url(url),
            **options)

        if osprofiler_sqlalchemy:
            osprofiler_sqlalchemy.add_tracing(sqlalchemy,
                                              self._engine_facade.get_engine(),
                                              'db')
        self.conf = conf

    @staticmethod
    def dress_url(url):
        # If no explicit driver has been set, we default to pymysql
        if url.startswith("mysql://"):
            url = sqlalchemy_url.make_url(url)
            url = url.set(drivername="mysql+pymysql")
            return str(url)
        return url

    def disconnect(self):
        self._engine_facade.get_engine().dispose()

    def _get_alembic_config(self):
        cfg = config.Config(
            "%s/sqlalchemy/alembic/alembic.ini" % os.path.dirname(__file__))
        cfg.set_main_option('sqlalchemy.url',
                            self.conf.database.connection.replace("%", "%%"))
        return cfg

    def upgrade(self, nocreate=False):
        cfg = self._get_alembic_config()
        cfg.conf = self.conf
        if nocreate:
            command.upgrade(cfg, "head")
        else:
            engine = self._engine_facade.get_engine()
            ctxt = migration.MigrationContext.configure(engine.connect())
            current_version = ctxt.get_current_revision()
            if current_version is None:
                models.Base.metadata.create_all(engine, checkfirst=False)
                command.stamp(cfg, "head")
            else:
                command.upgrade(cfg, "head")

    def clear(self):
        engine = self._engine_facade.get_engine()
        for table in reversed(models.Base.metadata.sorted_tables):
            engine.execute(table.delete())
        engine.dispose()

    def _retrieve_data(self, filter_expr, orderby, limit, table):
        if limit == 0:
            return []

        session = self._engine_facade.get_session()
        engine = self._engine_facade.get_engine()
        query = session.query(table)
        transformer = sql_utils.QueryTransformer(table, query,
                                                 dialect=engine.dialect.name)
        if filter_expr is not None:
            transformer.apply_filter(filter_expr)

        transformer.apply_options(orderby,
                                  limit)

        retrieve = {models.Alarm: self._retrieve_alarms,
                    models.AlarmChange: self._retrieve_alarm_history}
        return retrieve[table](transformer.get_query())

    @staticmethod
    def _row_to_alarm_model(row):
        return alarm_api_models.Alarm(
            alarm_id=row.alarm_id,
            enabled=row.enabled,
            type=row.type,
            name=row.name,
            description=row.description,
            timestamp=row.timestamp,
            user_id=row.user_id,
            project_id=row.project_id,
            state=row.state,
            state_timestamp=row.state_timestamp,
            state_reason=row.state_reason,
            ok_actions=row.ok_actions,
            alarm_actions=row.alarm_actions,
            insufficient_data_actions=(row.insufficient_data_actions),
            rule=row.rule,
            time_constraints=row.time_constraints,
            repeat_actions=row.repeat_actions,
            severity=row.severity,
            evaluate_timestamp=row.evaluate_timestamp
        )

    def _retrieve_alarms(self, query):
        return [self._row_to_alarm_model(x) for x in query.all()]

    @staticmethod
    def _get_pagination_query(session, query, pagination, api_model, model):
        if not pagination.get('sort'):
            pagination['sort'] = api_model.DEFAULT_SORT
        marker = None
        if pagination.get('marker'):
            key_attr = getattr(model, api_model.PRIMARY_KEY)
            marker_query = copy.copy(query)
            marker_query = marker_query.filter(
                key_attr == pagination['marker'])
            try:
                marker = marker_query.limit(1).one()
            except exc.NoResultFound:
                raise storage.InvalidMarker(
                    'Marker %s not found.' % pagination['marker'])
        limit = pagination.get('limit')
        # we sort by "severity" by its semantic than its alphabetical
        # order when "severity" specified in sorts.
        for sort_key, sort_dir in pagination['sort'][::-1]:
            if sort_key == 'severity':
                engine = session.connection()
                if engine.dialect.name != "mysql":
                    raise aodh.NotImplementedError
                sort_dir_func = {'asc': asc, 'desc': desc}[sort_dir]
                query = query.order_by(sort_dir_func(
                    func.field(getattr(model, sort_key), 'low',
                               'moderate', 'critical')))
                pagination['sort'].remove((sort_key, sort_dir))

        sort_keys = [s[0] for s in pagination['sort']]
        sort_dirs = [s[1] for s in pagination['sort']]
        return oslo_sql_utils.paginate_query(
            query, model, limit, sort_keys, sort_dirs=sort_dirs, marker=marker)

    def get_alarms(self, meter=None, pagination=None, **kwargs):
        """Yields a lists of alarms that match filters."""
        pagination = pagination or {}
        session = self._engine_facade.get_session()
        query = session.query(models.Alarm)
        query = apply_filters(query, models.Alarm, **kwargs)
        query = self._get_pagination_query(
            session, query, pagination, alarm_api_models.Alarm, models.Alarm)

        alarms = self._retrieve_alarms(query)

        # TODO(cmart): improve this by using sqlalchemy.func factory
        if meter is not None:
            alarms = filter(lambda row:
                            row.rule.get('meter_name', None) == meter,
                            alarms)

        return alarms

    def create_alarm(self, alarm):
        """Create an alarm.

        :param alarm: The alarm to create.
        """
        session = self._engine_facade.get_session()
        with session.begin():
            alarm_row = models.Alarm(alarm_id=alarm.alarm_id)
            alarm_row.update(alarm.as_dict())
            session.add(alarm_row)

        return self._row_to_alarm_model(alarm_row)

    def update_alarm(self, alarm):
        """Update an alarm.

        :param alarm: the new Alarm to update
        """
        session = self._engine_facade.get_session()
        with session.begin():
            count = session.query(models.Alarm).filter(
                models.Alarm.alarm_id == alarm.alarm_id).update(
                    alarm.as_dict())
            if not count:
                raise storage.AlarmNotFound(alarm.alarm_id)
        return alarm

    def delete_alarm(self, alarm_id):
        """Delete an alarm and its history data.

        :param alarm_id: ID of the alarm to delete
        """
        session = self._engine_facade.get_session()
        with session.begin():
            session.query(models.Alarm).filter(
                models.Alarm.alarm_id == alarm_id).delete()
            # FIXME(liusheng): we should use delete cascade
            session.query(models.AlarmChange).filter(
                models.AlarmChange.alarm_id == alarm_id).delete()

    @staticmethod
    def _row_to_alarm_change_model(row):
        return alarm_api_models.AlarmChange(event_id=row.event_id,
                                            alarm_id=row.alarm_id,
                                            type=row.type,
                                            detail=row.detail,
                                            user_id=row.user_id,
                                            project_id=row.project_id,
                                            on_behalf_of=row.on_behalf_of,
                                            timestamp=row.timestamp,
                                            severity=row.severity)

    def query_alarms(self, filter_expr=None, orderby=None, limit=None):
        """Yields a lists of alarms that match filter."""
        return self._retrieve_data(filter_expr, orderby, limit, models.Alarm)

    def _retrieve_alarm_history(self, query):
        return (self._row_to_alarm_change_model(x) for x in query.all())

    def query_alarm_history(self, filter_expr=None, orderby=None, limit=None):
        """Return an iterable of model.AlarmChange objects."""
        return self._retrieve_data(filter_expr,
                                   orderby,
                                   limit,
                                   models.AlarmChange)

    def get_alarm_changes(self, alarm_id, on_behalf_of,
                          user=None, project=None, alarm_type=None,
                          severity=None, start_timestamp=None,
                          start_timestamp_op=None, end_timestamp=None,
                          end_timestamp_op=None, pagination=None):
        """Yields list of AlarmChanges describing alarm history

        Changes are always sorted in reverse order of occurrence, given
        the importance of currency.

        Segregation for non-administrative users is done on the basis
        of the on_behalf_of parameter. This allows such users to have
        visibility on both the changes initiated by themselves directly
        (generally creation, rule changes, or deletion) and also on those
        changes initiated on their behalf by the alarming service (state
        transitions after alarm thresholds are crossed).

        :param alarm_id: ID of alarm to return changes for
        :param on_behalf_of: ID of tenant to scope changes query (None for
                             administrative user, indicating all projects)
        :param user: Optional ID of user to return changes for
        :param project: Optional ID of project to return changes for
        :param alarm_type: Optional change type
        :param severity: Optional alarm severity
        :param start_timestamp: Optional modified timestamp start range
        :param start_timestamp_op: Optional timestamp start range operation
        :param end_timestamp: Optional modified timestamp end range
        :param end_timestamp_op: Optional timestamp end range operation
        :param pagination: Pagination query parameters.
        """
        pagination = pagination or {}
        session = self._engine_facade.get_session()
        query = session.query(models.AlarmChange)
        query = query.filter(models.AlarmChange.alarm_id == alarm_id)

        if on_behalf_of is not None:
            query = query.filter(
                models.AlarmChange.on_behalf_of == on_behalf_of)
        if user is not None:
            query = query.filter(models.AlarmChange.user_id == user)
        if project is not None:
            query = query.filter(models.AlarmChange.project_id == project)
        if alarm_type is not None:
            query = query.filter(models.AlarmChange.type == alarm_type)
        if severity is not None:
            query = query.filter(models.AlarmChange.severity == severity)
        if start_timestamp:
            if start_timestamp_op == 'gt':
                query = query.filter(
                    models.AlarmChange.timestamp > start_timestamp)
            else:
                query = query.filter(
                    models.AlarmChange.timestamp >= start_timestamp)
        if end_timestamp:
            if end_timestamp_op == 'le':
                query = query.filter(
                    models.AlarmChange.timestamp <= end_timestamp)
            else:
                query = query.filter(
                    models.AlarmChange.timestamp < end_timestamp)

        query = self._get_pagination_query(
            session, query, pagination, alarm_api_models.AlarmChange,
            models.AlarmChange)
        return self._retrieve_alarm_history(query)

    def record_alarm_change(self, alarm_change):
        """Record alarm change event."""
        session = self._engine_facade.get_session()
        with session.begin():
            alarm_change_row = models.AlarmChange(
                event_id=alarm_change['event_id'])
            alarm_change_row.update(alarm_change)
            session.add(alarm_change_row)

    def clear_expired_alarm_history_data(self, ttl, max_count=100):
        """Clear expired alarm history data from the backend storage system.

        Clearing occurs according to the time-to-live.

        :param ttl: Number of seconds to keep alarm history records for.
        :param max_count: Number of records to delete.
        """
        session = self._engine_facade.get_session()
        with session.begin():
            end = timeutils.utcnow() - datetime.timedelta(seconds=ttl)
            alarm_history_q = (session.query(models.AlarmChange.event_id)
                               .filter(models.AlarmChange.timestamp < end))
            event_ids = [i[0] for i in alarm_history_q.limit(max_count)]
            deleted_rows = session.query(models.AlarmChange).filter(
                models.AlarmChange.event_id.in_(event_ids)
            ).delete(synchronize_session="fetch")
            LOG.info("%d alarm histories are removed from database",
                     deleted_rows)

    def conditional_update(self, model, values, expected_values, filters=None):
        """Compare-and-swap conditional update SQLAlchemy implementation."""
        filters = filters or {}
        filters.update(expected_values)

        session = self._engine_facade.get_session()
        query = session.query(model)
        if filters:
            query = query.filter_by(**filters)

        update_args = {'synchronize_session': False}

        result = query.update(values, **update_args)
        return 0 != result

    @staticmethod
    def _row_to_quota_model(row):
        return alarm_api_models.Quota(
            project_id=row.project_id,
            resource=row.resource,
            limit=row.limit,
        )

    def _retrieve_quotas(self, query):
        return [self._row_to_quota_model(x) for x in query.all()]

    def get_quotas(self, project_id):
        """Get resource quota for the given project."""
        filters = {'project_id': project_id}
        session = self._engine_facade.get_session()
        query = session.query(models.Quota).filter_by(**filters)
        return self._retrieve_quotas(query)

    def set_quotas(self, project_id, quotas):
        """Set resource quota for the given user."""
        session = self._engine_facade.get_session()

        with session.begin():
            for q in quotas:
                values = {
                    'project_id': project_id,
                    'resource': q['resource'],
                }

                quota = session.query(models.Quota).filter_by(**values).first()
                if not quota:
                    new_quota = models.Quota(project_id=project_id,
                                             resource=q['resource'],
                                             limit=q['limit'])
                    session.add(new_quota)
                else:
                    values['limit'] = q['limit']
                    quota.update(values.copy())

        filters = {'project_id': project_id}
        query = session.query(models.Quota).filter_by(**filters)
        return self._retrieve_quotas(query)

    def delete_quotas(self, project_id):
        filters = {'project_id': project_id}
        session = self._engine_facade.get_session()
        session.query(models.Quota).filter_by(**filters).delete()
