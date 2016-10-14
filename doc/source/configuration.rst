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
