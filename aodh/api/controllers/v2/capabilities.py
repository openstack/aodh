#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 IBM Corp.
# Copyright 2013 eNovance <licensing@enovance.com>
# Copyright Ericsson AB 2013. All rights reserved
# Copyright 2014 Hewlett-Packard Company
# Copyright 2015 Huawei Technologies Co., Ltd.
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

import pecan
from pecan import rest
import six
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from aodh.api.controllers.v2 import base


def _decode_unicode(input):
    """Decode the unicode of the message, and encode it into utf-8."""
    if isinstance(input, dict):
        temp = {}
        # If the input data is a dict, create an equivalent dict with a
        # predictable insertion order to avoid inconsistencies in the
        # message signature computation for equivalent payloads modulo
        # ordering
        for key, value in sorted(six.iteritems(input)):
            temp[_decode_unicode(key)] = _decode_unicode(value)
        return temp
    elif isinstance(input, (tuple, list)):
        # When doing a pair of JSON encode/decode operations to the tuple,
        # the tuple would become list. So we have to generate the value as
        # list here.
        return [_decode_unicode(element) for element in input]
    elif isinstance(input, six.text_type):
        return input.encode('utf-8')
    else:
        return input


def _recursive_keypairs(d, separator=':'):
    """Generator that produces sequence of keypairs for nested dictionaries."""
    for name, value in sorted(six.iteritems(d)):
        if isinstance(value, dict):
            for subname, subvalue in _recursive_keypairs(value, separator):
                yield ('%s%s%s' % (name, separator, subname), subvalue)
        elif isinstance(value, (tuple, list)):
            yield name, _decode_unicode(value)
        else:
            yield name, value


def _flatten_capabilities(capabilities):
    return dict((k, v) for k, v in _recursive_keypairs(capabilities))


class Capabilities(base.Base):
    """A representation of the API and storage capabilities.

    Usually constrained by restrictions imposed by the storage driver.
    """

    api = {wtypes.text: bool}
    "A flattened dictionary of API capabilities"
    alarm_storage = {wtypes.text: bool}
    "A flattened dictionary of alarm storage capabilities"

    @classmethod
    def sample(cls):
        return cls(
            api=_flatten_capabilities({
                'alarms': {'query': {'simple': True,
                                     'complex': True},
                           'history': {'query': {'simple': True,
                                                 'complex': True}}},
            }),
            alarm_storage=_flatten_capabilities(
                {'storage': {'production_ready': True}}),
        )


class CapabilitiesController(rest.RestController):
    """Manages capabilities queries."""

    @wsme_pecan.wsexpose(Capabilities)
    def get(self):
        """Returns a flattened dictionary of API capabilities.

        Capabilities supported by the currently configured storage driver.
        """
        # variation in API capabilities is effectively determined by
        # the lack of strict feature parity across storage drivers
        alarm_conn = pecan.request.storage
        driver_capabilities = {
            'alarms': alarm_conn.get_capabilities()['alarms'],
        }
        alarm_driver_perf = alarm_conn.get_storage_capabilities()
        return Capabilities(api=_flatten_capabilities(driver_capabilities),
                            alarm_storage=_flatten_capabilities(
                                alarm_driver_perf))
