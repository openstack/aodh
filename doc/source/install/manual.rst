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

=====================
 Installing Manually
=====================


Storage Backend Installation
============================

This step is a prerequisite for the collector, notification agent and API
services. You may use one of the listed database backends below to store
Aodh data.


The recommended Aodh storage backend is any SQLAlchemy-supported database
(`PostgreSQL` or `MySQL`). You need to create a `aodh` database first and then
initialise it by running::

 aodh-dbsync

To use MySQL as the storage backend, change the 'database' section in
aodh.conf as follows::

 [database]
 connection = mysql+pymysql://username:password@host/aodh?charset=utf8
