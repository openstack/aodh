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

.. note::
   Please notice, MongoDB requires pymongo_ to be installed on the system. The
   required minimum version of pymongo is 2.4.
..


SQLalchemy-supported DBs
------------------------

   The recommended Aodh storage backend is any SQLAlchemy-supported
   database (`PostgreSQL` or `MySQL`).

   In case of SQL-based database backends, you need to create a `aodh`
   database first and then initialise it by running::

    aodh-dbsync

   To use MySQL as the storage backend, change the 'database' section in
   aodh.conf as follows::

    [database]
    connection = mysql+pymysql://username:password@host/aodh?charset=utf8


MongoDB
-------

   Follow the instructions to install the MongoDB_ package for your operating
   system, then start the service. The required minimum version of MongoDB is 2.4.

   To use MongoDB as the storage backend, change the 'database' section in
   aodh.conf as follows::

    [database]
    connection = mongodb://username:password@host:27017/aodh

   If MongoDB is configured in replica set mode, add `?replicaSet=` in your
   connection URL::

    [database]
    connection = mongodb://username:password@host:27017/aodh?replicaSet=foobar


HBase
-----

   HBase backend is implemented to use HBase Thrift interface, therefore it is
   mandatory to have the HBase Thrift server installed and running. To start
   the Thrift server, please run the following command::

    ${HBASE_HOME}/bin/hbase thrift start

   The implementation uses `HappyBase`_, which is a wrapper library used to
   interact with HBase via Thrift protocol. You can verify the thrift
   connection by running a quick test from a client::

    import happybase

    conn = happybase.Connection(host=$hbase-thrift-server, port=9090, table_prefix=None)
    print conn.tables() # this returns a list of HBase tables in your HBase server

   .. note::
      HappyBase version 0.5 or greater is required. Additionally, version 0.7
      is not currently supported.
   ..

   In case of HBase, the needed database tables (`project`, `user`, `resource`,
   `meter`, `alarm`, `alarm_h`) should be created manually with `f` column
   family for each one.

   To use HBase as the storage backend, change the 'database' section in
   aodh.conf as follows::

    [database]
    connection = hbase://hbase-thrift-host:9090


.. _HappyBase: http://happybase.readthedocs.org/en/latest/index.html#
.. _MongoDB: http://www.mongodb.org/
.. _pymongo: https://pypi.python.org/pypi/pymongo/



