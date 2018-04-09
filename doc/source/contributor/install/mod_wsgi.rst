..
      Copyright 2013 New Dream Network, LLC (DreamHost)

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

==================================
Installing the API behind mod_wsgi
==================================

Aodh comes with a WSGI application file named `aodh/api/app.wsgi` for
configuring the API service to run behind Apache with ``mod_wsgi``. This file
is installed with the rest of the Aodh application code, and should not need to
be modified.

You can then configure Apache with something like this::

    Listen 8042

    <VirtualHost *:8042>
        WSGIDaemonProcess aodh-api processes=2 threads=10 user=SOMEUSER display-name=%{GROUP}
        WSGIProcessGroup aodh-api
        WSGIScriptAlias / /usr/lib/python2.7/dist-packages/aodh/api/app
        WSGIApplicationGroup %{GLOBAL}
        <IfVersion >= 2.4>
            ErrorLogFormat "%{cu}t %M"
        </IfVersion>
        ErrorLog /var/log/httpd/aodh_error.log
        CustomLog /var/log/httpd/aodh_access.log combined
    </VirtualHost>

    WSGISocketPrefix /var/run/httpd


Modify the ``WSGIDaemonProcess`` directive to set the ``user`` and ``group``
values to an appropriate user on your server. In many installations ``aodh``
will be correct.
