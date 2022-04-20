.. _telemetry-alarms:

======
Alarms
======

Alarms provide user-oriented Monitoring-as-a-Service for resources
running on OpenStack. This type of monitoring ensures you can
automatically scale in or out a group of instances through the
Orchestration service, but you can also use alarms for general-purpose
awareness of your cloud resources' health.

These alarms follow a tri-state model:

ok
  The rule governing the alarm has been evaluated as ``False``.

alarm
  The rule governing the alarm has been evaluated as ``True``.

insufficient data
  There are not enough datapoints available in the evaluation periods
  to meaningfully determine the alarm state.

Alarm definitions
~~~~~~~~~~~~~~~~~

The definition of an alarm provides the rules that govern when a state
transition should occur, and the actions to be taken thereon. The
nature of these rules depend on the alarm type.

Threshold rule alarms
---------------------

For conventional threshold-oriented alarms, state transitions are
governed by:

* A static threshold value with a comparison operator such as greater
  than or less than.

* A statistic selection to aggregate the data.

* A sliding time window to indicate how far back into the recent past
  you want to look.

Both Ceilometer and Gnocchi are supported as data source of the threshold rule
alarm. Valid threshold alarms are:

* threshold
* gnocchi_resources_threshold
* gnocchi_aggregation_by_metrics_threshold
* gnocchi_aggregation_by_resources_threshold

Composite rule alarms
---------------------

Composite alarms enable users to define an alarm with multiple triggering
conditions, using a combination of ``and`` and ``or`` relations.

Alarm dimensioning
~~~~~~~~~~~~~~~~~~

A key associated concept is the notion of *dimensioning* which
defines the set of matching meters that feed into an alarm
evaluation. Recall that meters are per-resource-instance, so in the
simplest case an alarm might be defined over a particular meter
applied to all resources visible to a particular user. More useful
however would be the option to explicitly select which specific
resources you are interested in alarming on.

At one extreme you might have narrowly dimensioned alarms where this
selection would have only a single target (identified by resource
ID). At the other extreme, you could have widely dimensioned alarms
where this selection identifies many resources over which the
statistic is aggregated. For example all instances booted from a
particular image or all instances with matching user metadata (the
latter is how the Orchestration service identifies autoscaling
groups).

Alarm evaluation
~~~~~~~~~~~~~~~~

Alarms are evaluated by the ``alarm-evaluator`` service on a periodic
basis, defaulting to once every minute.

Alarm actions
-------------

Any state transition of individual alarm (to ``ok``, ``alarm``, or
``insufficient data``) may have one or more actions associated with
it. These actions effectively send a signal to a consumer that the
state transition has occurred, and provide some additional context.
This includes the new and previous states, with some reason data
describing the disposition with respect to the threshold, the number
of datapoints involved and most recent of these. State transitions
are detected by the ``alarm-evaluator``, whereas the
``alarm-notifier`` effects the actual notification action.

HTTP/HTTPS action
  These are the *de facto* notification type used by Telemetry alarming and
  simply involve an HTTP(S) POST request being sent to an endpoint, with a
  request body containing a description of the state transition encoded as a
  JSON fragment.

OpenStack Services
  The user is able to define an alarm that simply trigger some OpenStack
  service by directly specifying the service URL, e.g.
  ``trust+http://127.0.0.1:7070/v1/webhooks/ab91ef39-3e4a-4750-a8b8-0271518cd481/invoke``.
  ``aodh-notifier`` will prepare ``X-Auth-Token`` header and send HTTP(S) POST
  request to that URL, containing the alarm information in the request body.

Heat Autoscaling
  This notifier works together with ``loadbalancer_member_health`` evaluator.
  Presumably, the end user defines a Heat template which contains an
  autoscaling group and all the members in the group are joined in an Octavia
  load balancer in order to expose highly available service to the outside, so
  that when the stack scales up or scales down, Heat makes sure the new members
  are joining the load balancer automatically and the old members are removed.
  However, this notifier deals with the situation that when some member fails,
  the Heat stack could be recovered automatically. More information
  `here <https://docs.openstack.org/self-healing-sig/latest/use-cases/loadbalancer-member.html>`_

Log actions
  These are a lightweight alternative to webhooks, whereby the state transition
  is simply logged by the ``alarm-notifier``, and are intended primarily for
  testing purposes by admin users.

If none of the above actions satisfy your requirement, you can implement your
own alarm actions according to the current suppported actions in
``aodh/notifier`` folder.


Using alarms
~~~~~~~~~~~~

Alarm creation
--------------

Threshold based alarm
`````````````````````

An example of creating a Gnocchi threshold-oriented alarm, based on an upper
bound on the CPU utilization for a particular instance:

.. code-block:: console

   $ aodh alarm create \
     --name cpu_hi \
     --type gnocchi_resources_threshold \
     --description 'instance running hot' \
     --metric cpu_util \
     --threshold 70.0 \
     --comparison-operator gt \
     --aggregation-method mean \
     --granularity 600 \
     --evaluation-periods 3 \
     --alarm-action 'log://' \
     --resource-id INSTANCE_ID \
     --resource-type instance

This creates an alarm that will fire when the average CPU utilization
for an individual instance exceeds 70% for three consecutive 10
minute periods. The notification in this case is simply a log message,
though it could alternatively be a webhook URL.

.. note::

    Alarm names must be unique for the alarms associated with an
    individual project. Administrator can limit the maximum
    resulting actions for three different states, and the
    ability for a normal user to create ``log://`` and ``test://``
    notifiers is disabled. This prevents unintentional
    consumption of disk and memory resources by the
    Telemetry service.

The sliding time window over which the alarm is evaluated is 30
minutes in this example. This window is not clamped to wall-clock
time boundaries, rather it's anchored on the current time for each
evaluation cycle, and continually creeps forward as each evaluation
cycle rolls around (by default, this occurs every minute).

.. note::

   The alarm granularity must match the granularities of the metric configured
   in Gnocchi.

Otherwise the alarm will tend to flit in and out of the
``insufficient data`` state due to the mismatch between the actual
frequency of datapoints in the metering store and the statistics
queries used to compare against the alarm threshold. If a shorter
alarm period is needed, then the corresponding interval should be
adjusted in the ``pipeline.yaml`` file.

Other notable alarm attributes that may be set on creation, or via a
subsequent update, include:

state
  The initial alarm state (defaults to ``insufficient data``).

description
  A free-text description of the alarm (defaults to a synopsis of the
  alarm rule).

enabled
  True if evaluation and actioning is to be enabled for this alarm
  (defaults to ``True``).

repeat-actions
  True if actions should be repeatedly notified while the alarm
  remains in the target state (defaults to ``False``).

ok-action
  An action to invoke when the alarm state transitions to ``ok``.

insufficient-data-action
  An action to invoke when the alarm state transitions to
  ``insufficient data``.

time-constraint
  Used to restrict evaluation of the alarm to certain times of the
  day or days of the week (expressed as ``cron`` expression with an
  optional timezone).

Composite alarm
```````````````

An example of creating a composite alarm, based on the composite of
two basic rules:

.. code-block:: console

   $ aodh alarm create \
     --name meta \
     --type composite \
     --composite-rule '{"or": [{"threshold": 0.8, "metric": "cpu_util", \
       "type": "gnocchi_resources_threshold", "resource_id": INSTANCE_ID1, \
       "resource_type": "instance", "aggregation_method": "last"}, \
       {"threshold": 0.8, "metric": "cpu_util", \
       "type": "gnocchi_resources_threshold", "resource_id": INSTANCE_ID2, \
       "resource_type": "instance", "aggregation_method": "last"}]}' \
     --alarm-action 'http://example.org/notify'

This creates an alarm that will fire when either of two basic rules
meets the condition. The notification in this case is a webhook call.
Any number of basic rules can be composed into a composite rule this
way, using either ``and`` or ``or``. Additionally, composite rules
can contain nested conditions:

.. note::

   Observe the *underscore in* ``resource_id`` & ``resource_type`` in
   composite rule as opposed to ``--resource-id`` &
   ``--resource-type`` CLI arguments.

.. code-block:: console

   $ aodh alarm create \
     --name meta \
     --type composite \
     --composite-rule '{"or": [ALARM_1, {"and": [ALARM_2, ALARM_3]}]}' \
     --alarm-action 'http://example.org/notify'


Event based alarm
`````````````````

An example of creating a event alarm based on power state of
instance:

.. code-block:: console

   $ aodh alarm create \
     --type event \
     --name instance_off \
     --description 'Instance powered OFF' \
     --event-type "compute.instance.power_off.*" \
     --enable True \
     --query "traits.instance_id=string::INSTANCE_ID" \
     --alarm-action 'log://' \
     --ok-action 'log://' \
     --insufficient-data-action 'log://'

Valid list of ``event-type`` and ``traits`` can be found in
``event_definitions.yaml`` file . ``--query`` may also contain mix of
traits for example to create alarm when instance is powered on but
went into error state:

.. code-block:: console

   $ aodh alarm create \
     --type event \
     --name instance_on_but_in_err_state \
     --description 'Instance powered ON but in error state' \
     --event-type "compute.instance.power_on.*" \
     --enable True \
     --query "traits.instance_id=string::INSTANCE_ID;traits.state=string::error" \
     --alarm-action 'log://' \
     --ok-action 'log://' \
     --insufficient-data-action 'log://'

Sample output of alarm type **event**:

.. code-block:: console

   +---------------------------+---------------------------------------------------------------+
   | Field                     | Value                                                         |
   +---------------------------+---------------------------------------------------------------+
   | alarm_actions             | ['log://']                                                    |
   | alarm_id                  | 15c0da26-524d-40ad-8fba-3e55ee0ddc91                          |
   | description               | Instance powered ON but in error state                        |
   | enabled                   | True                                                          |
   | event_type                | compute.instance.power_on.*                                   |
   | insufficient_data_actions | ['log://']                                                    |
   | name                      | instance_on_state_err                                         |
   | ok_actions                | ['log://']                                                    |
   | project_id                | 9ee200732f4c4d10a6530bac746f1b6e                              |
   | query                     | traits.instance_id = bb912729-fa51-443b-bac6-bf4c795f081d AND |
   |                           | traits.state = error                                          |
   | repeat_actions            | False                                                         |
   | severity                  | low                                                           |
   | state                     | insufficient data                                             |
   | state_timestamp           | 2017-07-15T02:28:31.114455                                    |
   | time_constraints          | []                                                            |
   | timestamp                 | 2017-07-15T02:28:31.114455                                    |
   | type                      | event                                                         |
   | user_id                   | 89b4e48bcbdb4816add7800502bd5122                              |
   +---------------------------+---------------------------------------------------------------+

.. note::

   To enable event alarms please refer `Configuration
   <https://docs.openstack.org/aodh/latest/contributor/event-alarm.html#configuration>`_

Alarm retrieval
---------------

You can display all your alarms via (some attributes are omitted for
brevity):

.. code-block:: console

   $ aodh alarm list
   +----------+-----------+--------+-------------------+----------+---------+
   | alarm_id | type      | name   | state             | severity | enabled |
   +----------+-----------+--------+-------------------+----------+---------+
   | ALARM_ID | threshold | cpu_hi | insufficient data | low      | True    |
   +----------+-----------+--------+-------------------+----------+---------+

In this case, the state is reported as ``insufficient data`` which
could indicate that:

* meters have not yet been gathered about this instance over the
  evaluation window into the recent past (for example a brand-new
  instance)

* *or*, that the identified instance is not visible to the
  user/project owning the alarm

* *or*, simply that an alarm evaluation cycle hasn't kicked off since
  the alarm was created (by default, alarms are evaluated once per
  minute).

.. note::

   The visibility of alarms depends on the role and project
   associated with the user issuing the query:

   * admin users see *all* alarms, regardless of the owner

   * non-admin users see only the alarms associated with their project
     (as per the normal project segregation in OpenStack)

Alarm update
------------

Once the state of the alarm has settled down, we might decide that we
set that bar too low with 70%, in which case the threshold (or most
any other alarm attribute) can be updated thusly:

.. code-block:: console

   $ aodh alarm update ALARM_ID --threshold 75

The change will take effect from the next evaluation cycle, which by
default occurs every minute.

Most alarm attributes can be changed in this way, but there is also
a convenient short-cut for getting and setting the alarm state:

.. code-block:: console

   $ openstack alarm state get ALARM_ID
   $ openstack alarm state set --state ok ALARM_ID

Over time the state of the alarm may change often, especially if the
threshold is chosen to be close to the trending value of the
statistic. You can follow the history of an alarm over its lifecycle
via the audit API:

.. code-block:: console

   $ aodh alarm-history show ALARM_ID
   +-----------+------------------+---------------------------------------------------+----------+
   | timestamp | type             | detail                                            | event_id |
   +-----------+------------------+---------------------------------------------------+----------+
   | TIME_3    | rule change      | {"rule": {"evaluation_periods": 3, "metric":      | EVENT_ID |
   |           |                  | "cpu_util", "resource_id": RESOURCE_ID,           |          |
   |           |                  | "aggregation_method": "mean", "granularity":600,  |          |
   |           |                  | "threshold": 75.0, "comparison_operator": "gt"    |          |
   |           |                  | "resource_type": "instance"}}                     |          |
   | TIME_2    | state transition | {"transition_reason": "Transition to alarm due 3  | EVENT_ID |
   |           |                  | samples outside threshold, most recent:           |          |
   |           |                  | 81.4108514719", "state": "alarm"}                 |          |
   | TIME_1    | state transition | {"transition_reason": "Transition to ok due to 1  | EVENT_ID |
   |           |                  | samples inside threshold, most recent:            |          |
   |           |                  | 67.952938019089", "state": "ok"}                  |          |
   | TIME_0    | creation         | {"alarm_actions": ["log://"], "user_id": USER_ID, | EVENT_ID |
   |           |                  | "name": "cup_hi", "state": "insufficient data",   |          |
   |           |                  | "timestamp": TIME_0, "description": "instance     |          |
   |           |                  | running hot", "enabled": true, "state_timestamp": |          |
   |           |                  | TIME_0, "rule": {"evaluation_periods": 3,         |          |
   |           |                  | "metric": "cpu_util", "resource_id": RESOURCE_ID, |          |
   |           |                  | "aggregation_method": "mean", "granularity": 600, |          |
   |           |                  | "resource_type": "instance"}, "alarm_id":         |          |
   |           |                  | ALARM_ID, "time_constraints": [],                 |          |
   |           |                  | "insufficient_data_actions": [],                  |          |
   |           |                  | "repeat_actions": false, "ok_actions": [],        |          |
   |           |                  | "project_id": PROJECT_ID, "type":                 |          |
   |           |                  | "gnocchi_resources_threshold", "severity": "low"} |          |
   +-----------+------------------+---------------------------------------------------+----------+

Alarm deletion
--------------

An alarm that is no longer required can be disabled so that it is no
longer actively evaluated:

.. code-block:: console

   $ aodh alarm update --enabled False ALARM_ID

or even deleted permanently (an irreversible step):

.. code-block:: console

   $ aodh alarm delete ALARM_ID

Debug alarms
------------

A good place to start is to add ``--debug`` flag when creating or
updating an alarm. For example:

.. code-block:: console

   $ aodh --debug alarm create <OTHER_PARAMS>

Look for the state to transition when event is triggered in
``/var/log/aodh/listener.log`` file. For example, the below logs shows
the transition state of alarm with id
``85a2942f-a2ec-4310-baea-d58f9db98654`` triggered by event id
``abe437a3-b75b-40b4-a3cb-26022a919f5e``

.. code-block:: console

   2017-07-15 07:03:20.149 2866 INFO aodh.evaluator [-] alarm 85a2942f-a2ec-4310-baea-d58f9db98654 transitioning to alarm because Event <id=abe437a3-b75b-40b4-a3cb-26022a919f5e,event_type=compute.instance.power_off.start> hits the query <query=[{"field": "traits.instance_id", "op": "eq", "type": "string", "value": "bb912729-fa51-443b-bac6-bf4c795f081d"}]>.


The below entry in ``/var/log/aodh/notifier.log`` also confirms that
event id ``abe437a3-b75b-40b4-a3cb-26022a919f5e`` hits the query
matching instance id ``bb912729-fa51-443b-bac6-bf4c795f081d``

.. code-block:: console

   2017-07-15 07:03:24.071 2863 INFO aodh.notifier.log [-] Notifying alarm instance_off 85a2942f-a2ec-4310-baea-d58f9db98654 of low priority from insufficient data to alarm with action log: because Event <id=abe437a3-b75b-40b4-a3cb-26022a919f5e,event_type=compute.instance.power_off.start> hits the query <query=[{"field": "traits.instance_id", "op": "eq", "type": "string", "value": "bb912729-fa51-443b-bac6-bf4c795f081d"}]>


``aodh alarm-history`` as mentioned earlier will also display the
transition:

.. code-block:: console

   $ aodh alarm-history show 85a2942f-a2ec-4310-baea-d58f9db98654
   +----------------------------+------------------+--------------------------------------------------------------------------------------------------------------------------+--------------------------------------+
   | timestamp                  | type             | detail                                                                                                                   | event_id                             |
   +----------------------------+------------------+--------------------------------------------------------------------------------------------------------------------------+--------------------------------------+
   | 2017-07-15T01:33:20.390623 | state transition | {"transition_reason": "Event <id=abe437a3-b75b-40b4-a3cb-26022a919f5e,event_type=compute.instance.power_off.start> hits  | c5ca92ae-584b-4da6-a12c-b7a00dd39fef |
   |                            |                  | the query <query=[{\"field\": \"traits.instance_id\", \"op\": \"eq\", \"type\": \"string\", \"value\": \"bb912729-fa51   |                                      |
   |                            |                  | -443b-bac6-bf4c795f081d\"}]>.", "state": "alarm"}                                                                        |                                      |
   | 2017-07-15T01:31:14.516188 | creation         | {"alarm_actions": ["log://"], "user_id": "89b4e48bcbdb4816add7800502bd5122", "name": "instance_off", "state":            | fb31f4c2-e357-44c3-9b6a-bd2aaaa4ae68 |
   |                            |                  | "insufficient data", "timestamp": "2017-07-15T01:31:14.516188", "description": "event_instance_power_off", "enabled":    |                                      |
   |                            |                  | true, "state_timestamp": "2017-07-15T01:31:14.516188", "rule": {"query": [{"field": "traits.instance_id", "type":        |                                      |
   |                            |                  | "string", "value": "bb912729-fa51-443b-bac6-bf4c795f081d", "op": "eq"}], "event_type": "compute.instance.power_off.*"},  |                                      |
   |                            |                  | "alarm_id": "85a2942f-a2ec-4310-baea-d58f9db98654", "time_constraints": [], "insufficient_data_actions": ["log://"],     |                                      |
   |                            |                  | "repeat_actions": false, "ok_actions": ["log://"], "project_id": "9ee200732f4c4d10a6530bac746f1b6e", "type": "event",    |                                      |
   |                            |                  | "severity": "low"}                                                                                                       |                                      |
   +----------------------------+------------------+--------------------------------------------------------------------------------------------------------------------------+--------------------------------------+
