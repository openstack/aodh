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

"""
SQLAlchemy models for aodh data.
"""
import json

from oslo_utils import timeutils
import six
from sqlalchemy import Column, String, Index, Boolean, Text, DateTime
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import TypeDecorator


class JSONEncodedDict(TypeDecorator):
    """Represents an immutable structure as a json-encoded string."""

    impl = Text

    @staticmethod
    def process_bind_param(value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    @staticmethod
    def process_result_value(value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class TimestampUTC(TypeDecorator):
    """Represents a timestamp precise to the microsecond."""

    impl = DateTime

    def load_dialect_impl(self, dialect):
        if dialect.name == 'mysql':
            return dialect.type_descriptor(mysql.DATETIME(fsp=6))
        return self.impl


class AodhBase(object):
    """Base class for Aodh Models."""
    __table_args__ = {'mysql_charset': "utf8",
                      'mysql_engine': "InnoDB"}
    __table_initialized__ = False

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def update(self, values):
        """Make the model object behave like a dict."""
        for k, v in six.iteritems(values):
            setattr(self, k, v)


Base = declarative_base(cls=AodhBase)


class Alarm(Base):
    """Define Alarm data."""
    __tablename__ = 'alarm'
    __table_args__ = (
        Index('ix_alarm_user_id', 'user_id'),
        Index('ix_alarm_project_id', 'project_id'),
        Index('ix_alarm_enabled', 'enabled'),
        Index('ix_alarm_type', 'type'),
    )
    alarm_id = Column(String(128), primary_key=True)
    enabled = Column(Boolean)
    name = Column(Text)
    type = Column(String(50))
    severity = Column(String(50))
    description = Column(Text)
    timestamp = Column(TimestampUTC, default=lambda: timeutils.utcnow())

    user_id = Column(String(128))
    project_id = Column(String(128))

    state = Column(String(255))
    state_reason = Column(Text)
    state_timestamp = Column(TimestampUTC,
                             default=lambda: timeutils.utcnow())

    ok_actions = Column(JSONEncodedDict)
    alarm_actions = Column(JSONEncodedDict)
    insufficient_data_actions = Column(JSONEncodedDict)
    repeat_actions = Column(Boolean)

    rule = Column(JSONEncodedDict)
    time_constraints = Column(JSONEncodedDict)


class AlarmChange(Base):
    """Define AlarmChange data."""
    __tablename__ = 'alarm_history'
    __table_args__ = (
        Index('ix_alarm_history_alarm_id', 'alarm_id'),
    )
    event_id = Column(String(128), primary_key=True)
    alarm_id = Column(String(128))
    on_behalf_of = Column(String(128))
    project_id = Column(String(128))
    user_id = Column(String(128))
    type = Column(String(20))
    detail = Column(Text)
    timestamp = Column(TimestampUTC, default=lambda: timeutils.utcnow())
    severity = Column(String(50))
