# Copyright 2015 OpenStack Foundation
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

"""initial base

Revision ID: 12fe8fac9fe4
Revises:
Create Date: 2015-07-28 17:38:37.022899

"""

# revision identifiers, used by Alembic.
revision = '12fe8fac9fe4'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy import types

import aodh.storage.sqlalchemy.models


class PreciseTimestamp(types.TypeDecorator):
    """Represents a timestamp precise to the microsecond."""

    impl = sa.DateTime

    def load_dialect_impl(self, dialect):
        if dialect.name == 'mysql':
            return dialect.type_descriptor(
                types.DECIMAL(precision=20,
                              scale=6,
                              asdecimal=True))
        return dialect.type_descriptor(self.impl)


def upgrade():
    op.create_table(
        'alarm_history',
        sa.Column('event_id', sa.String(length=128), nullable=False),
        sa.Column('alarm_id', sa.String(length=128), nullable=True),
        sa.Column('on_behalf_of', sa.String(length=128), nullable=True),
        sa.Column('project_id', sa.String(length=128), nullable=True),
        sa.Column('user_id', sa.String(length=128), nullable=True),
        sa.Column('type', sa.String(length=20), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('timestamp',
                  PreciseTimestamp(),
                  nullable=True),
        sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index(
        'ix_alarm_history_alarm_id', 'alarm_history', ['alarm_id'],
        unique=False)
    op.create_table(
        'alarm',
        sa.Column('alarm_id', sa.String(length=128), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('type', sa.String(length=50), nullable=True),
        sa.Column('severity', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('timestamp',
                  PreciseTimestamp(),
                  nullable=True),
        sa.Column('user_id', sa.String(length=128), nullable=True),
        sa.Column('project_id', sa.String(length=128), nullable=True),
        sa.Column('state', sa.String(length=255), nullable=True),
        sa.Column('state_timestamp',
                  PreciseTimestamp(),
                  nullable=True),
        sa.Column('ok_actions',
                  aodh.storage.sqlalchemy.models.JSONEncodedDict(),
                  nullable=True),
        sa.Column('alarm_actions',
                  aodh.storage.sqlalchemy.models.JSONEncodedDict(),
                  nullable=True),
        sa.Column('insufficient_data_actions',
                  aodh.storage.sqlalchemy.models.JSONEncodedDict(),
                  nullable=True),
        sa.Column('repeat_actions', sa.Boolean(), nullable=True),
        sa.Column('rule',
                  aodh.storage.sqlalchemy.models.JSONEncodedDict(),
                  nullable=True),
        sa.Column('time_constraints',
                  aodh.storage.sqlalchemy.models.JSONEncodedDict(),
                  nullable=True),
        sa.PrimaryKeyConstraint('alarm_id')
    )
    op.create_index(
        'ix_alarm_project_id', 'alarm', ['project_id'], unique=False)
    op.create_index(
        'ix_alarm_user_id', 'alarm', ['user_id'], unique=False)
