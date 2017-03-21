#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2015-2016 Red Hat, Inc.
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

import os
import uuid

from oslo_config import cfg
from oslo_log import log
from paste import deploy
import pecan

from aodh.api import hooks
from aodh.api import middleware
from aodh import service
from aodh import storage

LOG = log.getLogger(__name__)


# NOTE(sileht): pastedeploy uses ConfigParser to handle
# global_conf, since python 3 ConfigParser doesn't
# allow storing object as config value, only strings are
# permit, so to be able to pass an object created before paste load
# the app, we store them into a global var. But the each loaded app
# store it's configuration in unique key to be concurrency safe.
global APPCONFIGS
APPCONFIGS = {}


def setup_app(root, conf):
    app_hooks = [hooks.ConfigHook(conf),
                 hooks.DBHook(
                     storage.get_connection_from_config(conf)),
                 hooks.TranslationHook()]
    return pecan.make_app(
        root,
        hooks=app_hooks,
        wrap_app=middleware.ParsableErrorMiddleware,
        guess_content_type_from_ext=False
    )


def load_app(conf):
    global APPCONFIGS

    # Build the WSGI app
    cfg_path = conf.api.paste_config
    if not os.path.isabs(cfg_path):
        cfg_path = conf.find_file(cfg_path)

    if cfg_path is None or not os.path.exists(cfg_path):
        raise cfg.ConfigFilesNotFoundError([conf.api.paste_config])

    config = dict(conf=conf)
    configkey = str(uuid.uuid4())
    APPCONFIGS[configkey] = config

    LOG.info("WSGI config used: %s", cfg_path)
    return deploy.loadapp("config:" + cfg_path,
                          name="aodh+" + (
                              conf.api.auth_mode
                              if conf.api.auth_mode else "noauth"
                          ),
                          global_conf={'configkey': configkey})


def app_factory(global_config, **local_conf):
    global APPCONFIGS
    appconfig = APPCONFIGS.get(global_config.get('configkey'))
    return setup_app(root=local_conf.get('root'), **appconfig)


def build_wsgi_app(argv=None):
    return load_app(service.prepare_service(argv=argv))
