#!/bin/bash -x
set -e
AODH_TEST_DRIVERS=${AODH_TEST_DRIVERS:-postgresql}
for indexer in ${AODH_TEST_DRIVERS}
do
    pifpaf -g AODH_TEST_STORAGE_URL run $indexer -- ./tools/pretty_tox.sh $*
done
