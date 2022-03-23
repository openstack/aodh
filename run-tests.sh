#!/bin/bash -x
set -e

AODH_TEST_DRIVERS=${AODH_TEST_DRIVERS:-postgresql}
export GABBI_LIVE_FAIL_IF_NO_TEST=1
export AODH_SERVICE_TOKEN=foobar # Needed for gabbi
export AODH_SERVICE_ROLES=admin

# unit tests

export OS_TEST_PATH=aodh/tests/unit
stestr run $*

# functional tests

export OS_TEST_PATH=aodh/tests/functional
for indexer in ${AODH_TEST_DRIVERS}
do
    pifpaf -g AODH_TEST_STORAGE_URL run $indexer -- stestr run $*
done

# live functional tests

cleanup(){
    type -t database_stop >/dev/null && database_stop || true
}
trap cleanup EXIT

export OS_TEST_PATH=aodh/tests/functional_live
for indexer in ${AODH_TEST_DRIVERS}
do
    eval $(pifpaf -e DATABASE run $indexer)
    pifpaf -e AODH run aodh --database-url $DATABASE_URL -- stestr run $*
    cleanup
done
