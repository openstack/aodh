#!/bin/bash -x
set -e

export OS_TEST_PATH=aodh/tests/unit
./tools/pretty_tox.sh $*

export OS_TEST_PATH=aodh/tests/functional
AODH_TEST_DRIVERS=${AODH_TEST_DRIVERS:-postgresql}
for indexer in ${AODH_TEST_DRIVERS}
do
    pifpaf -g AODH_TEST_STORAGE_URL run $indexer -- ./tools/pretty_tox.sh $*
done
