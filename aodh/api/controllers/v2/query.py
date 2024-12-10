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

import copy
import json

import jsonschema
from oslo_log import log
from oslo_utils import timeutils
import pecan
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from aodh.api.controllers.v2 import alarms
from aodh.api.controllers.v2 import base
from aodh.api import rbac
from aodh.i18n import _
from aodh import profiler
from aodh.storage import models

LOG = log.getLogger(__name__)


class ComplexQuery(base.Base):
    """Holds a sample query encoded in json."""

    filter = wtypes.text
    "The filter expression encoded in json."

    orderby = wtypes.text
    "List of single-element dicts for specifing the ordering of the results."

    limit = int
    "The maximum number of results to be returned."

    @classmethod
    def sample(cls):
        return cls(filter='{"and": [{"and": [{"=": ' +
                          '{"counter_name": "cpu_util"}}, ' +
                          '{">": {"counter_volume": 0.23}}, ' +
                          '{"<": {"counter_volume": 0.26}}]}, ' +
                          '{"or": [{"and": [{">": ' +
                          '{"timestamp": "2013-12-01T18:00:00"}}, ' +
                          '{"<": ' +
                          '{"timestamp": "2013-12-01T18:15:00"}}]}, ' +
                          '{"and": [{">": ' +
                          '{"timestamp": "2013-12-01T18:30:00"}}, ' +
                          '{"<": ' +
                          '{"timestamp": "2013-12-01T18:45:00"}}]}]}]}',
                   orderby='[{"counter_volume": "ASC"}, ' +
                           '{"timestamp": "DESC"}]',
                   limit=42
                   )


def _list_to_regexp(items, regexp_prefix=""):
    regexp = ["^%s$" % item for item in items]
    regexp = regexp_prefix + "|".join(regexp)
    return regexp


@profiler.trace_cls('api')
class ValidatedComplexQuery(object):
    complex_operators = ["and", "or"]
    order_directions = ["asc", "desc"]
    simple_ops = ["=", "!=", "<", ">", "<=", "=<", ">=", "=>", "=~"]
    regexp_prefix = "(?i)"

    complex_ops = _list_to_regexp(complex_operators, regexp_prefix)
    simple_ops = _list_to_regexp(simple_ops, regexp_prefix)
    order_directions = _list_to_regexp(order_directions, regexp_prefix)

    timestamp_fields = ["timestamp", "state_timestamp"]

    def __init__(self, query, db_model, additional_name_mapping=None,
                 metadata_allowed=False):
        additional_name_mapping = additional_name_mapping or {}
        self.name_mapping = {"user": "user_id",
                             "project": "project_id"}
        self.name_mapping.update(additional_name_mapping)
        valid_keys = db_model.get_field_names()
        valid_keys = list(valid_keys) + list(self.name_mapping.keys())
        valid_fields = _list_to_regexp(valid_keys)

        if metadata_allowed:
            valid_filter_fields = valid_fields + r"|^metadata\.[\S]+$"
        else:
            valid_filter_fields = valid_fields

        schema_value = {
            "oneOf": [{"type": "string"},
                      {"type": "number"},
                      {"type": "boolean"}],
            "minProperties": 1,
            "maxProperties": 1}

        schema_value_in = {
            "type": "array",
            "items": {"oneOf": [{"type": "string"},
                                {"type": "number"}]},
            "minItems": 1}

        schema_field = {
            "type": "object",
            "patternProperties": {valid_filter_fields: schema_value},
            "additionalProperties": False,
            "minProperties": 1,
            "maxProperties": 1}

        schema_field_in = {
            "type": "object",
            "patternProperties": {valid_filter_fields: schema_value_in},
            "additionalProperties": False,
            "minProperties": 1,
            "maxProperties": 1}

        schema_leaf_in = {
            "type": "object",
            "patternProperties": {"(?i)^in$": schema_field_in},
            "additionalProperties": False,
            "minProperties": 1,
            "maxProperties": 1}

        schema_leaf_simple_ops = {
            "type": "object",
            "patternProperties": {self.simple_ops: schema_field},
            "additionalProperties": False,
            "minProperties": 1,
            "maxProperties": 1}

        schema_and_or_array = {
            "type": "array",
            "items": {"$ref": "#"},
            "minItems": 2}

        schema_and_or = {
            "type": "object",
            "patternProperties": {self.complex_ops: schema_and_or_array},
            "additionalProperties": False,
            "minProperties": 1,
            "maxProperties": 1}

        schema_not = {
            "type": "object",
            "patternProperties": {"(?i)^not$": {"$ref": "#"}},
            "additionalProperties": False,
            "minProperties": 1,
            "maxProperties": 1}

        self.schema = {
            "oneOf": [{"$ref": "#/definitions/leaf_simple_ops"},
                      {"$ref": "#/definitions/leaf_in"},
                      {"$ref": "#/definitions/and_or"},
                      {"$ref": "#/definitions/not"}],
            "minProperties": 1,
            "maxProperties": 1,
            "definitions": {"leaf_simple_ops": schema_leaf_simple_ops,
                            "leaf_in": schema_leaf_in,
                            "and_or": schema_and_or,
                            "not": schema_not}}

        self.orderby_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "patternProperties":
                    {valid_fields:
                        {"type": "string",
                         "pattern": self.order_directions}},
                "additionalProperties": False,
                "minProperties": 1,
                "maxProperties": 1}}

        self.original_query = query

    def validate(self, visibility_field):
        """Validates the query content and does the necessary conversions."""
        if self.original_query.filter is wtypes.Unset:
            self.filter_expr = None
        else:
            try:
                self.filter_expr = json.loads(self.original_query.filter)
                self._validate_filter(self.filter_expr)
            except (ValueError, jsonschema.exceptions.ValidationError) as e:
                raise base.ClientSideError(
                    _("Filter expression not valid: %s") % str(e))
            self._replace_isotime_with_datetime(self.filter_expr)
            self._convert_operator_to_lower_case(self.filter_expr)
            self._normalize_field_names_for_db_model(self.filter_expr)

        self._force_visibility(visibility_field)

        if self.original_query.orderby is wtypes.Unset:
            self.orderby = None
        else:
            try:
                self.orderby = json.loads(self.original_query.orderby)
                self._validate_orderby(self.orderby)
            except (ValueError, jsonschema.exceptions.ValidationError) as e:
                raise base.ClientSideError(
                    _("Order-by expression not valid: %s") % e)
            self._convert_orderby_to_lower_case(self.orderby)
            self._normalize_field_names_in_orderby(self.orderby)

        if self.original_query.limit is wtypes.Unset:
            self.limit = None
        else:
            self.limit = self.original_query.limit

        if self.limit is not None and self.limit <= 0:
            msg = _('Limit should be positive')
            raise base.ClientSideError(msg)

    @staticmethod
    def lowercase_values(mapping):
        """Converts the values in the mapping dict to lowercase."""
        items = mapping.items()
        for key, value in items:
            mapping[key] = value.lower()

    def _convert_orderby_to_lower_case(self, orderby):
        for orderby_field in orderby:
            self.lowercase_values(orderby_field)

    def _normalize_field_names_in_orderby(self, orderby):
        for orderby_field in orderby:
            self._replace_field_names(orderby_field)

    def _traverse_postorder(self, tree, visitor):
        op = list(tree.keys())[0]
        if op.lower() in self.complex_operators:
            for i, operand in enumerate(tree[op]):
                self._traverse_postorder(operand, visitor)
        if op.lower() == "not":
            self._traverse_postorder(tree[op], visitor)

        visitor(tree)

    def _check_cross_project_references(self, own_project_id,
                                        visibility_field):
        """Do not allow other than own_project_id."""
        def check_project_id(subfilter):
            op, value = list(subfilter.items())[0]
            if (op.lower() not in self.complex_operators
                    and list(value.keys())[0] == visibility_field
                    and value[visibility_field] != own_project_id):
                raise base.ProjectNotAuthorized(value[visibility_field])

        self._traverse_postorder(self.filter_expr, check_project_id)

    def _force_visibility(self, visibility_field):
        """Force visibility field.

        If the tenant is not admin insert an extra
        "and <visibility_field>=<tenant's project_id>" clause to the query.
        """
        authorized_project = rbac.get_limited_to_project(
            pecan.request, pecan.request.enforcer)
        is_admin = authorized_project is None
        if not is_admin:
            self._restrict_to_project(authorized_project, visibility_field)
            self._check_cross_project_references(authorized_project,
                                                 visibility_field)

    def _restrict_to_project(self, project_id, visibility_field):
        restriction = {"=": {visibility_field: project_id}}
        if self.filter_expr is None:
            self.filter_expr = restriction
        else:
            self.filter_expr = {"and": [restriction, self.filter_expr]}

    def _replace_isotime_with_datetime(self, filter_expr):
        def replace_isotime(subfilter):
            op, value = list(subfilter.items())[0]
            if op.lower() not in self.complex_operators:
                field = list(value.keys())[0]
                if field in self.timestamp_fields:
                    date_time = self._convert_to_datetime(subfilter[op][field])
                    subfilter[op][field] = date_time

        self._traverse_postorder(filter_expr, replace_isotime)

    def _normalize_field_names_for_db_model(self, filter_expr):
        def _normalize_field_names(subfilter):
            op, value = list(subfilter.items())[0]
            if op.lower() not in self.complex_operators:
                self._replace_field_names(value)
        self._traverse_postorder(filter_expr,
                                 _normalize_field_names)

    def _replace_field_names(self, subfilter):
        field, value = list(subfilter.items())[0]
        if field in self.name_mapping:
            del subfilter[field]
            subfilter[self.name_mapping[field]] = value
        if field.startswith("metadata."):
            del subfilter[field]
            subfilter["resource_" + field] = value

    @staticmethod
    def lowercase_keys(mapping):
        """Converts the values of the keys in mapping to lowercase."""
        loop_mapping = copy.deepcopy(mapping)
        items = loop_mapping.items()
        for key, value in items:
            del mapping[key]
            mapping[key.lower()] = value

    def _convert_operator_to_lower_case(self, filter_expr):
        self._traverse_postorder(filter_expr, self.lowercase_keys)

    @staticmethod
    def _convert_to_datetime(isotime):
        try:
            date_time = timeutils.parse_isotime(isotime)
            date_time = date_time.replace(tzinfo=None)
            return date_time
        except ValueError:
            LOG.exception("String %s is not a valid isotime", isotime)
            msg = _('Failed to parse the timestamp value %s') % isotime
            raise base.ClientSideError(msg)

    def _validate_filter(self, filter_expr):
        jsonschema.validate(filter_expr, self.schema)

    def _validate_orderby(self, orderby_expr):
        jsonschema.validate(orderby_expr, self.orderby_schema)


class QueryAlarmHistoryController(rest.RestController):
    """Provides complex query possibilities for alarm history."""
    @wsme_pecan.wsexpose([alarms.AlarmChange], body=ComplexQuery)
    def post(self, body):
        """Define query for retrieving AlarmChange data.

        :param body: Query rules for the alarm history to be returned.
        """
        target = rbac.target_from_segregation_rule(
            pecan.request, pecan.request.enforcer)
        rbac.enforce('query_alarm_history', pecan.request,
                     pecan.request.enforcer, target)

        query = ValidatedComplexQuery(body,
                                      models.AlarmChange)
        query.validate(visibility_field="on_behalf_of")
        conn = pecan.request.storage
        return [alarms.AlarmChange.from_db_model(s)
                for s in conn.query_alarm_history(query.filter_expr,
                                                  query.orderby,
                                                  query.limit)]


class QueryAlarmsController(rest.RestController):
    """Provides complex query possibilities for alarms."""
    history = QueryAlarmHistoryController()

    @wsme_pecan.wsexpose([alarms.Alarm], body=ComplexQuery)
    def post(self, body):
        """Define query for retrieving Alarm data.

        :param body: Query rules for the alarms to be returned.
        """

        target = rbac.target_from_segregation_rule(
            pecan.request, pecan.request.enforcer)
        rbac.enforce('query_alarm', pecan.request,
                     pecan.request.enforcer, target)

        query = ValidatedComplexQuery(body,
                                      models.Alarm)
        query.validate(visibility_field="project_id")
        conn = pecan.request.storage
        return [alarms.Alarm.from_db_model(s)
                for s in conn.query_alarms(query.filter_expr,
                                           query.orderby,
                                           query.limit)]


class QueryController(rest.RestController):

    alarms = QueryAlarmsController()
