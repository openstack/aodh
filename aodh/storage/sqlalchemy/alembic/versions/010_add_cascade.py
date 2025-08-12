# Copyright 2025 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

"""Add cascade

Revision ID: 010
Revises: 009
Create Date: 2025-07-19 12:09:36.651705

"""

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None

from alembic import op
from sqlalchemy.engine import reflection


def upgrade():
    inspector = reflection.Inspector.from_engine(op.get_bind())

    fks_to_cascade = {
        'alarm_counter': 'alarm_id',
        'alarm_history': 'alarm_id'
    }

    for table, column in fks_to_cascade.items():
        fk_constraints = inspector.get_foreign_keys(table)
        for fk in fk_constraints:
            if column in fk['constrained_columns']:
                op.drop_constraint(
                    constraint_name=fk['name'],
                    table_name=table,
                    type_='foreignkey'
                )
                op.create_foreign_key(
                    constraint_name=fk['name'],
                    source_table=table,
                    referent_table=fk['referred_table'],
                    local_cols=fk['constrained_columns'],
                    remote_cols=fk['referred_columns'],
                    ondelete='CASCADE'
                )
