# Copyright 2019 Catalyst Cloud Ltd.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""Add evaluate_timestamp column to alarm table

Revision ID: 006
Revises: 6ae0d05d9451
Create Date: 2019-12-05 11:23:42.379029
"""

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '6ae0d05d9451'

from alembic import op
from oslo_utils import timeutils
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'alarm',
        sa.Column('evaluate_timestamp', sa.DateTime(), nullable=True,
                  server_default=str(timeutils.utcnow()))
    )
