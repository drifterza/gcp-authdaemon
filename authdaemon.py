#!/usr/bin/env python
# Copyright (C) 2012 Google Inc.
# Copyright (C) 2019 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Background daemon to refresh OAuth access tokens.
Tokens are written to the pathname supplied.

Runs only on Google Compute Engine (GCE).
"""

from __future__ import print_function

import atexit
import contextlib
import json
import os
import platform
import subprocess
import sys
import time
import urllib.request
import urllib.error


REFRESH = 25  # seconds remaining when starting refresh
RETRY_INTERVAL = 5 # seconds between retrying a failed refresh
META_URL = 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/'
SUPPORTED_SCOPES = [
  'https://www.googleapis.com/auth/cloud-platform',
]


def read_meta(part):
    r = urllib.request.Request(META_URL + part)
    r.add_header('Metadata-Flavor', 'Google')
    return contextlib.closing(urllib.request.urlopen(r))


def select_scope():
    with read_meta('scopes') as d:
        data = d.read().decode('utf8')
        avail = set(data.split())
    scopes = [s for s in SUPPORTED_SCOPES if s in avail]
    if scopes:
        return scopes[0]
    sys.stderr.write('error: VM must have one of these scopes:\n\n')
    for s in SUPPORTED_SCOPES:
        sys.stderr.write('  %s\n' % (s))
    sys.exit(1)


def acquire_token(scope, retry):
    while True:
        try:
            with read_meta('token?scopes=' + scope) as d:
                return json.load(d)
        except urllib.error.URLError:
            if not retry:
                raise
        time.sleep(RETRY_INTERVAL)


def update_cookie(scope, retry):
    now = int(time.time())
    token = acquire_token(scope, retry)
    access_token = token['access_token']
    expires = now + int(token['expires_in'])  # Epoch in sec
    path = sys.argv[1]
    tmp_path = path + ".lock"
    with open(tmp_path, 'w') as f:
        f.write(json.dumps(token))
    print('Updating %s.' % path)
    print('Expires: %d, %s, in %d seconds'% (
        expires, time.ctime(expires), expires - now))
    sys.stdout.flush()
    os.rename(tmp_path, path)
    return expires


def refresh_loop(scope, expires):
    expires = expires - REFRESH
    while True:
        now = time.time()
        expires = max(expires, now + RETRY_INTERVAL)
        while now < expires:
            time.sleep(expires - now)
            now = time.time()
        expires = update_cookie(scope, retry=True) - REFRESH


def main():
    scope = select_scope()
    expires = update_cookie(scope, retry=False)
    refresh_loop(scope, expires)


if __name__ == '__main__':
    main()
