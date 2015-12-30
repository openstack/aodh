#
# Copyright Ericsson AB 2013. All rights reserved
# Copyright 2015 Red Hat, Inc
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
"""Common functions for MongoDB backend
"""

import weakref

from oslo_log import log
from oslo_utils import netutils
import pymongo
import retrying

from aodh.i18n import _

LOG = log.getLogger(__name__)


def make_timestamp_range(start, end,
                         start_timestamp_op=None, end_timestamp_op=None):

    """Create the query document to find timestamps within that range.

    This is done by given two possible datetimes and their operations.
    By default, using $gte for the lower bound and $lt for the upper bound.
    """
    ts_range = {}

    if start:
        if start_timestamp_op == 'gt':
            start_timestamp_op = '$gt'
        else:
            start_timestamp_op = '$gte'
        ts_range[start_timestamp_op] = start

    if end:
        if end_timestamp_op == 'le':
            end_timestamp_op = '$lte'
        else:
            end_timestamp_op = '$lt'
        ts_range[end_timestamp_op] = end
    return ts_range


class ConnectionPool(object):

    def __init__(self):
        self._pool = {}

    def connect(self, url, max_retries, retry_interval):
        connection_options = pymongo.uri_parser.parse_uri(url)
        del connection_options['database']
        del connection_options['username']
        del connection_options['password']
        del connection_options['collection']
        pool_key = tuple(connection_options)

        if pool_key in self._pool:
            client = self._pool.get(pool_key)()
            if client:
                return client
        splitted_url = netutils.urlsplit(url)
        log_data = {'db': splitted_url.scheme,
                    'nodelist': connection_options['nodelist']}
        LOG.info(_('Connecting to %(db)s on %(nodelist)s') % log_data)
        try:
            client = MongoProxy(
                pymongo.MongoClient(url),
                max_retries,
                retry_interval,
            )
        except pymongo.errors.ConnectionFailure as e:
            LOG.warning(_('Unable to connect to the database server: '
                        '%(errmsg)s.') % {'errmsg': e})
            raise
        self._pool[pool_key] = weakref.ref(client)
        return client


class QueryTransformer(object):

    operators = {"<": "$lt",
                 ">": "$gt",
                 "<=": "$lte",
                 "=<": "$lte",
                 ">=": "$gte",
                 "=>": "$gte",
                 "!=": "$ne",
                 "in": "$in",
                 "=~": "$regex"}

    complex_operators = {"or": "$or",
                         "and": "$and"}

    ordering_functions = {"asc": pymongo.ASCENDING,
                          "desc": pymongo.DESCENDING}

    def transform_orderby(self, orderby):
        orderby_filter = []

        for field in orderby:
            field_name = list(field.keys())[0]
            ordering = self.ordering_functions[list(field.values())[0]]
            orderby_filter.append((field_name, ordering))
        return orderby_filter

    @staticmethod
    def _move_negation_to_leaf(condition):
        """Moves every not operator to the leafs.

        Moving is going by applying the De Morgan rules and annihilating
        double negations.
        """
        def _apply_de_morgan(tree, negated_subtree, negated_op):
            if negated_op == "and":
                new_op = "or"
            else:
                new_op = "and"

            tree[new_op] = [{"not": child}
                            for child in negated_subtree[negated_op]]
            del tree["not"]

        def transform(subtree):
            op = list(subtree.keys())[0]
            if op in ["and", "or"]:
                [transform(child) for child in subtree[op]]
            elif op == "not":
                negated_tree = subtree[op]
                negated_op = list(negated_tree.keys())[0]
                if negated_op == "and":
                    _apply_de_morgan(subtree, negated_tree, negated_op)
                    transform(subtree)
                elif negated_op == "or":
                    _apply_de_morgan(subtree, negated_tree, negated_op)
                    transform(subtree)
                elif negated_op == "not":
                    # two consecutive not annihilates themselves
                    value = list(negated_tree.values())[0]
                    new_op = list(value.keys())[0]
                    subtree[new_op] = negated_tree[negated_op][new_op]
                    del subtree["not"]
                    transform(subtree)

        transform(condition)

    def transform_filter(self, condition):
        # in Mongo not operator can only be applied to
        # simple expressions so we have to move every
        # not operator to the leafs of the expression tree
        self._move_negation_to_leaf(condition)
        return self._process_json_tree(condition)

    def _handle_complex_op(self, complex_op, nodes):
        element_list = []
        for node in nodes:
            element = self._process_json_tree(node)
            element_list.append(element)
        complex_operator = self.complex_operators[complex_op]
        op = {complex_operator: element_list}
        return op

    def _handle_not_op(self, negated_tree):
        # assumes that not is moved to the leaf already
        # so we are next to a leaf
        negated_op = list(negated_tree.keys())[0]
        negated_field = list(negated_tree[negated_op].keys())[0]
        value = negated_tree[negated_op][negated_field]
        if negated_op == "=":
            return {negated_field: {"$ne": value}}
        elif negated_op == "!=":
            return {negated_field: value}
        else:
            return {negated_field: {"$not":
                                    {self.operators[negated_op]: value}}}

    def _handle_simple_op(self, simple_op, nodes):
        field_name = list(nodes.keys())[0]
        field_value = list(nodes.values())[0]

        # no operator for equal in Mongo
        if simple_op == "=":
            op = {field_name: field_value}
            return op

        operator = self.operators[simple_op]
        op = {field_name: {operator: field_value}}
        return op

    def _process_json_tree(self, condition_tree):
        operator_node = list(condition_tree.keys())[0]
        nodes = list(condition_tree.values())[0]

        if operator_node in self.complex_operators:
            return self._handle_complex_op(operator_node, nodes)

        if operator_node == "not":
            negated_tree = condition_tree[operator_node]
            return self._handle_not_op(negated_tree)

        return self._handle_simple_op(operator_node, nodes)

MONGO_METHODS = set([typ for typ in dir(pymongo.collection.Collection)
                     if not typ.startswith('_')])
MONGO_METHODS.update(set([typ for typ in dir(pymongo.MongoClient)
                          if not typ.startswith('_')]))
MONGO_METHODS.update(set([typ for typ in dir(pymongo)
                          if not typ.startswith('_')]))


def _safe_mongo_call(max_retries, retry_interval):
    return retrying.retry(
        retry_on_exception=lambda e: isinstance(
            e, pymongo.errors.AutoReconnect),
        wait_fixed=retry_interval * 1000,
        stop_max_attempt_number=max_retries if max_retries >= 0 else None
    )


class MongoProxy(object):
    def __init__(self, conn, max_retries, retry_interval):
        self.conn = conn
        self.max_retries = max_retries
        self.retry_interval = retry_interval

    def __getitem__(self, item):
        """Create and return proxy around the method in the connection.

        :param item: name of the connection
        """
        return MongoProxy(self.conn[item])

    def find(self, *args, **kwargs):
        # We need this modifying method to return a CursorProxy object so that
        # we can handle the Cursor next function to catch the AutoReconnect
        # exception.
        return CursorProxy(self.conn.find(*args, **kwargs),
                           self.max_retries,
                           self.retry_interval)

    def __getattr__(self, item):
        """Wrap MongoDB connection.

        If item is the name of an executable method, for example find or
        insert, wrap this method to retry.
        Else wrap getting attribute with MongoProxy.
        """
        if item in ('name', 'database'):
            return getattr(self.conn, item)
        if item in MONGO_METHODS:
            return _safe_mongo_call(
                self.max_retries,
                self.retry_interval,
            )(getattr(self.conn, item))
        return MongoProxy(getattr(self.conn, item),
                          self.max_retries,
                          self.retry_interval)

    def __call__(self, *args, **kwargs):
        return self.conn(*args, **kwargs)


class CursorProxy(pymongo.cursor.Cursor):
    def __init__(self, cursor, max_retries, retry_interval):
        self.cursor = cursor
        self.next = _safe_mongo_call(
            max_retries, retry_interval)(self._next)

    def __getitem__(self, item):
        return self.cursor[item]

    def _next(self):
        """Wrap Cursor next method.

        This method will be executed before each Cursor next method call.
        """
        try:
            save_cursor = self.cursor.clone()
            return self.cursor.next()
        except pymongo.errors.AutoReconnect:
            self.cursor = save_cursor
            raise

    def __getattr__(self, item):
        return getattr(self.cursor, item)
