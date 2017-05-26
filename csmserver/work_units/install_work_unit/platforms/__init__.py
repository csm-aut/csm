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
from base import BaseInstallWorkUnit, InstallPendingMonitoringWorkUnit, MonitorWorkUnit
from constants import InstallJobType
from IOS_XE import IOSXEInstallPendingMonitoringWorkUnit


class BaseInstallWorkUnitFactory(object):
    def get_work_unit(self, install_job):
        if install_job.job_type == InstallJobType.MONITOR:
            print "{} is a monitor job".format(install_job.install_action)
            return self.create_monitor_work_unit(install_job)
        else:
            if self.need_monitor_job_for_install_job(install_job):
                return self.create_install_pending_monitor_work_unit(install_job)
            else:
                return self.create_install_work_unit(install_job)

    def create_monitor_work_unit(self, install_job):
        return MonitorWorkUnit(install_job.host_id, install_job.id)

    def create_install_work_unit(self, install_job):
        return BaseInstallWorkUnit(install_job.host_id, install_job.id)

    def create_install_pending_monitor_work_unit(self, install_job):
        work_unit_class = self.get_monitor_handler_class()
        return work_unit_class(install_job.host_id, install_job.id)

    def get_monitor_handler_class(self):
        return InstallPendingMonitoringWorkUnit

    def need_monitor_job_for_install_job(self, install_job):
        return self.get_monitor_handler_class().monitor_action_exists_for_install_action(install_job.install_action)


class IOSXEInstallWorkUnitFactory(BaseInstallWorkUnitFactory):
    def get_monitor_handler_class(self):
        return IOSXEInstallPendingMonitoringWorkUnit
