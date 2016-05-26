..
      Copyright 2014 Huawei Technologies Co., Ltd.

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

===========
Event alarm
===========

Aodh allows users to define alarms which can be evaluated based on events
passed from other OpenStack services. The events can be emitted when the
resources from other OpenStack services have been updated, created or deleted,
such as 'compute.instance.reboot.end', 'scheduler.select_destinations.end'.
When creating an alarm with type of "event", an event_type can be specified to
identify the type of evernt that will trigger the alarm. The event_type field
support fuzzy matching with wildcard. Additionally, users can also specify
query conditions to filter specific events used to trigger the alarm.

This feature was implemented with proposal event-alarm_.

.. _event-alarm: https://blueprints.launchpad.net/ceilometer/+spec/event-alarm-evaluator

Usage
=====

When creating an alarm of "event" type, the "event_rule" need to be specified,
which includes an "event_type" field and a "query" field, the "event_type"
allow users to specify a specific event type used to match the incoming events
when evaluating alarm, and the "query" field includes a list of query
conditions used to filter specific events when evaluating the alarm.

The following is an example of event alarm rule::

      "event_rule": {
          "event_type": "compute.instance.update",
          "query" : [
              {
                  "field" : "traits.instance_id",
                  "type" : "string",
                  "value" : "153462d0-a9b8-4b5b-8175-9e4b05e9b856",
                  "op" : "eq",
              },
              {
                  "field" : "traits.state",
                  "type" : "string",
                  "value" : "error",
                  "op" : "eq",
              },
          ]
      }


Configuration
=============

To enable this functionality, config the Ceilometer to be able to publish
events to the queue the aodh-listener service listen on. The
*event_alarm_topic* config option of Aodh identify which messaging topic the
aodh-listener on, the default value is "alarm.all". In Ceilometer side,
a publisher of notifier type need to be configured in the event pipeline config
file(event_pipeline.yaml as default), the notifier should be with a messaging
topic same as the *event_alarm_topic* option defined. For an example::

    ---
    sources:
        - name: event_source
          events:
              - "*"
          sinks:
              - event_sink
    sinks:
        - name: event_sink
          transformers:
          publishers:
              - notifier://
              - notifier://?topic=alarm.all
