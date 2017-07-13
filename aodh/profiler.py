# Copyright 2017 Fujitsu Ltd.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import socket

from oslo_log import log
from oslo_utils import importutils
import webob.dec

profiler = importutils.try_import('osprofiler.profiler')
profiler_initializer = importutils.try_import('osprofiler.initializer')
profiler_web = importutils.try_import('osprofiler.web')

LOG = log.getLogger(__name__)


class WsgiMiddleware(object):

    def __init__(self, application, **kwargs):
        self.application = application

    @classmethod
    def factory(cls, global_conf, **local_conf):
        if profiler_web:
            return profiler_web.WsgiMiddleware.factory(global_conf)

        def filter_(app):
            return cls(app)

        return filter_

    @webob.dec.wsgify
    def __call__(self, request):
        return request.get_response(self.application)


def setup(conf):
    if hasattr(conf, 'profiler') and conf.profiler.enabled:
        profiler_initializer.init_from_conf(
            conf=conf,
            context={},
            project=conf.project,
            service=conf.prog,
            host=socket.gethostbyname(socket.gethostname()))
        LOG.info('OSprofiler is enabled.')


def trace_cls(name, **kwargs):
    """Wrap the OSprofiler trace_cls.

    Wrap the OSprofiler trace_cls decorator so that it will not try to
    patch the class unless OSprofiler is present.

    :param name: The name of action. For example, wsgi, rpc, db, ...
    :param kwargs: Any other keyword args used by profiler.trace_cls
    """

    def decorator(cls):
        if profiler:
            trace_decorator = profiler.trace_cls(name, **kwargs)
            return trace_decorator(cls)
        return cls

    return decorator
