#!/bin/bash -x
set -e

cleanup(){
    type -t database_stop >/dev/null && database_stop || true
}
trap cleanup EXIT

export OS_TEST_PATH=aodh/tests/functional_live
export GABBI_LIVE_FAIL_IF_NO_TEST=1
export AODH_SERVICE_TOKEN=foobar # Needed for gabbi
export AODH_SERVICE_ROLES=admin

AODH_TEST_DRIVERS=${AODH_TEST_DRIVERS:-postgresql}
for indexer in ${AODH_TEST_DRIVERS}
do
    eval $(pifpaf -e DATABASE run $indexer)
    pifpaf -e AODH run aodh --database-url $DATABASE_URL -- stestr run $*
    cleanup
done
