#!/bin/bash -xe

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# This script is executed inside post_test_hook function in devstack gate.

function generate_testr_results {
    if [ -f .testrepository/0 ]; then
        sudo .tox/functional/bin/testr last --subunit > $WORKSPACE/testrepository.subunit
        sudo mv $WORKSPACE/testrepository.subunit $BASE/logs/testrepository.subunit
        sudo .tox/functional/bin/python /usr/local/jenkins/slave_scripts/subunit2html.py $BASE/logs/testrepository.subunit $BASE/logs/testr_results.html
        sudo gzip -9 $BASE/logs/testrepository.subunit
        sudo gzip -9 $BASE/logs/testr_results.html
        sudo chown jenkins:jenkins $BASE/logs/testrepository.subunit.gz $BASE/logs/testr_results.html.gz
        sudo chmod a+r $BASE/logs/testrepository.subunit.gz $BASE/logs/testr_results.html.gz
    fi
}

# If we're running in the gate find our keystone endpoint to give to
# gabbi tests and do a chown. Otherwise the existing environment
# should provide URL and TOKEN.
if [ -f $BASE/new/devstack ]; then
    export AODH_DIR="$BASE/new/aodh"
    JENKINS_USER=jenkins
    sudo chown -R jenkins:stack $AODH_DIR
    source $BASE/new/devstack/openrc admin admin
    openstack endpoint list
    export AODH_SERVICE_URL=$(openstack endpoint show alarming -c publicurl -f value)
    export AODH_SERVICE_TOKEN=$(openstack token issue -c id -f value)
    # Go to the aodh dir
    cd $AODH_DIR
fi

# Run tests
echo "Running aodh functional test suite"
set +e

# NOTE(ityaptin) Expect a script param which contains at least one backend name
AODH_TEST_BACKEND="${1:?test backend required}" sudo -E -H -u ${JENKINS_USER:-${USER}} tox -efunctional
EXIT_CODE=$?
set -e

# Collect and parse result
if [ -n "$AODH_DIR" ]; then
    generate_testr_results
fi
exit $EXIT_CODE
