# =============================================================================
# Copyright (c) 2016, Cisco Systems, Inc
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
# =============================================================================
from base import InstallPendingMonitoringWorkUnit
from constants import JobStatus, InstallAction


class IOSXEInstallPendingMonitoringWorkUnit(InstallPendingMonitoringWorkUnit):
    """
    This class specifies which install actions for IOS XE devices need monitor jobs upon completion,
    and schedules the appropriate monitor jobs.

    The monitor_info object defines the specifications for the monitor jobs.

    regarding monitor_info object:
    It's a dictionary object. Keys are the install actions for which we need monitor jobs.
    Each key is mapped against a list with 3 items that describe the monitor job
    that need to be created upon the completion of this install action
    1. install action for the monitor job
    2. max number of trials before we stop running the monitor job and declare failure of the install job
    3. a list of tuples that define the time intervals between executions of the monitor job, in the following format:
        [(0, time interval in seconds between consecutive executions starting from trial count 0 until the next trial count in this list),
         (trial count k, time interval in seconds between consecutive executions starting from this trial count k until the next trial count in this list),
         ...
         (trial count n, time interval in seconds between consecutive executions starting from this trial count n until the max number of trials is reached)
        ]
       example: [(0, 1800), (1, 300)] => from trial count 0 to 1, time interval is 30 minutes(1800 seconds),
                                         from trial count 1 to max trial numbers allowed, time interval is 5 minutes(300 seconds) between each trial
    """
    monitor_info = {InstallAction.INSTALL_ADD: [InstallAction.ADD_MONITOR, 10, [(0, 900)]],
                    InstallAction.INSTALL_ACTIVATE: [InstallAction.ACTIVATE_MONITOR, 5, [(0, 1800), (1, 300)]]}
