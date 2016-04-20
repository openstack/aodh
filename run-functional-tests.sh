#!/bin/bash -x
set -e

export AODH_TEST_BACKEND=${AODH_TEST_BACKEND:-mysql}
export AODH_SERVICE_URL=${AODH_SERVICE_URL:-http://127.0.0.1:8042}

case $AODH_TEST_BACKEND in
    hbase)
        export AODH_TEST_STORAGE_URL="hbase://__test__"
        ;;
    *)
        source $(which overtest) $AODH_TEST_BACKEND
        ;;
esac

$*
