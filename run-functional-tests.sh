#!/bin/bash -x
set -e

case $AODH_TEST_BACKEND in
    hbase)
        export AODH_TEST_STORAGE_URL="hbase://__test__"
        ;;
    *)
        source $(which overtest) $AODH_TEST_BACKEND
        ;;
esac

$*
