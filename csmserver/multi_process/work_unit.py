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
class WorkUnit(object):
    """
    A WorkUnit instance defines the Work which will be processed by a worker as defined
    in the process_pool class.  The Job Manager handles the dispatching of the WorkUnit.
    It allows only one unique instance of the WorkUnit as defined by get_unique_key()
    to be executed.
    """
    def __init__(self):
        self.in_progress_jobs = None
        self.lock = None

    def process(self, db_session, logger, process_name):
        try:
            self.start(db_session, logger, process_name)
        except Exception:
            logger.exception("WorkUnit.process() hit exception")
        finally:
            if self.in_progress_jobs is not None and self.lock is not None:
                with self.lock:
                    if self.get_unique_key() in self.in_progress_jobs:
                        self.in_progress_jobs.remove(self.get_unique_key())

    def start(self, db_session, logger, process_name):
        raise NotImplementedError("Children must override start()")

    def get_unique_key(self):
        """
        Returns an unique value which represents this instance.  An example is an
        unique prefix with the job id from a specific DB table (e.g. email_job_1).
        """
        raise NotImplementedError("Children must override get_unique_key()")