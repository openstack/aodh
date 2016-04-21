.. _architecture:

=====================
 System Architecture
=====================

.. index::

High-Level Architecture
=======================

Each of Aodh's services are designed to scale horizontally. Additional
workers and nodes can be added depending on the expected load. It provides
daemons to evaluate and notify based on defined alarming rules.

Evaluating the data
===================

Alarming Service
----------------

The alarming component of Aodh, first delivered in Ceilometer service during
Havana development cycle then split out to this independent project in Liberty
development cycle, allows you to set alarms based on threshold evaluation for
a collection of samples or a dedicate event. An alarm can be set on a single
meter, or on a combination. For example, you may want to trigger an alarm when
the memory consumption reaches 70% on a given instance if the instance has been
up for more than 10 min. To setup an alarm, you will call
:ref:`Aodh's API server <alarms-api>` specifying the alarm conditions and
an action to take.

Of course, if you are not administrator of the cloud itself, you can only set
alarms on meters for your own components.

There can be multiple form of actions, but only several actions have been
implemented so far:

1. :term:`HTTP callback`: you provide a URL to be called whenever the alarm has
   been set off. The payload of the request contains all the details of why the
   alarm was triggered.
2. :term:`log`: mostly useful for debugging, stores alarms in a log file.
3. :term:`zaqar`: Send notification to messaging service via Zaqar API.

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
