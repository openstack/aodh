..
      Copyright 2012 Nicolas Barcet for Canonical
                2013 New Dream Network, LLC (DreamHost)

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

.. _installing_manually:

===================
Installing Manually
===================

Installing the API Server
=========================
There are two recommended ways to start api server:
 1. Starting API server through mod_wsgi_;
 2. Starting API server through: uwsgi_.

Not recommended, for testing purpose, we can also start api server by
aodh-api binary::

    aodh-api --port 8042 -- --config-file /etc/aodh/aodh.conf

Database configuration
======================

You can use any SQLAlchemy-supported DB such as  `PostgreSQL` or `MySQL`.
To use MySQL as the storage backend, change the 'database' section in
aodh.conf as follows::

    [database]
    connection = mysql+pymysql://username:password@host/aodh?charset=utf8

.. _mod_wsgi: ../install/mod_wsgi.html
.. _uwsgi: ../install/uwsgi.html
