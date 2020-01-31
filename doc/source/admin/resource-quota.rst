..
      Copyright (c) 2020 Catalyst Cloud Limited

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

=========================
Resource Quota Management
=========================

The amount of resources(e.g. alarms) that could be created by each OpenStack
project is controlled by quota. The default resource quota for each project is
set in Aodh config file as follows unless changed by the cloud administrator
via Quota API.

.. code-block:: ini

    [api]
    user_alarm_quota = -1
    project_alarm_quota = -1
    alarm_max_actions = -1

user_alarm_quota
  The default alarm quota for an openstack user, default is unlimited.
  Sometimes the alarm creation request satisfies the project quota but fails
  the user quota.

project_alarm_quota
  The default alarm quota for an openstack project, default is unlimited. The
  cloud administrator can change project quota using Quota API, see examples
  below.

alarm_max_actions
  The maximum number of alarm actions could be created per alarm, default is
  unlimited.


Quota API
---------
Aodh Quota API is aiming for multi-tenancy support. By default, only the admin
user is able to change the resource quota for projects as defined by the
default policy rule 'telemetry:update_quotas'. User alarm quota and alarm
action quota are not supported in Quota API.

An HTTP request example using ``httpie`` command:

.. code-block:: console

    cat <<EOF | http post v2/quotas X-Auth-Token:$token
    {
      "project_id": "8aecc55977714e898281c24260747d78",
      "quotas": [
        {
          "resource": "alarms",
          "limit": 30
        }
      ]
    }
    EOF