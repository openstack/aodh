.. _install-rdo:

Install and configure for Red Hat Enterprise Linux and CentOS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section describes how to install and configure the
Telemetry Alarming service, code-named aodh, on the controller node.

This section assumes that you already have a working OpenStack
environment with at least the following components installed:
Compute, Image Service, Identity.

.. include:: prereq-common.rst

Install and configure components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::

   Default configuration files vary by distribution. You might need to add
   these sections and options rather than modifying existing sections and
   options. Also, an ellipsis (...) in the configuration snippets indicates
   potential default configuration options that you should retain.

1. Install the packages:

   .. code-block:: console

      # yum install openstack-aodh-api \
        openstack-aodh-evaluator openstack-aodh-notifier \
        openstack-aodh-listener openstack-aodh-expirer \
        python-aodhclient

.. include:: configure-common.rst

Finalize installation
~~~~~~~~~~~~~~~~~~~~~

#. Start the Telemetry Alarming services and configure them to start
   when the system boots:

   .. code-block:: console

      # systemctl enable openstack-aodh-api.service \
        openstack-aodh-evaluator.service \
        openstack-aodh-notifier.service \
        openstack-aodh-listener.service
      # systemctl start openstack-aodh-api.service \
        openstack-aodh-evaluator.service \
        openstack-aodh-notifier.service \
        openstack-aodh-listener.service
