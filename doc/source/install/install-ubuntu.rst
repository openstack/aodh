.. _install-ubuntu:

Install and configure for Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section describes how to install and configure the
Telemetry Alarming service, code-named aodh, on the controller node.

This section assumes that you already have a working OpenStack
environment with at least the following components installed:
Compute, Image Service, Identity.

.. include:: prereq-common.rst

Install and configure components
--------------------------------

.. note::

   Default configuration files vary by distribution. You might need to add
   these sections and options rather than modifying existing sections and
   options. Also, an ellipsis (...) in the configuration snippets indicates
   potential default configuration options that you should retain.

1. Install the packages:

   .. code-block:: console

      # apt-get install aodh-api aodh-evaluator aodh-notifier \
        aodh-listener aodh-expirer python-aodhclient

.. include:: configure-common.rst

Finalize installation
---------------------

#. Restart the Alarming services:

   .. code-block:: console

      # service aodh-api restart
      # service aodh-evaluator restart
      # service aodh-notifier restart
      # service aodh-listener restart
