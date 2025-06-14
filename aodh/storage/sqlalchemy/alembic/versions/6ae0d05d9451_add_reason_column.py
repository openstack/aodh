#
# Copyright 2017 OpenStack Foundation
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

"""add_reason_column

Revision ID: 6ae0d05d9451
Revises: 367aadf5485f
Create Date: 2017-06-05 16:42:42.379029

"""

# revision identifiers, used by Alembic.
revision = '6ae0d05d9451'
down_revision = '367aadf5485f'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('alarm', sa.Column('state_reason', sa.Text, nullable=True))
