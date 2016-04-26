..
      Copyright 2012 New Dream Network (DreamHost)
      Copyright 2013 eNovance

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

==========
 Glossary
==========

.. glossary::

   alarm
     An action triggered whenever a meter reaches a certain threshold.

   API server
     HTTP REST API service for Aodh.

   ceilometer
     From Wikipedia [#]_:

       A ceilometer is a device that uses a laser or other light
       source to determine the height of a cloud base.

   http callback
     HTTP callback is used for calling a predefined URL, whenever an
     alarm has been set off. The payload of the request contains
     all the details of why the alarm was triggered.

   log
     Logging is one of the alarm actions that is useful mostly for debugging,
     it stores the alarms in a log file.

   zaqar
     According to `Zaqar Developer Documentation`_:

       Zaqar is a multi-tenant cloud messaging and notification service for web
       and mobile developers.

   project
     The OpenStack tenant or project.

   resource
     The OpenStack entity being metered (e.g. instance, volume, image, etc).

   user
     An OpenStack user.

.. [#] http://en.wikipedia.org/wiki/Ceilometer
.. _Zaqar Developer Documentation: http://docs.openstack.org/developer/zaqar/
