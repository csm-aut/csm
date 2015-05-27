# =============================================================================
# exceptions
#
# Copyright (c)  2014, Cisco Systems
# All rights reserved.
#
# # Author: Klaudiusz Staniek
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


class GeneralError(Exception):
    """General error"""
    def __init__(self, message=None, host=None):
        self.message = message
        self.host = host

    def __str__(self):
        message = self.message or self.__class__.__doc__
        return "{}: {}".format(self.host, message) if self.host else message


class ConnectionError(GeneralError):
    """General connection error"""
    pass


class ConnectionAuthenticationError(ConnectionError):
    """Connection authentication error"""
    pass


class ConnectionTimeoutError(ConnectionError):
    """Connection timeout error"""
    pass


class CommandError(GeneralError):
    """Command execution error"""
    def __init__(self, message=None, host=None, command=None):
        GeneralError.__init__(self, message, host)
        self.command = command

    def __str__(self):
        message = self.message or self.__class__.__doc__
        message = "{}: '{}'".format(message, self.command) \
            if self.command else message
        message = "{}: {}".format(self.host, message) \
            if self.host else message
        return message


class CommandSyntaxError(CommandError):
    """Command syntax error"""
    pass


class CommandTimeoutError(CommandError):
    """Command timeout error"""
    pass


class InvalidHopInfoError(GeneralError):
    """Invalid device connection parameters"""
    pass


