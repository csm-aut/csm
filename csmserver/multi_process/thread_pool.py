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
import threading
from utils import import_module
from database import DBSession
from models import logger
        
## Item pushed on the work queue to tell the worker threads to terminate
SENTINEL = "QUIT"

def is_sentinel(obj):
    """Predicate to determine whether an item from the queue is the
    signal to stop"""
    return type(obj) is str and obj == SENTINEL

class PoolWorker(threading.Thread):
    """Thread that consumes WorkUnits from a queue to process them"""
    def __init__(self, workq, *args, **kwds):
        """\param workq: Queue object to consume the work units from"""
        threading.Thread.__init__(self, *args, **kwds)
        self._workq = workq

    def run(self):
        """Process the work unit, or wait for sentinel to exit"""
        while 1:
            workunit = self._workq.get()
            if is_sentinel(workunit):
                # Got sentinel
                break

            # Run the job / sequence
            workunit.process(DBSession(), logger, self.name)


class Pool(object):
    """
    The Pool class represents a pool of worker threads. It has methods
    which allows tasks to be offloaded to the worker processes in a
    few different ways
    """

    def __init__(self, num_workers, name="Pool"):
        """
        \param nworkers (integer) number of worker threads to start
        \param name (string) prefix for the worker threads' name
        """ 
        # Python 2.7.6 use Queue, Python 3.3 use queue
        queue_module = import_module('Queue')
        if queue_module is None:
            queue_module = import_module('queue')
            
        self._workq   = queue_module.Queue()  
  
        self._closed  = False
        self._workers = []
        for idx in range(num_workers):
            thr = PoolWorker(self._workq, name="Worker-%s-%d" % (name, idx))
            try:
                thr.start()
            except:
                # If one thread has a problem, undo everything
                self.terminate()
                raise
            else:
                self._workers.append(thr)

    def submit(self, work_unit):
        self._workq.put(work_unit)
    
    
    def close(self):
        """Prevents any more tasks from being submitted to the
        pool. Once all the tasks have been completed the worker
        processes will exit."""
        # No lock here. We assume it's sufficiently atomic...
        self._closed = True

    def terminate(self):
        """Stops the worker processes immediately without completing
        outstanding work. When the pool object is garbage collected
        terminate() will be called immediately."""
        self.close()

        # Clearing the job queue
        try:
            while 1:
                self._workq.get_nowait()
        #except Queue.empty():
        except:
            pass

        # Send one sentinel for each worker thread: each thread will die
        # eventually, leaving the next sentinel for the next thread
        for thr in self._workers:
            self._workq.put(SENTINEL)

if __name__ == "__main__":
    print('begin')



