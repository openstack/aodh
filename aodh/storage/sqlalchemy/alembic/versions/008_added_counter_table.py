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

"""added_counter_table

Revision ID: 008
Revises: 007
Create Date: 2025-01-15 10:28:02.087788

"""

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'alarm_counter',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('alarm_id', sa.String(length=128), nullable=False),
        sa.Column('project_id', sa.String(length=128), nullable=False),
        sa.Column('state', sa.String(length=128), nullable=False),
        sa.Column('value', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['alarm_id'],
            ['alarm.alarm_id'],
            name='alarm_fkey_ref',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('alarm_id', 'project_id', 'state')
    )
    op.create_index(
        'ix_alarm_counter_alarm_id',
        'alarm_counter',
        ['alarm_id'],
        unique=False
    )
    op.create_index(
        'ix_alarm_counter_project_id',
        'alarm_counter',
        ['project_id'],
        unique=False
    )
    op.create_index(
        'ix_alarm_counter_state',
        'alarm_counter',
        ['state'],
        unique=False
    )
