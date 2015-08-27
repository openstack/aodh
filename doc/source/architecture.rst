.. _architecture:

=====================
 System Architecture
=====================

.. index::
   single: agent; architecture
   double: compute agent; architecture
   double: collector; architecture
   double: data store; architecture
   double: database; architecture
   double: API; architecture

High-Level Architecture
=======================

Each of Aodh's services are designed to scale horizontally. Additional
workers and nodes can be added depending on the expected load. It provides
daemons to evaluate and notify based on defined alarming rules.

Evaluating the data
===================

Alarming Service
----------------

The alarming component of Aodh, first delivered in the Havana
version, allows you to set alarms based on threshold evaluation for a
collection of samples. An alarm can be set on a single meter, or on a
combination. For example, you may want to trigger an alarm when the memory
consumption reaches 70% on a given instance if the instance has been up for
more than 10 min. To setup an alarm, you will call
:ref:`Aodh's API server <alarms-api>` specifying the alarm conditions and
an action to take.

Of course, if you are not administrator of the cloud itself, you can only set
alarms on meters for your own components.

There can be multiple form of actions, but two have been implemented so far:

1. :term:`HTTP callback`: you provide a URL to be called whenever the alarm has
   been set off. The payload of the request contains all the details of why the
   alarm was triggered.
2. :term:`log`: mostly useful for debugging, stores alarms in a log file.

For more details on this, we recommend that you read the blog post by
Mehdi Abaakouk `Autoscaling with Heat and Ceilometer`_. Particular attention
should be given to the section "Some notes about deploying alarming" as the
database setup (using a separate database from the one used for metering)
will be critical in all cases of production deployment.

.. _Autoscaling with Heat and Ceilometer: http://techs.enovance.com/5991/autoscaling-with-heat-and-ceilometer

Alarm Rules
===========

.. list-plugins:: aodh.alarm.rule
   :detailed:

Alarm Evaluators
================

.. list-plugins:: aodh.evaluator
   :detailed:

Alarm Notifiers
===============

.. list-plugins:: aodh.notifier
   :detailed:

Alarm Storage
===============

.. list-plugins:: aodh.storage
   :detailed:
