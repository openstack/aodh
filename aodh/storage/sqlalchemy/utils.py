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
#

import operator

from sqlalchemy import and_
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import not_
from sqlalchemy import or_


class QueryTransformer(object):
    operators = {"=": operator.eq,
                 "<": operator.lt,
                 ">": operator.gt,
                 "<=": operator.le,
                 "=<": operator.le,
                 ">=": operator.ge,
                 "=>": operator.ge,
                 "!=": operator.ne,
                 "in": lambda field_name, values: field_name.in_(values),
                 "=~": lambda field, value: field.op("regexp")(value)}

    # operators which are different for different dialects
    dialect_operators = {'postgresql': {'=~': (lambda field, value:
                                               field.op("~")(value))}}

    complex_operators = {"or": or_,
                         "and": and_,
                         "not": not_}

    ordering_functions = {"asc": asc,
                          "desc": desc}

    def __init__(self, table, query, dialect='mysql'):
        self.table = table
        self.query = query
        self.dialect_name = dialect

    def _get_operator(self, op):
        return (self.dialect_operators.get(self.dialect_name, {}).get(op)
                or self.operators[op])

    def _handle_complex_op(self, complex_op, nodes):
        op = self.complex_operators[complex_op]
        if op == not_:
            nodes = [nodes]
        element_list = []
        for node in nodes:
            element = self._transform(node)
            element_list.append(element)
        return op(*element_list)

    def _handle_simple_op(self, simple_op, nodes):
        op = self._get_operator(simple_op)
        field_name, value = list(nodes.items())[0]
        return op(getattr(self.table, field_name), value)

    def _transform(self, sub_tree):
        operator, nodes = list(sub_tree.items())[0]
        if operator in self.complex_operators:
            return self._handle_complex_op(operator, nodes)
        else:
            return self._handle_simple_op(operator, nodes)

    def apply_filter(self, expression_tree):
        condition = self._transform(expression_tree)
        self.query = self.query.filter(condition)

    def apply_options(self, orderby, limit):
        self._apply_order_by(orderby)
        if limit is not None:
            self.query = self.query.limit(limit)

    def _apply_order_by(self, orderby):
        if orderby is not None:
            for field in orderby:
                attr, order = list(field.items())[0]
                ordering_function = self.ordering_functions[order]
                if attr == 'severity':
                    self.query = self.query.order_by(ordering_function(
                        func.field(getattr(self.table, attr), 'low',
                                   'moderate', 'critical')))
                else:
                    self.query = self.query.order_by(ordering_function(
                        getattr(self.table, attr)))
        else:
            self.query = self.query.order_by(desc(self.table.timestamp))

    def get_query(self):
        return self.query
