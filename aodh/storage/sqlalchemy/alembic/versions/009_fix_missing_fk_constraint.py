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

"""Fix missing FK constraint

Revision ID: 009
Revises: 008
Create Date: 2025-07-18 23:45:50.411424

"""

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('alarm_history', 'alarm_id', nullable=False,
                    existing_type=sa.String(128), existing_nullable=True,
                    existing_server_default=False)
    op.create_foreign_key(
        constraint_name=None,
        source_table='alarm_history', referent_table='alarm',
        local_cols=['alarm_id'], remote_cols=['alarm_id'])
