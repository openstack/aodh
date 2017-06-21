Prerequisites
-------------

Before you install and configure the Telemetry service, you must create a
database, service credentials, and API endpoints.

#. To create the database, complete these steps:

   * Use the database access client to connect to
     the database server as the ``root`` user:

     .. code-block:: console

        $ mysql -u root -p

   * Create the ``aodh`` database:

     .. code-block:: console

        CREATE DATABASE aodh;

   * Grant proper access to the ``aodh`` database:

     .. code-block:: console

        GRANT ALL PRIVILEGES ON aodh.* TO 'aodh'@'localhost' \
          IDENTIFIED BY 'AODH_DBPASS';
        GRANT ALL PRIVILEGES ON aodh.* TO 'aodh'@'%' \
          IDENTIFIED BY 'AODH_DBPASS';

     Replace ``AODH_DBPASS`` with a suitable password.

   * Exit the database access client.

#. Source the ``admin`` credentials to gain access to admin-only
   CLI commands:

   .. code-block:: console

      $ . admin-openrc

#. To create the service credentials, complete these steps:

   * Create the ``aodh`` user:

     .. code-block:: console

        $ openstack user create --domain default \
          --password-prompt aodh
        User Password:
        Repeat User Password:
        +-----------+----------------------------------+
        | Field     | Value                            |
        +-----------+----------------------------------+
        | domain_id | e0353a670a9e496da891347c589539e9 |
        | enabled   | True                             |
        | id        | b7657c9ea07a4556aef5d34cf70713a3 |
        | name      | aodh                             |
        +-----------+----------------------------------+

   * Add the ``admin`` role to the ``aodh`` user:

     .. code-block:: console

        $ openstack role add --project service --user aodh admin

     .. note::

        This command provides no output.

   * Create the ``aodh`` service entity:

     .. code-block:: console

        $ openstack service create --name aodh \
          --description "Telemetry" alarming
        +-------------+----------------------------------+
        | Field       | Value                            |
        +-------------+----------------------------------+
        | description | Telemetry                        |
        | enabled     | True                             |
        | id          | 3405453b14da441ebb258edfeba96d83 |
        | name        | aodh                             |
        | type        | alarming                         |
        +-------------+----------------------------------+

#. Create the Alarming service API endpoints:

   .. code-block:: console

      $ openstack endpoint create --region RegionOne \
        alarming public http://controller:8042
        +--------------+----------------------------------+
        | Field        | Value                            |
        +--------------+----------------------------------+
        | enabled      | True                             |
        | id           | 340be3625e9b4239a6415d034e98aace |
        | interface    | public                           |
        | region       | RegionOne                        |
        | region_id    | RegionOne                        |
        | service_id   | 8c2c7f1b9b5049ea9e63757b5533e6d2 |
        | service_name | aodh                             |
        | service_type | alarming                         |
        | url          | http://controller:8042           |
        +--------------+----------------------------------+

      $ openstack endpoint create --region RegionOne \
        alarming internal http://controller:8042
        +--------------+----------------------------------+
        | Field        | Value                            |
        +--------------+----------------------------------+
        | enabled      | True                             |
        | id           | 340be3625e9b4239a6415d034e98aace |
        | interface    | internal                         |
        | region       | RegionOne                        |
        | region_id    | RegionOne                        |
        | service_id   | 8c2c7f1b9b5049ea9e63757b5533e6d2 |
        | service_name | aodh                             |
        | service_type | alarming                         |
        | url          | http://controller:8042           |
        +--------------+----------------------------------+

      $ openstack endpoint create --region RegionOne \
        alarming admin http://controller:8042
        +--------------+----------------------------------+
        | Field        | Value                            |
        +--------------+----------------------------------+
        | enabled      | True                             |
        | id           | 340be3625e9b4239a6415d034e98aace |
        | interface    | admin                            |
        | region       | RegionOne                        |
        | region_id    | RegionOne                        |
        | service_id   | 8c2c7f1b9b5049ea9e63757b5533e6d2 |
        | service_name | aodh                             |
        | service_type | alarming                         |
        | url          | http://controller:8042           |
        +--------------+----------------------------------+
