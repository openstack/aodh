# -*- encoding: utf-8 -*-
#
# Copyright 2016 OpenStack Foundation
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

"""precisetimestamp_to_datetime

Revision ID: 367aadf5485f
Revises: f8c31b1ffe11
Create Date: 2016-09-19 16:43:34.379029

"""

# revision identifiers, used by Alembic.
revision = '367aadf5485f'
down_revision = 'f8c31b1ffe11'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy import func

from aodh.storage.sqlalchemy import models


def upgrade():
    bind = op.get_bind()
    if bind and bind.engine.name == "mysql":
        # NOTE(jd) So that crappy engine that is MySQL does not have "ALTER
        # TABLE … USING …". We need to copy everything and convert…
        for table_name, column_name in (("alarm", "timestamp"),
                                        ("alarm", "state_timestamp"),
                                        ("alarm_history", "timestamp")):
            existing_type = sa.types.DECIMAL(
                precision=20, scale=6, asdecimal=True)
            existing_col = sa.Column(
                column_name,
                existing_type,
                nullable=True)
            temp_col = sa.Column(
                column_name + "_ts",
                models.TimestampUTC(),
                nullable=True)
            op.add_column(table_name, temp_col)
            t = sa.sql.table(table_name, existing_col, temp_col)
            op.execute(t.update().values(
                **{column_name + "_ts": func.from_unixtime(existing_col)}))
            op.drop_column(table_name, column_name)
            op.alter_column(table_name,
                            column_name + "_ts",
                            nullable=True,
                            type_=models.TimestampUTC(),
                            existing_nullable=True,
                            existing_type=existing_type,
                            new_column_name=column_name)
