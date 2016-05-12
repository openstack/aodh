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


Aodh Sample Configuration File
==============================

Configure Aodh by editing /etc/aodh/aodh.conf.

No config file is provided with the source code, it will be created during
the installation. In case where no configuration file was installed, one
can be easily created by running::

    oslo-config-generator --config-file=/etc/aodh/aodh-config-generator.conf \
        --output-file=/etc/aodh/aodh.conf

The following is a sample Aodh configuration for adaptation and use. It is
auto-generated from Aodh when this documentation is built, and can also be
viewed in `file form <_static/aodh.conf.sample>`_.

.. note::

    As a developer, with full development tools, you can create a sample
    configuration file from any branch or commit. Just checkout to that
    branch or commit, run ``tox -e genconfig``, then `etc/aodh/aodh.conf`
    will be generated.

.. literalinclude:: _static/aodh.conf.sample
