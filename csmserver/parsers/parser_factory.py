# =============================================================================
# Copyright (c) 2015, Cisco Systems, Inc
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
import abc

from platforms.base import BaseInventoryParser
from platforms.eXR import EXRSoftwarePackageParser
from platforms.IOS_XE import IOSXESoftwarePackageParser
from platforms.IOS import IOSSoftwarePackageParser
from platforms.IOS_XR import IOSXRSoftwarePackageParser
from platforms.IOS_XR import IOSXRSatelliteParser
from platforms.IOS_XR import ASR9KInventoryParser
from platforms.NX_OS import NXOSSoftwarePackageParser
from platforms.NX_OS import NXOSInventoryParser


class ParserFactory(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def create_software_package_parser(self):
        """
        return the parser for parsing and setting the software package info
        :return: parser object
        """
        return

    def create_inventory_parser(self):
        """
        return the parser for parsing and storing the inventory info
        :return: parser object
        """
        return BaseInventoryParser()

    def create_satellite_parser(self):
        return None


class EXRParserFactory(ParserFactory):

    def create_software_package_parser(self):
        return EXRSoftwarePackageParser()


class IOSXEParserFactory(ParserFactory):

    def create_software_package_parser(self):
        return IOSXESoftwarePackageParser()


class IOSParserFactory(ParserFactory):

    def create_software_package_parser(self):
        return IOSSoftwarePackageParser()


class IOSXRParserFactory(ParserFactory):

    def create_software_package_parser(self):
        return IOSXRSoftwarePackageParser()

    def create_satellite_parser(self):
        return IOSXRSatelliteParser()


class ASR9KParserFactory(IOSXRParserFactory):

    def create_inventory_parser(self):
        return ASR9KInventoryParser()


class NXOSParserFactory(ParserFactory):

    def create_software_package_parser(self):
        return NXOSSoftwarePackageParser()

    def create_inventory_parser(self):
        return NXOSInventoryParser()
