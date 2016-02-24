..
      Copyright 2012 New Dream Network, LLC (DreamHost)

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.


=============
Configuration
=============

Configure Aodh by editing `/etc/aodh/aodh.conf`.

No config file is provided with the source code, but one can be easily created
by running:

::

    tox -e genconfig

This command will create an `etc/aodh/aodh.conf` file which can be used as a
base for the default configuration file at `/etc/aodh/aodh.conf`.

For the list and description of configuration options that can be set for Aodh in
order to set up the services please see the
`Telemetry section <http://docs.openstack.org/trunk/config-reference/content/ch_configuring-openstack-telemetry.html>`_
in the OpenStack Manuals Configuration Reference.

HBase
===================

This storage implementation uses Thrift HBase interface. The default Thrift
connection settings should be changed to support using ConnectionPool in HBase.
To ensure proper configuration, please add the following lines to the
`hbase-site.xml` configuration file::

    <property>
      <name>hbase.thrift.minWorkerThreads</name>
      <value>200</value>
    </property>

For pure development purposes, you can use HBase from Apache_ or some other
vendor like Cloudera or Hortonworks. To verify your installation, you can use
the `list` command in `HBase shell`, to list the tables in your
HBase server, as follows::

    $ ${HBASE_HOME}/bin/hbase shell

    hbase> list

.. note::
    This driver has been tested against HBase 0.94.2/CDH 4.2.0,
    HBase 0.94.4/HDP 1.2, HBase 0.94.18/Apache, HBase 0.94.5/Apache,
    HBase 0.96.2/Apache and HBase 0.98.0/Apache.
    Versions earlier than 0.92.1 are not supported due to feature incompatibility.

To find out more about supported storage backends please take a look on the
:doc:`install/manual/` guide.

.. note::

    If you are changing the configuration on the fly to use HBase, as a storage
    backend, you will need to restart the Aodh services that use the
    database to allow the changes to take affect, i.e. the collector and API
    services.

.. _Apache: https://hbase.apache.org/book/quickstart.html
