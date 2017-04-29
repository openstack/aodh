#!/usr/bin/env bash

set -o pipefail

TESTRARGS=$*

# --until-failure is not compatible with --subunit see:
#
# https://bugs.launchpad.net/testrepository/+bug/1411804
#
# this work around exists until that is addressed
if [[ "$TESTARGS" =~ "until-failure" ]]; then
    ostestr --slowest $TESTRARGS
else
    ostestr --no-pretty --slowest --subunit $TESTRARGS | subunit-trace -f
fi
