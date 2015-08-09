#!/bin/sh
oslo-config-generator --output-file etc/aodh/aodh.conf \
                      --namespace aodh \
                      --namespace oslo.db \
                      --namespace oslo.log \
                      --namespace oslo.messaging \
                      --namespace oslo.policy \
                      --namespace oslo.service.service \
                      --namespace keystonemiddleware.auth_token
