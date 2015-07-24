#!/bin/bash -x
set -e

# Use a mongodb backend by default
if [ -z "$AODH_TEST_BACKEND" ]; then
    AODH_TEST_BACKEND="mongodb"
fi
echo $AODH_TEST_BACKEND
for backend in $AODH_TEST_BACKEND; do
    ./setup-test-env-${backend}.sh ./tools/pretty_tox.sh $*
done
