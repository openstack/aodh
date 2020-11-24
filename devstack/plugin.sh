# Install and start **Aodh** service in devstack
#
# To enable Aodh in devstack add an entry to local.conf that
# looks like
#
# [[local|localrc]]
# enable_plugin aodh https://opendev.org/openstack/aodh
#
# By default all aodh services are started (see
# devstack/settings).
#
#   AODH_BACKEND:            Database backend (e.g. 'mysql')
#   AODH_COORDINATION_URL:   URL for group membership service provided by tooz.

# Support potential entry-points console scripts in VENV or not
if [[ ${USE_VENV} = True ]]; then
    PROJECT_VENV["aodh"]=${AODH_DIR}.venv
    AODH_BIN_DIR=${PROJECT_VENV["aodh"]}/bin
else
    AODH_BIN_DIR=$(get_python_exec_prefix)
fi


if [ -z "$AODH_DEPLOY" ]; then
    # Default
    AODH_DEPLOY=simple

    # Fallback to common wsgi devstack configuration
    if [ "$ENABLE_HTTPD_MOD_WSGI_SERVICES" == "True" ]; then
        AODH_DEPLOY=mod_wsgi

    # Deprecated config
    elif [ -n "$AODH_USE_MOD_WSGI" ] ; then
        echo_summary "AODH_USE_MOD_WSGI is deprecated, use AODH_DEPLOY instead"
        if [ "$AODH_USE_MOD_WSGI" == True ]; then
            AODH_DEPLOY=mod_wsgi
        fi
    fi
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
    local venv_path=""

    # Copy proxy vhost and wsgi file
    sudo cp $AODH_DIR/aodh/api/app.wsgi $AODH_WSGI_DIR/app

    if [[ ${USE_VENV} = True ]]; then
        venv_path="python-path=${PROJECT_VENV["aodh"]}/lib/$(python_version)/site-packages"
    fi

    sudo cp $AODH_DIR/devstack/apache-aodh.template $aodh_apache_conf
    sudo sed -e "
        s|%PORT%|$AODH_SERVICE_PORT|g;
        s|%APACHE_NAME%|$APACHE_NAME|g;
        s|%WSGIAPP%|$AODH_WSGI_DIR/app|g;
        s|%USER%|$STACK_USER|g;
        s|%APIWORKERS%|$API_WORKERS|g;
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
    if [ "$AODH_DEPLOY" == "mod_wsgi" ]; then
        _aodh_cleanup_apache_wsgi
    fi
}

# Set configuration for storage backend.
function _aodh_configure_storage_backend {
    if [ "$AODH_BACKEND" = 'mysql' ] || [ "$AODH_BACKEND" = 'postgresql' ] ; then
        iniset $AODH_CONF database connection $(database_connection_url aodh)
    else
        die $LINENO "Unable to configure unknown AODH_BACKEND $AODH_BACKEND"
    fi
}

# Configure Aodh
function configure_aodh {
    iniset_rpc_backend aodh $AODH_CONF

    iniset $AODH_CONF oslo_messaging_notifications topics "$AODH_NOTIFICATION_TOPICS"
    iniset $AODH_CONF DEFAULT debug "$ENABLE_DEBUG_LOG_LEVEL"

    if [[ -n "$AODH_COORDINATION_URL" ]]; then
        iniset $AODH_CONF coordination backend_url $AODH_COORDINATION_URL
    fi

    # Set up logging
    if [ "$SYSLOG" != "False" ]; then
        iniset $AODH_CONF DEFAULT use_syslog "True"
    fi

    # Format logging
    if [ "$LOG_COLOR" == "True" ] && [ "$SYSLOG" == "False" ] && [ "$AODH_DEPLOY" != "mod_wsgi" ]; then
        setup_colorized_logging $AODH_CONF DEFAULT
    fi

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

    # Configured storage
    _aodh_configure_storage_backend

    # NOTE: This must come after database configuration as those can
    # call cleanup_aodh which will wipe the WSGI config.
    if [ "$AODH_DEPLOY" == "mod_wsgi" ]; then
        _aodh_config_apache_wsgi
    elif [ "$AODH_DEPLOY" == "uwsgi" ]; then
        # iniset creates these files when it's called if they don't exist.
        AODH_UWSGI_FILE=$AODH_CONF_DIR/aodh-uwsgi.ini

        rm -f "$AODH_UWSGI_FILE"

        iniset "$AODH_UWSGI_FILE" uwsgi http $AODH_SERVICE_HOST:$AODH_SERVICE_PORT
        iniset "$AODH_UWSGI_FILE" uwsgi wsgi-file "$AODH_DIR/aodh/api/app.wsgi"
        # This is running standalone
        iniset "$AODH_UWSGI_FILE" uwsgi master true
        # Set die-on-term & exit-on-reload so that uwsgi shuts down
        iniset "$AODH_UWSGI_FILE" uwsgi die-on-term true
        iniset "$AODH_UWSGI_FILE" uwsgi exit-on-reload true
        iniset "$AODH_UWSGI_FILE" uwsgi threads 10
        iniset "$AODH_UWSGI_FILE" uwsgi processes $API_WORKERS
        iniset "$AODH_UWSGI_FILE" uwsgi enable-threads true
        iniset "$AODH_UWSGI_FILE" uwsgi plugins python
        iniset "$AODH_UWSGI_FILE" uwsgi lazy-apps true
        # uwsgi recommends this to prevent thundering herd on accept.
        iniset "$AODH_UWSGI_FILE" uwsgi thunder-lock true
        # Override the default size for headers from the 4k default.
        iniset "$AODH_UWSGI_FILE" uwsgi buffer-size 65535
        # Make sure the client doesn't try to re-use the connection.
        iniset "$AODH_UWSGI_FILE" uwsgi add-header "Connection: close"
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
    install_aodhclient
    if python3_enabled; then
        PY_VERS=${PYTHON3_VERSION}
    else
        PY_VERS=${PYTHON2_VERSION}
    fi
    sudo -H SETUPTOOLS_USE_DISTUTILS=stdlib python${PY_VERS} -m pip \
	    install -e "$AODH_DIR"[test,$AODH_BACKEND]
    sudo install -d -o $STACK_USER -m 755 $AODH_CONF_DIR

    if [ "$AODH_DEPLOY" == "mod_wsgi" ]; then
        install_apache_wsgi
    elif [ "$AODH_DEPLOY" == "uwsgi" ]; then
        pip_install uwsgi
    fi
}

# install_aodhclient() - Collect source and prepare
function install_aodhclient {
    if use_library_from_git "python-aodhclient"; then
        git_clone_by_name "python-aodhclient"
        setup_dev_lib "python-aodhclient"
    else
        pip_install_gr aodhclient
    fi
    aodh complete | sudo tee /etc/bash_completion.d/aodh.bash_completion > /dev/null
}

# start_aodh() - Start running processes, including screen
function start_aodh {
    if [[ "$AODH_DEPLOY" == "mod_wsgi" ]]; then
        enable_apache_site aodh
        restart_apache_server
    elif [ "$AODH_DEPLOY" == "uwsgi" ]; then
        run_process aodh-api "$AODH_BIN_DIR/uwsgi $AODH_UWSGI_FILE"
    else
        run_process aodh-api "$AODH_BIN_DIR/aodh-api -p $AODH_SERVICE_PORT"
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

# configure_tempest_for_aodh()
# NOTE (gmann): Configure all the Tempest setting for Aodh service in
# this function.
function configure_tempest_for_aodh {
    if is_service_enabled tempest; then
        iniset $TEMPEST_CONFIG service_available aodh True
    fi
}

# stop_aodh() - Stop running processes
function stop_aodh {
    if [ "$AODH_DEPLOY" == "mod_wsgi" ]; then
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
        # Use stack_install_service here to account for virtualenv
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
    elif [[ "$1" == "stack" && "$2" == "test-config" ]]; then
        echo_summary "Configuring Tempest for Aodh"
        configure_tempest_for_aodh
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
