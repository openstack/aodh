# Install and start **Aodh** service in devstack
#
# To enable Aodh in devstack add an entry to local.conf that
# looks like
#
# [[local|localrc]]
# enable_plugin aodh git://git.openstack.org/openstack/aodh
#
# By default all aodh services are started (see
# devstack/settings).
#
#   AODH_BACKEND:            Database backend (e.g. 'mysql', 'mongodb')
#   AODH_COORDINATION_URL:   URL for group membership service provided by tooz.

# Support potential entry-points console scripts in VENV or not
if [[ ${USE_VENV} = True ]]; then
    PROJECT_VENV["aodh"]=${AODH_DIR}.venv
    AODH_BIN_DIR=${PROJECT_VENV["aodh"]}/bin
else
    AODH_BIN_DIR=$(get_python_exec_prefix)
fi

# Test if any Aodh services are enabled
# is_aodh_enabled
function is_aodh_enabled {
    [[ ,${ENABLED_SERVICES} =~ ,"aodh-" ]] && return 0
    return 1
}

function aodh_service_url {
    echo "$AODH_SERVICE_PROTOCOL://$AODH_SERVICE_HOST:$AODH_SERVICE_PORT"
}


# _install_mongdb - Install mongodb and python lib.
function _aodh_install_mongodb {
    # Server package is the same on all
    local packages=mongodb-server

    if is_fedora; then
        # mongodb client
        packages="${packages} mongodb"
    fi

    install_package ${packages}

    if is_fedora; then
        restart_service mongod
    else
        restart_service mongodb
    fi

    # give time for service to restart
    sleep 5
}

# _install_redis() - Install the redis server and python lib.
function _aodh_install_redis {
    if is_ubuntu; then
        install_package redis-server
        restart_service redis-server
    else
        # This will fail (correctly) where a redis package is unavailable
        install_package redis
        restart_service redis
    fi

    pip_install_gr redis
}

# Configure mod_wsgi
function _aodh_config_apache_wsgi {
    sudo mkdir -p $AODH_WSGI_DIR

    local aodh_apache_conf=$(apache_site_config_for aodh)
    local apache_version=$(get_apache_version)
    local venv_path=""

    # Copy proxy vhost and wsgi file
    sudo cp $AODH_DIR/aodh/api/app.wsgi $AODH_WSGI_DIR/app

    if [[ ${USE_VENV} = True ]]; then
        venv_path="python-path=${PROJECT_VENV["aodh"]}/lib/$(python_version)/site-packages"
    fi

    sudo cp $AODH_DIR/devstack/apache-aodh.template $aodh_apache_conf
    if [ "$AODH_BACKEND" = 'hbase' ] ; then
        # Use one process to have single in-memory DB instance for data consistency
        AODH_API_WORKERS=1
    else
        AODH_API_WORKERS=$API_WORKERS
    fi
    sudo sed -e "
        s|%PORT%|$AODH_SERVICE_PORT|g;
        s|%APACHE_NAME%|$APACHE_NAME|g;
        s|%WSGIAPP%|$AODH_WSGI_DIR/app|g;
        s|%USER%|$STACK_USER|g;
        s|%APIWORKERS%|$AODH_API_WORKERS|g;
        s|%VIRTUALENV%|$venv_path|g
    " -i $aodh_apache_conf
}

# Install required services for coordination
function _aodh_prepare_coordination {
    if echo $AODH_COORDINATION_URL | grep -q '^memcached:'; then
        install_package memcached
    elif echo $AODH_COORDINATION_URL | grep -q '^redis:'; then
        _aodh_install_redis
    fi
}

# Install required services for storage backends
function _aodh_prepare_storage_backend {
    if [ "$AODH_BACKEND" = 'mongodb' ] ; then
        pip_install_gr pymongo
        _aodh_install_mongodb
    fi
}

# Create aodh related accounts in Keystone
function _aodh_create_accounts {
    if is_service_enabled aodh-api; then

        create_service_user "aodh" "admin"

        local aodh_service=$(get_or_create_service "aodh" \
            "alarming" "OpenStack Alarming Service")
        get_or_create_endpoint $aodh_service \
            "$REGION_NAME" \
            "$(aodh_service_url)" \
            "$(aodh_service_url)" \
            "$(aodh_service_url)"
    fi
}

# Activities to do before aodh has been installed.
function preinstall_aodh {
    # Needed to build psycopg2
    if is_ubuntu; then
        install_package libpq-dev
    else
        install_package postgresql-devel
    fi
}

# Remove WSGI files, disable and remove Apache vhost file
function _aodh_cleanup_apache_wsgi {
    sudo rm -f $AODH_WSGI_DIR/*
    sudo rm -f $(apache_site_config_for aodh)
}

# cleanup_aodh() - Remove residual data files, anything left over
# from previous runs that a clean run would need to clean up
function cleanup_aodh {
    if [ "$AODH_BACKEND" = 'mongodb' ] ; then
        mongo aodh --eval "db.dropDatabase();"
    fi
    if [ "$AODH_USE_MOD_WSGI" == "True" ]; then
        _aodh_cleanup_apache_wsgi
    fi
}

# Set configuration for storage backend.
function _aodh_configure_storage_backend {
    if [ "$AODH_BACKEND" = 'mysql' ] || [ "$AODH_BACKEND" = 'postgresql' ] ; then
        iniset $AODH_CONF database connection $(database_connection_url aodh)
    elif [ "$AODH_BACKEND" = 'mongodb' ] ; then
        iniset $AODH_CONF database connection mongodb://localhost:27017/aodh
        cleanup_aodh
    elif [ "$AODH_BACKEND" = 'hbase' ] ; then
        iniset $AODH_CONF database connection hbase://__test__
    else
        die $LINENO "Unable to configure unknown AODH_BACKEND $AODH_BACKEND"
    fi
}

# Configure Aodh
function configure_aodh {
    iniset_rpc_backend aodh $AODH_CONF

    iniset $AODH_CONF DEFAULT notification_topics "$AODH_NOTIFICATION_TOPICS"
    iniset $AODH_CONF DEFAULT verbose True
    iniset $AODH_CONF DEFAULT debug "$ENABLE_DEBUG_LOG_LEVEL"

    if [[ -n "$AODH_COORDINATION_URL" ]]; then
        iniset $AODH_CONF coordination backend_url $AODH_COORDINATION_URL
    fi

    # Install the policy file for the API server
    cp $AODH_DIR/etc/aodh/policy.json $AODH_CONF_DIR
    iniset $AODH_CONF oslo_policy policy_file $AODH_CONF_DIR/policy.json

    cp $AODH_DIR/etc/aodh/api_paste.ini $AODH_CONF_DIR

    # The alarm evaluator needs these options to call gnocchi/ceilometer APIs
    iniset $AODH_CONF service_credentials auth_type password
    iniset $AODH_CONF service_credentials username aodh
    iniset $AODH_CONF service_credentials user_domain_id default
    iniset $AODH_CONF service_credentials project_domain_id default
    iniset $AODH_CONF service_credentials password $SERVICE_PASSWORD
    iniset $AODH_CONF service_credentials project_name $SERVICE_PROJECT_NAME
    iniset $AODH_CONF service_credentials region_name $REGION_NAME
    iniset $AODH_CONF service_credentials auth_url $KEYSTONE_SERVICE_URI

    configure_auth_token_middleware $AODH_CONF aodh $AODH_AUTH_CACHE_DIR

    iniset $AODH_CONF notification store_events $AODH_EVENTS

    # Configured storage
    _aodh_configure_storage_backend

    # NOTE: This must come after database configuration as those can
    # call cleanup_aodh which will wipe the WSGI config.
    if [ "$AODH_USE_MOD_WSGI" == "True" ]; then
        iniset $AODH_CONF api pecan_debug "False"
        _aodh_config_apache_wsgi
    fi

    if is_service_enabled gnocchi-api; then
        iniset $AODH_CONF DEFAULT gnocchi_url $(gnocchi_service_url)
    fi
}

# init_aodh() - Initialize etc.
function init_aodh {
    # Get aodh keystone settings in place
    _aodh_create_accounts
    # Create cache dir
    sudo install -d -o $STACK_USER $AODH_AUTH_CACHE_DIR
    rm -f $AODH_AUTH_CACHE_DIR/*

    if is_service_enabled mysql postgresql; then
        if [ "$AODH_BACKEND" = 'mysql' ] || [ "$AODH_BACKEND" = 'postgresql' ] ; then
            recreate_database aodh
            $AODH_BIN_DIR/aodh-dbsync
        fi
    fi
}

# Install Aodh.
# The storage and coordination backends are installed here because the
# virtualenv context is active at this point and python drivers need to be
# installed. The context is not active during preinstall (when it would
# otherwise makes sense to do the backend services).
function install_aodh {
    _aodh_prepare_coordination
    _aodh_prepare_storage_backend
    install_aodhclient
    sudo -H pip install -e "$AODH_DIR"[test,$AODH_BACKEND]
    sudo install -d -o $STACK_USER -m 755 $AODH_CONF_DIR $AODH_API_LOG_DIR
}

# install_aodhclient() - Collect source and prepare
function install_aodhclient {
    if use_library_from_git "python-ceilometerclient"; then
        git_clone_by_name "python-ceilometerclient"
        setup_dev_lib "python-ceilometerclient"
        sudo install -D -m 0644 -o $STACK_USER {${GITDIR["python-ceilometerclient"]}/tools/,/etc/bash_completion.d/}ceilometer.bash_completion
    else
        pip_install_gr python-ceilometerclient
    fi
}

# start_aodh() - Start running processes, including screen
function start_aodh {
    if [[ "$AODH_USE_MOD_WSGI" == "False" ]]; then
        run_process aodh-api "$AODH_BIN_DIR/aodh-api -d -v --log-dir=$AODH_API_LOG_DIR --config-file $AODH_CONF"
    else
        enable_apache_site aodh
        restart_apache_server
        tail_log aodh /var/log/$APACHE_NAME/aodh.log
        tail_log aodh-api /var/log/$APACHE_NAME/aodh_access.log
    fi

    # Only die on API if it was actually intended to be turned on
    if is_service_enabled aodh-api; then
        echo "Waiting for aodh-api to start..."
        if ! wait_for_service $SERVICE_TIMEOUT $(aodh_service_url)/v2/; then
            die $LINENO "aodh-api did not start"
        fi
    fi

    run_process aodh-notifier "$AODH_BIN_DIR/aodh-notifier --config-file $AODH_CONF"
    run_process aodh-evaluator "$AODH_BIN_DIR/aodh-evaluator --config-file $AODH_CONF"
    run_process aodh-listener "$AODH_BIN_DIR/aodh-listener --config-file $AODH_CONF"
}

# stop_aodh() - Stop running processes
function stop_aodh {
    if [ "$AODH_USE_MOD_WSGI" == "True" ]; then
        disable_apache_site aodh
        restart_apache_server
    fi
    # Kill the aodh screen windows
    for serv in aodh-api aodh-notifier aodh-evaluator aodh-listener; do
        stop_process $serv
    done
}

# This is the main for plugin.sh
if is_service_enabled aodh; then
    if [[ "$1" == "stack" && "$2" == "pre-install" ]]; then
        # Set up other services
        echo_summary "Configuring system services for Aodh"
        preinstall_aodh
    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        echo_summary "Installing Aodh"
        # Use stack_install_service here to account for vitualenv
        stack_install_service aodh
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        echo_summary "Configuring Aodh"
        configure_aodh
    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        echo_summary "Initializing Aodh"
        # Tidy base for aodh
        init_aodh
        # Start the services
        start_aodh
    fi

    if [[ "$1" == "unstack" ]]; then
        echo_summary "Shutting Down Aodh"
        stop_aodh
    fi

    if [[ "$1" == "clean" ]]; then
        echo_summary "Cleaning Aodh"
        cleanup_aodh
    fi
fi
