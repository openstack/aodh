#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
"""Base classes for storage engines
"""
import copy

import aodh
from aodh.utils import get_func_valid_keys


def update_nested(original_dict, updates):
    """Updates the leaf nodes in a nest dict.

     Updates occur without replacing entire sub-dicts.
    """
    dict_to_update = copy.deepcopy(original_dict)
    for key, value in updates.items():
        if isinstance(value, dict):
            sub_dict = update_nested(dict_to_update.get(key, {}), value)
            dict_to_update[key] = sub_dict
        else:
            dict_to_update[key] = updates[key]
    return dict_to_update


class Model(object):
    """base class for storage api models."""

    def __init__(self, **kwds):
        self.fields = list(kwds)
        for k, v in kwds.items():
            setattr(self, k, v)

    def as_dict(self):
        d = {}
        for f in self.fields:
            v = getattr(self, f)
            if isinstance(v, Model):
                v = v.as_dict()
            elif isinstance(v, list) and v and isinstance(v[0], Model):
                v = [sub.as_dict() for sub in v]
            d[f] = v
        return d

    def __eq__(self, other):
        return self.as_dict() == other.as_dict()

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def get_field_names(cls):
        fields = get_func_valid_keys(cls.__init__)
        return set(fields) - set(["self"])


class Connection(object):
    """Base class for alarm storage system connections."""

    # A dictionary representing the capabilities of this driver.
    CAPABILITIES = {
        'alarms': {'query': {'simple': False,
                             'complex': False},
                   'history': {'query': {'simple': False,
                                         'complex': False}}},
    }

    STORAGE_CAPABILITIES = {
        'storage': {'production_ready': False},
    }

    def __init__(self, conf):
        pass

    @staticmethod
    def upgrade():
        """Migrate the database to `version` or the most recent version."""

    @staticmethod
    def get_alarms(*args, **kwargs):
        """Yields a lists of alarms that match filters."""
        raise aodh.NotImplementedError('Alarms not implemented')

    @staticmethod
    def create_alarm(alarm):
        """Create an alarm. Returns the alarm as created.

        :param alarm: The alarm to create.
        """
        raise aodh.NotImplementedError('Alarms not implemented')

    @staticmethod
    def update_alarm(alarm):
        """Update alarm."""
        raise aodh.NotImplementedError('Alarms not implemented')

    @staticmethod
    def delete_alarm(alarm_id):
        """Delete an alarm and its history data."""
        raise aodh.NotImplementedError('Alarms not implemented')

    @staticmethod
    def get_alarm_changes(alarm_id, on_behalf_of,
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
        :param severity: Optional change severity
        :param start_timestamp: Optional modified timestamp start range
        :param start_timestamp_op: Optional timestamp start range operation
        :param end_timestamp: Optional modified timestamp end range
        :param end_timestamp_op: Optional timestamp end range operation
        :param pagination: Pagination parameters.
        """
        raise aodh.NotImplementedError('Alarm history not implemented')

    @staticmethod
    def record_alarm_change(alarm_change):
        """Record alarm change event."""
        raise aodh.NotImplementedError('Alarm history not implemented')

    @staticmethod
    def clear():
        """Clear database."""

    @staticmethod
    def query_alarms(filter_expr=None, orderby=None, limit=None):
        """Return an iterable of model.Alarm objects.

        :param filter_expr: Filter expression for query.
        :param orderby: List of field name and direction pairs for order by.
        :param limit: Maximum number of results to return.
        """

        raise aodh.NotImplementedError('Complex query for alarms '
                                       'is not implemented.')

    @staticmethod
    def query_alarm_history(filter_expr=None, orderby=None, limit=None):
        """Return an iterable of model.AlarmChange objects.

        :param filter_expr: Filter expression for query.
        :param orderby: List of field name and direction pairs for order by.
        :param limit: Maximum number of results to return.
        """

        raise aodh.NotImplementedError('Complex query for alarms '
                                       'history is not implemented.')

    @classmethod
    def get_capabilities(cls):
        """Return an dictionary with the capabilities of each driver."""
        return cls.CAPABILITIES

    @classmethod
    def get_storage_capabilities(cls):
        """Return a dictionary representing the performance capabilities.

        This is needed to evaluate the performance of each driver.
        """
        return cls.STORAGE_CAPABILITIES

    @staticmethod
    def clear_expired_alarm_history_data(ttl, max_count=None):
        """Clear expired alarm history data from the backend storage system.

        Clearing occurs according to the time-to-live.

        :param ttl: Number of seconds to keep alarm history records for.
        :param max_count: Number of records to delete.
        """
        raise aodh.NotImplementedError('Clearing alarm history '
                                       'not implemented')

    @staticmethod
    def get_quotas(project_id):
        """Get resource quota for the given project."""
        raise aodh.NotImplementedError('Getting resource quota not '
                                       'implemented')

    @staticmethod
    def set_quotas(project_id, quotas):
        """Set resource quota for the given user."""
        raise aodh.NotImplementedError('Setting resource quota not '
                                       'implemented')

    @staticmethod
    def delete_quotas(project_id):
        raise aodh.NotImplementedError('Deleting resource quota not '
                                       'implemented')
