===================================
Telemetry Alarming service overview
===================================

The Telemetry Alarming services trigger alarms when the collected metering
or event data break the defined rules.

The Telemetry Alarming service consists of the following components:

An API server (``aodh-api``)
  Runs on one or more central management servers to provide access
  to the alarm information stored in the data store.

An alarm evaluator (``aodh-evaluator``)
  Runs on one or more central management servers to determine when
  alarms fire due to the associated statistic trend crossing a
  threshold over a sliding time window.

A notification listener (``aodh-listener``)
  Runs on a central management server and determines when to fire alarms.
  The alarms are generated based on defined rules against events, which are
  captured by the Telemetry Data Collection service's notification agents.

An alarm notifier (``aodh-notifier``)
  Runs on one or more central management servers to allow alarms to be
  set based on the threshold evaluation for a collection of samples.

These services communicate by using the OpenStack messaging bus.
