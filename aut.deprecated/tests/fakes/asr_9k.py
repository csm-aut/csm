# =============================================================================
# -*- coding: utf-8 -*-
#
# asr_9k.py - Fake ASR9k Implementation
#
# Copyright (c) 2014, Cisco Systems
# All rights reserved.
#
# Author: Klaudiusz Staniek
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

commands = {
    'show redundancy': (
        """RP/0/RSP0/CPU0:test#sh redundancy
Fri Feb 21 03:57:05.394 CET
Redundancy information for node 0/RSP0/CPU0:
==========================================
Node 0/RSP0/CPU0 is in ACTIVE role
Node Redundancy Partner (0/RSP1/CPU0) is in STANDBY role
Standby node in 0/RSP1/CPU0 is ready
Standby node in 0/RSP1/CPU0 is NSR-ready
Node 0/RSP0/CPU0 is in process group PRIMARY role
Process Redundancy Partner (0/RSP1/CPU0) is in BACKUP role
Backup node in 0/RSP1/CPU0 is ready
Backup node in 0/RSP1/CPU0 is NSR-ready

Group            Primary         Backup          Status
---------        ---------       ---------       ---------
v6-routing       0/RSP0/CPU0     0/RSP1/CPU0     Ready
mcast-routing    0/RSP0/CPU0     0/RSP1/CPU0     Ready
netmgmt          0/RSP0/CPU0     0/RSP1/CPU0     Ready
v4-routing       0/RSP0/CPU0     0/RSP1/CPU0     Ready
central-services 0/RSP0/CPU0     0/RSP1/CPU0     Ready
dlrsc            0/RSP0/CPU0     0/RSP1/CPU0     Ready
dsc              0/RSP0/CPU0     0/RSP1/CPU0     Ready

Reload and boot info
----------------------
A9K-RSP440-TR reloaded Fri Feb 21 02:35:02 2014: 1 hour, 22 minutes ago
Active node booted Fri Feb 21 03:25:27 2014: 31 minutes ago
Last switch-over Fri Feb 21 03:32:49 2014: 24 minutes ago
Standby node boot Fri Feb 21 03:33:26 2014: 23 minutes ago
Standby node last went not ready Fri Feb 21 03:37:26 2014: 19 minutes ago
Standby node last went ready Fri Feb 21 03:37:26 2014: 19 minutes ago
There have been 2 switch-overs since reload

Active node reload "Cause: MBI-HELLO reloading node on receiving reload notification"
Standby node reload "Cause: Initiating switch-over."

RP/0/RSP0/CPU0:test#""",
    ),
    'show redundancy summary': (
        """Fri Feb 21 04:00:57.606 CET
Active/Primary   Standby/Backup
--------------   --------------
0/RSP0/CPU0(A)   0/RSP1/CPU0(S) (Node Ready, NSR: Ready)
0/RSP0/CPU0(P)   0/RSP1/CPU0(B) (Proc Group Ready, NSR: Ready)""",
    ),
    'admin show redundancy location all': (
        """Fri Feb 21 04:15:07.603 CET
Redundancy information for node 0/RSP0/CPU0:
==========================================
Node 0/RSP0/CPU0 is in ACTIVE role
Node Redundancy Partner (0/RSP1/CPU0) is in STANDBY role
Standby node in 0/RSP1/CPU0 is ready
Standby node in 0/RSP1/CPU0 is NSR-ready
Node 0/RSP0/CPU0 is in process group PRIMARY role
Process Redundancy Partner (0/RSP1/CPU0) is in BACKUP role
Backup node in 0/RSP1/CPU0 is ready
Backup node in 0/RSP1/CPU0 is NSR-ready

Group            Primary         Backup          Status
---------        ---------       ---------       ---------
v6-routing       0/RSP0/CPU0     0/RSP1/CPU0     Ready
mcast-routing    0/RSP0/CPU0     0/RSP1/CPU0     Ready
netmgmt          0/RSP0/CPU0     0/RSP1/CPU0     Ready
v4-routing       0/RSP0/CPU0     0/RSP1/CPU0     Ready
central-services 0/RSP0/CPU0     0/RSP1/CPU0     Ready
dlrsc            0/RSP0/CPU0     0/RSP1/CPU0     Ready
dsc              0/RSP0/CPU0     0/RSP1/CPU0     Ready

Reload and boot info
----------------------
A9K-RSP440-TR reloaded Fri Feb 21 02:35:02 2014: 1 hour, 40 minutes ago
Active node booted Fri Feb 21 03:25:27 2014: 49 minutes ago
Last switch-over Fri Feb 21 03:32:49 2014: 42 minutes ago
Standby node boot Fri Feb 21 03:33:26 2014: 41 minutes ago
Standby node last went not ready Fri Feb 21 03:37:26 2014: 37 minutes ago
Standby node last went ready Fri Feb 21 03:37:26 2014: 37 minutes ago
There have been 2 switch-overs since reload

Active node reload "Cause: MBI-HELLO reloading node on receiving reload notification"
Standby node reload "Cause: Initiating switch-over."
"""
    )
}


class ASR9k(object):
    @classmethod
    def execute_command(cls, command):
        ret_success = commands[command][0]
        return ret_success

    @classmethod
    def is_commnad(cls, command):
        return command in commands

    @classmethod
    def get_prompt(cls):
        return "RP/0/RSP0/CPU0:test#"

    @classmethod
    def invalid_command(cls):
        return "% Invalid input detected at '^' marker."
