#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 IBM Corp.
# Copyright 2013 eNovance <licensing@enovance.com>
# Copyright Ericsson AB 2013. All rights reserved
# Copyright 2014 Hewlett-Packard Company
# Copyright 2015 Huawei Technologies Co., Ltd.
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

import ast
import datetime
import functools
import inspect

from oslo_utils import strutils
from oslo_utils import timeutils
import pecan
import wsme
from wsme import types as wtypes

from aodh.i18n import _


operation_kind = ('lt', 'le', 'eq', 'ne', 'ge', 'gt')
operation_kind_enum = wtypes.Enum(str, *operation_kind)


class ClientSideError(wsme.exc.ClientSideError):
    def __init__(self, error, status_code=400):
        pecan.response.translatable_error = error
        super().__init__(error, status_code)


class ProjectNotAuthorized(ClientSideError):
    def __init__(self, id, aspect='project'):
        params = dict(aspect=aspect, id=id)
        super().__init__(
            _("Not Authorized to access %(aspect)s %(id)s") % params,
            status_code=401)


class AdvEnum(wtypes.wsproperty):
    """Handle default and mandatory for wtypes.Enum."""
    def __init__(self, name, *args, **kwargs):
        self._name = '_advenum_%s' % name
        self._default = kwargs.pop('default', None)
        mandatory = kwargs.pop('mandatory', False)
        enum = wtypes.Enum(*args, **kwargs)
        super().__init__(datatype=enum, fget=self._get,
                         fset=self._set, mandatory=mandatory)

    def _get(self, parent):
        if hasattr(parent, self._name):
            value = getattr(parent, self._name)
            return value or self._default
        return self._default

    def _set(self, parent, value):
        try:
            if self.datatype.validate(value):
                setattr(parent, self._name, value)
        except ValueError as e:
            raise wsme.exc.InvalidInput(self._name.replace('_advenum_', '', 1),
                                        value, e)


class Base(wtypes.DynamicBase):
    _wsme_attributes = []

    @classmethod
    def from_db_model(cls, m):
        return cls(**(m.as_dict()))

    @classmethod
    def from_db_and_links(cls, m, links):
        return cls(links=links, **(m.as_dict()))

    def as_dict(self, db_model):
        valid_keys = inspect.getfullargspec(db_model.__init__)[0]
        if 'self' in valid_keys:
            valid_keys.remove('self')
        return self.as_dict_from_keys(valid_keys)

    def as_dict_from_keys(self, keys):
        return {k: getattr(self, k)
                for k in keys
                if hasattr(self, k) and
                getattr(self, k) != wsme.Unset}

    def to_dict(self):
        d = {}
        for attr in self._wsme_attributes:
            attr_val = getattr(self, attr.name)
            if not isinstance(attr_val, wtypes.UnsetType):
                d[attr.name] = attr_val
        return d


class Query(Base):
    """Query filter."""

    # The data types supported by the query.
    _supported_types = ['integer', 'float', 'string', 'boolean', 'datetime']

    # Functions to convert the data field to the correct type.
    _type_converters = {'integer': int,
                        'float': float,
                        'boolean': functools.partial(
                            strutils.bool_from_string, strict=True),
                        'string': str,
                        'datetime': timeutils.parse_isotime}

    _op = None  # provide a default

    def get_op(self):
        return self._op or 'eq'

    def set_op(self, value):
        self._op = value

    field = wsme.wsattr(wtypes.text, mandatory=True)
    "The name of the field to test"

    # op = wsme.wsattr(operation_kind, default='eq')
    # this ^ doesn't seem to work.
    op = wsme.wsproperty(operation_kind_enum, get_op, set_op)
    "The comparison operator. Defaults to 'eq'."

    value = wsme.wsattr(wtypes.text, mandatory=True)
    "The value to compare against the stored data"

    type = wtypes.text
    "The data type of value to compare against the stored data"

    def __repr__(self):
        # for logging calls
        return '<Query {!r} {} {!r} {}>'.format(self.field,
                                                self.op,
                                                self.value,
                                                self.type)

    @classmethod
    def sample(cls):
        return cls(field='resource_id',
                   op='eq',
                   value='bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
                   type='string'
                   )

    def as_dict(self):
        return self.as_dict_from_keys(['field', 'op', 'type', 'value'])

    def get_value(self, forced_type=None):
        """Convert metadata value to the specified data type.

        This method is called during metadata query to help convert the
        querying metadata to the data type specified by user. If there is no
        data type given, the metadata will be parsed by ast.literal_eval to
        try to do a smart converting.

        NOTE (flwang) Using "_" as prefix to avoid an InvocationError raised
        from wsmeext/sphinxext.py. It's OK to call it outside the Query class.
        Because the "public" side of that class is actually the outside of the
        API, and the "private" side is the API implementation. The method is
        only used in the API implementation, so it's OK.

        :returns: metadata value converted with the specified data type.
        """
        type = forced_type or self.type
        try:
            converted_value = self.value
            if not type:
                try:
                    converted_value = ast.literal_eval(self.value)
                except (ValueError, SyntaxError):
                    # Unable to convert the metadata value automatically
                    # let it default to self.value
                    pass
            else:
                if type not in self._supported_types:
                    # Types must be explicitly declared so the
                    # correct type converter may be used. Subclasses
                    # of Query may define _supported_types and
                    # _type_converters to define their own types.
                    raise TypeError()
                converted_value = self._type_converters[type](self.value)
                if isinstance(converted_value, datetime.datetime):
                    converted_value = timeutils.normalize_time(converted_value)
        except ValueError:
            msg = (_('Unable to convert the value %(value)s'
                     ' to the expected data type %(type)s.') %
                   {'value': self.value, 'type': type})
            raise ClientSideError(msg)
        except TypeError:
            msg = (_('The data type %(type)s is not supported. The supported'
                     ' data type list is: %(supported)s') %
                   {'type': type, 'supported': self._supported_types})
            raise ClientSideError(msg)
        except Exception:
            msg = (_('Unexpected exception converting %(value)s to'
                     ' the expected data type %(type)s.') %
                   {'value': self.value, 'type': type})
            raise ClientSideError(msg)
        return converted_value


class AlarmNotFound(ClientSideError):
    def __init__(self, alarm, auth_project):
        if not auth_project:
            msg = _('Alarm %s not found') % alarm
        else:
            msg = _('Alarm %(alarm_id)s not found in project %'
                    '(project)s') % {
                        'alarm_id': alarm, 'project': auth_project}
        super().__init__(msg, status_code=404)


class AlarmRule(Base):
    """Base class Alarm Rule extension and wsme.types."""
    @staticmethod
    def validate_alarm(alarm):
        pass

    @staticmethod
    def create_hook(alarm):
        pass

    @staticmethod
    def update_hook(alarm):
        pass
