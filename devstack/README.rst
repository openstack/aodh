=========================
Enabling Aodh in DevStack
=========================

1. Download DevStack::

    git clone https://opendev.org/openstack/devstack.git
    cd devstack

2. Add this repo as an external repository in ``local.conf`` file::

    [[local|localrc]]
    enable_plugin aodh https://opendev.org/openstack/aodh

   To use stable branches, make sure devstack is on that branch, and specify
   the branch name to enable_plugin, for example::

    enable_plugin aodh https://opendev.org/openstack/aodh stable/mitaka

   There are some options, such as AODH_BACKEND, defined in
   ``aodh/devstack/settings``, they can be used to configure the installation
   of Aodh. If you don't want to use their default value, you can set a new
   one in ``local.conf``.

3. Run ``stack.sh``.
