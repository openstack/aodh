#!/bin/bash -x
set -e

export AODH_TEST_BACKEND=${AODH_TEST_BACKEND:-mysql}
export AODH_SERVICE_URL=${AODH_SERVICE_URL:-http://127.0.0.1:8042}

case $AODH_TEST_BACKEND in
    hbase)
        AODH_TEST_STORAGE_URL="hbase://__test__" $*
        ;;
    *)
        pifpaf -g AODH_TEST_STORAGE_URL run $AODH_TEST_BACKEND -- $*
        ;;
esac
