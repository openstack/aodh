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

"""add index for enabled and type

Revision ID: f8c31b1ffe11
Revises: bb07adac380
Create Date: 2016-06-02 19:39:42.495020

"""

# revision identifiers, used by Alembic.
revision = 'f8c31b1ffe11'
down_revision = 'bb07adac380'
branch_labels = None
depends_on = None

from alembic import op


def upgrade():
    op.create_index(
        'ix_alarm_enabled', 'alarm', ['enabled'], unique=False)
    op.create_index(
        'ix_alarm_type', 'alarm', ['type'], unique=False)
