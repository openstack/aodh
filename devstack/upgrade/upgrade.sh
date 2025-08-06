#!/usr/bin/env bash

# ``upgrade-aodh``

echo "*********************************************************************"
echo "Begin $0"
echo "*********************************************************************"

# Clean up any resources that may be in use
cleanup() {
    set +o errexit

    echo "*********************************************************************"
    echo "ERROR: Abort $0"
    echo "*********************************************************************"

    # Kill ourselves to signal any calling process
    trap 2; kill -2 $$
}

trap cleanup SIGHUP SIGINT SIGTERM

# Keep track of the grenade directory
RUN_DIR=$(cd $(dirname "$0") && pwd)

# Source params
source $GRENADE_DIR/grenaderc

# Import common functions
source $GRENADE_DIR/functions

# This script exits on an error so that errors don't compound and you see
# only the first error that occurred.
set -o errexit

# Upgrade Aodh
# ==================
# Locate aodh devstack plugin, the directory above the
# grenade plugin.
AODH_DEVSTACK_DIR=$(dirname $(dirname $0))

# Get functions from current DevStack
source $TARGET_DEVSTACK_DIR/functions
source $TARGET_DEVSTACK_DIR/stackrc
source $TARGET_DEVSTACK_DIR/lib/apache

# Get aodh functions from devstack plugin
source $AODH_DEVSTACK_DIR/settings

# Print the commands being run so that we can see the command that triggers
# an error.
set -o xtrace

# Install the target aodh
source $AODH_DEVSTACK_DIR/plugin.sh stack install

# calls upgrade-aodh for specific release
upgrade_project aodh $RUN_DIR $BASE_DEVSTACK_BRANCH $TARGET_DEVSTACK_BRANCH

# Migrate the database
# NOTE(chdent): As we evolve BIN_DIR is likely to be defined, but
# currently it is not.
AODH_BIN_DIR=$(get_python_exec_prefix)
$AODH_BIN_DIR/aodh-dbsync --config-file $AODH_CONF || die $LINENO "DB sync error"

# Start Aodh
start_aodh

ensure_services_started aodh-api aodh-evaluator aodh-listener

set +o xtrace
echo "*********************************************************************"
echo "SUCCESS: End $0"
echo "*********************************************************************"
