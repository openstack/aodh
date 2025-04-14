#
# Copyright 2014 OpenStack Foundation
#
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

from oslo_log import log

from aodh import service
from aodh import storage


LOG = log.getLogger(__name__)


def dbsync():
    conf = service.prepare_service()
    storage.get_connection_from_config(conf).upgrade()


def expirer():
    conf = service.prepare_service()

    if conf.database.alarm_history_time_to_live > 0:
        LOG.debug("Clearing expired alarm history data")
        conn = storage.get_connection_from_config(conf)
        max_count = conf.database.alarm_histories_delete_batch_size
        try:
            if max_count > 0:
                conn.clear_expired_alarm_history_data(
                    conf.database.alarm_history_time_to_live,
                    max_count)
            else:
                deleted = max_count = 100
                while deleted and deleted > 0:
                    deleted = conn.clear_expired_alarm_history_data(
                        conf.database.alarm_history_time_to_live,
                        max_count)
        except TypeError:
            LOG.warning("Storage driver does not support "
                        "'alarm_histories_delete_batch_size' config option.")
    else:
        LOG.info("Nothing to clean, database alarm history time to live "
                 "is disabled")
