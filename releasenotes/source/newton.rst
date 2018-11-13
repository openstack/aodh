=============================
 Newton Series Release Notes
=============================

3.0.3
=====

Bug Fixes
---------

.. releasenotes/notes/gnocchi-external-resource-owner-3fad253d30746b0d.yaml @ b'f87e0d05c4662c14c7a9f49a0a829cf9bf3edbdb'

- When an unprivileged user want to access to Gnocchi resources created by
  Ceilometer, that doesn't work because the filter scope the Gnocchi query to
  resource owner to the user. To fix we introduce a new configuration option
  "gnocchi_external_project_owner" set by default to "service". The new
  filter now allow two kind of Gnocchi resources:

  * owned by the user project
  * owned by "gnocchi_external_project_owner" and the orignal project_id of
    the resource is the user project.


3.0.0
=====

New Features
------------

.. releasenotes/notes/enable-aodh-service-multi-processes-67ed9a0b7fac69aa.yaml @ b'bb7d87f0538d69c2db8f316891217733a2b5a443'

- Enable aodh services, including aodh-evaluator, aodh-listener and aodh-notifier to run in multiple worker mode.
  New options are introduced corresponsively as [evaluator]workers, [listener]workers and [notifier]workers. They all default to 1.

.. releasenotes/notes/event-listener-batch-support-04e6ff159ef34d8c.yaml @ b'56f24bdad16c21fe7daa4502844fa9e8a976a232'

- Add support for batch processing of messages from queue. This will allow the aodh-listener to grab multiple event messages per thread to enable more efficient processing.

.. releasenotes/notes/fix-ssl-request-8107616b6a85a217.yaml @ b'788403b0f18c8e68e01485f3c21f71f06eb57198'

- A new option “rest_notifier_ca_bundle_certificate_path” has been added in the configuration file, set None as default value. If this option is present and SSL is used for alarm action the certificate path provided will be used as value of verify parameter in action request.

.. releasenotes/notes/ingestion-lag-2317725887287fbc.yaml @ b'b3874c47f1051d37ed839f4f8fffda2c77641f28'

- Allow to extends the alarm evaluation windows to compensate the reporting/ingestion lag.
  An new option is introduced additional_ingestion_lag defaulted to 0. It represents the number of seconds of the window extension.

.. releasenotes/notes/notifier-batch-listener-01796e2cb06344dd.yaml @ b'520425faf80cf2e0fb86cab216440df5550171c8'

- Add support for batch processing of messages from queue. This will allow the aodh-notifier to grab multiple messages per thread to enable more efficient processing.


Upgrade Notes
-------------

.. releasenotes/notes/add-a-data-migration-tool-daa14b0cb5d4cc62.yaml @ b'a096e57759c00b8f98499a36bf8a8854daa378ec'

- Add a tool for migrating alarm and alarm history data from NoSQL storage to SQL storage. The migration tool has been tested OK in devstack environment, but users need to be cautious with this, because the data migration between storage backends is a bit dangerous.

.. releasenotes/notes/event-listener-batch-support-04e6ff159ef34d8c.yaml @ b'56f24bdad16c21fe7daa4502844fa9e8a976a232'

- batch_size and batch_timeout configuration options are added to [listener] section of configuration. The batch_size controls the number of messages to grab before processing. Similarly, the batch_timeout defines the wait time before processing.

.. releasenotes/notes/notifier-batch-listener-01796e2cb06344dd.yaml @ b'520425faf80cf2e0fb86cab216440df5550171c8'

- batch_size and batch_timeout configuration options are added to [notifier] section of configuration. The batch_size controls the number of messages to grab before processing. Similarly, the batch_timeout defines the wait time before processing.

.. releasenotes/notes/support-combination-to-composite-conversion-3e688a6b7d01a57e.yaml @ b'050a7dcb344a5ee3ad0351f3a4c18e90078e782b'

- Add a tool for converting combination alarms to composite alarms, since we have deprecated the combination alarm support and recommend to use composite alarm to perform multiple conditions alarming.


Deprecation Notes
-----------------

.. releasenotes/notes/deprecate-combination-alarms-7ff26b73b61a0e59.yaml @ b'20abf3b1fb0190aa7c777f01844d062682ea41e1'

- The combination alarms are officially deprecated and disabled by default. Set api.enable_combination_alarms to True to enable them. Existing alarms will still be evaluated, but access to them via the API is linked to whether that configuration option is turned on or off. It's advised to use composite alarms instead.


Bug Fixes
---------

.. releasenotes/notes/fix-ssl-request-8107616b6a85a217.yaml @ b'788403b0f18c8e68e01485f3c21f71f06eb57198'

- [`bug 1582131 <https://bugs.launchpad.net/aodh/+bug/1582131>`_] Fix an issue with adding CA_BUNDLE certificate parth as value of "verify" parameter in SSL requests.

.. releasenotes/notes/partition-coordinator-improvement-ff1c257f69f120ac.yaml @ b'dd06bf9277774c56121be0b4878c8973f38e761d'

- [`bug 1575530 <https://bugs.launchpad.net/aodh/+bug/1575530>`_] Patch was added to fix and improve the partition coordinator, make sure the input tasks can be correctly distributed to partition members.


Other Notes
-----------

.. releasenotes/notes/remove-alarm-name-unique-constraint-4fb0b14f3ad46f0b.yaml @ b'413f83d79530140280eacc3c25ba980fbcc3c1f9'

- Alarm name unique constraint for each project has been removed.


