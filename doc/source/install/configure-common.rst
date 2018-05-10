2. Edit the ``/etc/aodh/aodh.conf`` file and complete the following actions:

   * In the ``[database]`` section, configure database access:

     .. code-block:: ini

        [database]
        ...
        connection = mysql+pymysql://aodh:AODH_DBPASS@controller/aodh

     Replace ``AODH_DBPASS`` with the password you chose for the
     Telemetry Alarming module database. You must escape special characters
     such as ``:``, ``/``, ``+``, and ``@`` in the connection string in accordance
     with `RFC2396 <https://www.ietf.org/rfc/rfc2396.txt>`_.

   * In the ``[DEFAULT]`` section,
     configure ``RabbitMQ`` message queue access:

     .. code-block:: ini

        [DEFAULT]
        ...
        transport_url = rabbit://openstack:RABBIT_PASS@controller

     Replace ``RABBIT_PASS`` with the password you chose for the
     ``openstack`` account in ``RabbitMQ``.

   * In the ``[DEFAULT]`` and ``[keystone_authtoken]`` sections,
     configure Identity service access:

     .. code-block:: ini

        [DEFAULT]
        ...
        auth_strategy = keystone

        [keystone_authtoken]
        ...
        www_authenticate_uri = http://controller:5000
        auth_url = http://controller:5000
        memcached_servers = controller:11211
        auth_type = password
        project_domain_id = default
        user_domain_id = default
        project_name = service
        username = aodh
        password = AODH_PASS

     Replace ``AODH_PASS`` with the password you chose for
     the ``aodh`` user in the Identity service.

   * In the ``[service_credentials]`` section, configure service credentials:

     .. code-block:: ini

        [service_credentials]
        ...
        auth_type = password
        auth_url = http://controller:5000/v3
        project_domain_id = default
        user_domain_id = default
        project_name = service
        username = aodh
        password = AODH_PASS
        interface = internalURL
        region_name = RegionOne

     Replace ``AODH_PASS`` with the password you chose for
     the ``aodh`` user in the Identity service.

.. todo:

   Workaround for https://bugs.launchpad.net/ubuntu/+source/aodh/+bug/1513599.

3. In order to initialize the database please run the ``aodh-dbsync`` script.
