#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2015 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import os

from oslo_config import cfg
from oslo_log import log
from paste import deploy
import pecan
from werkzeug import serving

from aodh.api import hooks
from aodh.api import middleware
from aodh.i18n import _
from aodh.i18n import _LW
from aodh import service
from aodh import storage

LOG = log.getLogger(__name__)

PECAN_CONFIG = {
    'app': {
        'root': 'aodh.api.controllers.root.RootController',
        'modules': ['aodh.api'],
    },
}


def setup_app(pecan_config=PECAN_CONFIG, conf=None):
    if conf is None:
        # NOTE(jd) That sucks but pecan forces us to use kwargs :(
        raise RuntimeError("Config is actually mandatory")
    # FIXME: Replace DBHook with a hooks.TransactionHook
    app_hooks = [hooks.ConfigHook(conf),
                 hooks.DBHook(
                     storage.get_connection_from_config(conf)),
                 hooks.TranslationHook()]

    pecan.configuration.set_config(dict(pecan_config), overwrite=True)

    # NOTE(sileht): pecan debug won't work in multi-process environment
    pecan_debug = conf.api.pecan_debug
    if conf.api.workers != 1 and pecan_debug:
        pecan_debug = False
        LOG.warning(_LW('pecan_debug cannot be enabled, if workers is > 1, '
                        'the value is overrided with False'))

    app = pecan.make_app(
        pecan_config['app']['root'],
        debug=pecan_debug,
        hooks=app_hooks,
        wrap_app=middleware.ParsableErrorMiddleware,
        guess_content_type_from_ext=False
    )

    return app


def load_app(conf):
    # Build the WSGI app
    cfg_file = None
    cfg_path = conf.api.paste_config
    if not os.path.isabs(cfg_path):
        cfg_file = conf.find_file(cfg_path)
    elif os.path.exists(cfg_path):
        cfg_file = cfg_path

    if not cfg_file:
        raise cfg.ConfigFilesNotFoundError([conf.api.paste_config])
    LOG.info("Full WSGI config used: %s" % cfg_file)
    return deploy.loadapp("config:" + cfg_file)


def build_server(conf):
    app = load_app(conf)
    # Create the WSGI server and start it
    host, port = conf.api.host, conf.api.port

    LOG.info(_('Starting server in PID %s') % os.getpid())
    LOG.info(_("Configuration:"))
    conf.log_opt_values(LOG, logging.INFO)

    if host == '0.0.0.0':
        LOG.info(_(
            'serving on 0.0.0.0:%(sport)s, view at http://127.0.0.1:%(vport)s')
            % ({'sport': port, 'vport': port}))
    else:
        LOG.info(_("serving on http://%(host)s:%(port)s") % (
                 {'host': host, 'port': port}))

    serving.run_simple(host, port,
                       app, processes=conf.api.workers)


def _app():
    conf = service.prepare_service()
    return setup_app(conf=conf)


def app_factory(global_config, **local_conf):
    return _app()
