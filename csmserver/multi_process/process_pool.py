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
from multiprocessing import Process, Manager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.engine.url import URL
from database import db_settings, ENABLE_DEBUG
from models import get_db_session_logger
        
# Item pushed on the work queue to tell the worker threads to terminate
SENTINEL = "QUIT"


def is_sentinel(obj):
    """Predicate to determine whether an item from the queue is the
    signal to stop"""
    return type(obj) is str and obj == SENTINEL


class PoolWorker(Process):
    """Thread that consumes WorkUnits from a queue to process them"""
    def __init__(self, queue, *args, **kwds):
        """\param workq: Queue object to consume the work units from"""
        Process.__init__(self, *args, **kwds)
        self.queue = queue

        DATABASE_CONNECTION_INFO = URL(**db_settings)
        # Create the database engine
        engine = create_engine(DATABASE_CONNECTION_INFO, pool_size=20, pool_recycle=3600,
                               convert_unicode=True, echo=ENABLE_DEBUG)
        self.db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))()

        self.logger = get_db_session_logger(self.db_session)

    def run(self):
        """Process the work unit, or wait for sentinel to exit"""
        while 1:
            work_unit = self.queue.get()
            if is_sentinel(work_unit):
                # Got sentinel
                break

            # Run the job / sequence
            work_unit.process(self.db_session, self.logger, self.name)


class Pool(object):
    """
    The Pool class represents a pool of worker threads. It has methods
    which allows tasks to be offloaded to the worker processes in a
    few different ways
   """
    def __init__(self, num_workers, name="Pool"):
        """
        \param num_workers (integer) number of worker threads to start
        \param name (string) prefix for the worker threads' name
        """
        self.queue = Manager().Queue()
        self.closed = False
        self.workers = []

        for idx in range(num_workers):
            process = PoolWorker(self.queue, name="%s-Worker-%d" % (name, idx))
            process.daemon = True
            try:
                process.start()
            except:
                # If one thread has a problem, undo everything
                self.terminate()
                raise
            else:
                self.workers.append(process)

    def submit(self, work_unit):
        self.queue.put(work_unit)
    
    def close(self):
        """Prevents any more tasks from being submitted to the
        pool. Once all the tasks have been completed the worker
        processes will exit."""
        # No lock here. We assume it's sufficiently atomic...
        self.closed = True

    def terminate(self):
        """Stops the worker processes immediately without completing
        outstanding work. When the pool object is garbage collected
        terminate() will be called immediately."""
        self.close()

        # Clearing the job queue
        try:
            while 1:
                self.queue.get_nowait()
        # except Manager().Queue.empty():
        except:
            pass

        # Send one sentinel for each worker thread: each thread will die
        # eventually, leaving the next sentinel for the next thread
        for process in self.workers:
            self.queue.put(SENTINEL)

    
class WorkUnit(object):

    def process(self, db_session, logger, process_name):
        """Do the work. Shouldn't raise any exception"""
        raise NotImplementedError("Children must override Process")

if __name__ == "__main__":
    pass

