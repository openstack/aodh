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

==============================
Installing development sandbox
==============================

Configuring devstack
====================

.. index::
   double: installing; devstack

1. Download devstack_.

2. Create a ``local.conf`` file as input to devstack.

   .. note::

      ``local.conf`` replaces the former configuration file called ``localrc``.
      If you used localrc before, remove it to switch to using the new file.
      For further information see the `devstack configuration
      <https://docs.openstack.org/devstack/latest/configuration.html>`_.

3. The aodh services are not enabled by default, so they must be
   enabled in ``local.conf`` before running ``stack.sh``.

   This example ``local.conf`` file shows all of the settings required for
   aodh::

      [[local|localrc]]

      # Enable the aodh alarming services
      enable_plugin aodh https://opendev.org/openstack/aodh master

.. _devstack: https://docs.openstack.org/devstack/latest/
