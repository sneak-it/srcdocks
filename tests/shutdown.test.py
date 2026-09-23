#!/usr/bin/env python3
"""Stops main.cpp with SIGTERM while a fake server takes a second to shut down, as srcds does.

When PID 1 exits the kernel SIGKILLs the rest of the container, so main has to outlive the server.
"""

import signal
import subprocess
import tempfile
import time
from pathlib import Path

SOURCE = Path(__file__).parents[1] / 'srcds' / 'main.cpp'

tmp = Path(tempfile.mkdtemp())

# Like runServer.sh and srcds_run, the wrapper does not exec, so the server outlives it on SIGTERM
(tmp / 'linkLatest.sh').write_text('#!/bin/sh\nexit 0\n')
(tmp / 'runServer.sh').write_text(f'#!/bin/bash\nbash {tmp}/server.sh\n')
(tmp / 'server.sh').write_text(f'trap "sleep 1; touch {tmp}/clean; exit 0" TERM\n'
                               f'touch {tmp}/started\n'
                               'while :; do sleep 0.1; done\n')
for script in ('linkLatest.sh', 'runServer.sh'):
    (tmp / script).chmod(0o755)

(tmp / 'main.cpp').write_text(SOURCE.read_text().replace('/srcds/', f'{tmp}/'))
subprocess.run(['g++', '-Wall', '-Wextra', '-Werror', '-o', tmp / 'main', tmp / 'main.cpp'], check=True)

# A session of its own, because main signals its whole process group
main = subprocess.Popen([tmp / 'main'], start_new_session=True)
deadline = time.time() + 10
while not (tmp / 'started').exists():
    assert time.time() < deadline, 'fake server never started'
    time.sleep(0.05)

main.send_signal(signal.SIGTERM)
main.wait(timeout=10)
assert (tmp / 'clean').exists(), 'main exited before the server finished shutting down'

print('all ok')
