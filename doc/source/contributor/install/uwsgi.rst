=============================
Installing the API with uwsgi
=============================

The module ``aodh.wsgi.api`` provides the function to set up the V2 API WSGI
application. The module is installed with the rest of the Aodh application
code, and should not need to be modified.

Install uwsgi.

On RHEL/CentOS/Fedora::

    sudo dnf install uwsgi-plugin-python3

On Ubuntu/Debian::

    sudo apt-get install uwsgi-plugin-python3

Create aodh-uwsgi.ini file::

    [uwsgi]
    http = 0.0.0.0:8041
    module = aodh.wsgi.api:application
    plugins = python
    # This is running standalone
    master = true
    # Set die-on-term & exit-on-reload so that uwsgi shuts down
    exit-on-reload = true
    die-on-term = true
    # uwsgi recommends this to prevent thundering herd on accept.
    thunder-lock = true
    # Override the default size for headers from the 4k default. (mainly for keystone token)
    buffer-size = 65535
    enable-threads = true
    # Set the number of threads usually with the returns of command nproc
    threads = 8
    # Make sure the client doesn't try to re-use the connection.
    add-header = Connection: close
    # Set uid and gip to an appropriate user on your server. In many
    # installations ``aodh`` will be correct.
    uid = aodh
    gid = aodh

Then start the uwsgi server::

    uwsgi ./aodh-uwsgi.ini

Or start in background with::

    uwsgi -d ./aodh-uwsgi.ini
