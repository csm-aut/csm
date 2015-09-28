# =============================================================================
# Manager
#
# Copyright (c)  2014, Cisco Systems
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


import gc
import os
import sys
import threading
import weakref
import time

from functools import partial

from multiprocessing import Pipe
from au.Logger import logger_registry
from au.LoggerProxy import LoggerProxy
from au.utils.tty import get_terminal_size
from au.utils.impl import format_exception, serializeable_sys_exc_info

from au.utils.cast import to_list
from au.utils.impl import get_label
from au.utils.log import log_to_file
from au.utils.decorators import pre_upgrade
from au.utils.decorators import upgrade
from au.utils.decorators import post_upgrade
from au.utils.decorators import cli_cmd_file
from au.utils.decorators import repository
from au.utils.decorators import pkg_file
from au.utils.decorators import turbo_boot
from au.utils.decorators import issu
from au.utils.decorators import best_effort_config
from au.utils import pkglist

from au.workqueue.WorkQueue import WorkQueue
from au.workqueue.Task import Task

from au.plugins import plugin_map


HEADER = '\033[96m'
OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'


def _prepare_plugin(func):
    """
    A decorator that unpacks the host and connection from the job argument
    and passes them as separate arguments to the wrapped function.
    """
    def _wrapped(job, *args, **kwargs):
        def job_rename(job, name):
            job.name = name

        job_id = id(job)
        to_parent = job.data['pipe']
        device = job.data['device']

        cli_cmd = get_label(func, 'cmd_file')
        repo_url = get_label(func, 'repository')
        pkg_file = get_label(func, 'pkg_file')
        turbo_boot = get_label(func, 'turbo_boot')
        issu = get_label(func, 'issu')
        best_effort_config = get_label(func, 'best_effort_config')
        log_options = get_label(func, 'log_to')
        pre_upgrade = get_label(func, 'pre_upgrade')
        upgrade = get_label(func, 'upgrade')
        post_upgrade = get_label(func, 'post_upgrade')

        kwargs.update(pre_upgrade)
        kwargs.update(upgrade)
        kwargs.update(post_upgrade)
        kwargs.update(cli_cmd)
        if repo_url :
            kwargs.update(repo_url)
        if pkg_file :
            kwargs.update(pkg_file)
        if issu :
            kwargs.update(issu)
        if best_effort_config:
            kwargs.update(best_effort_config)
        kwargs.update(turbo_boot)

        if log_options is not None:
            # Enable logging.
            proxy = LoggerProxy(to_parent, log_options['logger_id'])
            log_cb = partial(proxy.log, job_id)
            rename_log_cb = partial(proxy.rename_log, job_id)
            job_rename_cb = partial(job_rename, job)
            proxy.add_log(job_id, device.name, job.failures + 1)
            try:
                device.command_output_received.listen(log_cb)
                device.name_changed.listen(rename_log_cb)
                device.name_changed.listen(job_rename_cb)
                result = func(job, device, *args, **kwargs)
            except:
                proxy.log_aborted(job_id, serializeable_sys_exc_info())
                raise
            else:
                proxy.log_succeeded(job_id)
            finally:
                device.command_output_received.disconnect(log_cb)
                device.name_changed.disconnect(rename_log_cb)
                device.name_changed.disconnect(job_rename_cb)
        else:
            #conn.connect(host.get_address(), host.get_tcp_port())
            result = func(job, device, *args, **kwargs)
            #conn.close(force = True)
        return result

    return _wrapped


def _is_recoverable_error(cls):
    # Hack: We can't use isinstance(), because the classes may
    # have been created by another python process; apparently this
    # will cause isinstance() to return False.
    return cls.__name__ in (
        'CompileError', 'FailException', 'PluginError', 'DeviceError')


def _call_logger(funcname, logger_id, *args):
    logger = logger_registry.get(logger_id)
    if not logger:
        return
    return getattr(logger, funcname)(*args)


class _PipeHandler(threading.Thread):

    """
    Each PipeHandler holds an open pipe to a subprocess, to allow the
    sub-process to access the manager and communicate status information.
    """

    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.to_child, self.to_parent = Pipe()

    def _handle_request(self, request):
        try:
            command, arg = request
            if command == 'log-add':
                log = _call_logger('add_log', *arg)
                self.to_child.send(log)
            elif command == 'log-rename':
                log = _call_logger('rename_log', *arg)
                self.to_child.send(log)
            elif command == 'log-message':
                _call_logger('log', *arg)
            elif command == 'log-aborted':
                _call_logger('log_aborted', *arg)
            elif command == 'log-succeeded':
                _call_logger('log_succeeded', *arg)
            else:
                raise Exception('invalid command on pipe: ' + repr(command))
        except Exception, e:
            self.to_child.send(e)
            raise

    def run(self):
        while True:
            try:
                request = self.to_child.recv()
            except (EOFError, IOError):
                break
            self._handle_request(request)


class Manager(object):

    def __init__(self,
                 devices,
                 options,
                 verbose=0,
                 mode='threading',
                 max_threads=1,
                 stdout=sys.stdout,
                 stderr=sys.stderr):

        self.devices = to_list(devices)
        self.workqueue = WorkQueue(mode=mode)
        self.pipe_handlers = weakref.WeakValueDictionary()
        self.verbose = verbose
        self.stdout = options.stdoutfile
        self.stderr = options.stdoutfile
        self.devnull = open(os.devnull, 'w')
        self.channel_map = {
            'fatal_errors': self.stderr,
            'debug': self.stdout
        }
        self.completed = 0
        self.total = 0
        self.failed = 0
        self.failed_devices = set()
        self.status_bar_length = 0
        self.set_max_threads(max_threads)

        self.task = None

        # Listen to what the workqueue is doing.
        self.workqueue.job_init_event.listen(self._on_job_init)
        self.workqueue.job_started_event.listen(self._on_job_started)
        self.workqueue.job_error_event.listen(self._on_job_error)
        self.workqueue.job_succeeded_event.listen(self._on_job_succeeded)
        self.workqueue.job_aborted_event.listen(self._on_job_aborted)

        self.options = options

    def _update_verbosity(self):
        if self.verbose < 0:
            self.channel_map['status_bar'] = self.devnull
            self.channel_map['connection'] = self.devnull
            self.channel_map['errors'] = self.devnull
            self.channel_map['tracebacks'] = self.devnull
        elif self.verbose == 0:
            self.channel_map['status_bar'] = self.devnull
            self.channel_map['connection'] = self.devnull
            self.channel_map['errors'] = self.stderr
            self.channel_map['tracebacks'] = self.devnull
        elif self.verbose == 1 and self.get_max_threads() == 1:
            self.channel_map['status_bar'] = self.devnull
            self.channel_map['connection'] = self.stdout
            self.channel_map['errors'] = self.stderr
            self.channel_map['tracebacks'] = self.devnull
        elif self.verbose == 1:
            self.channel_map['status_bar'] = self.stdout
            self.channel_map['connection'] = self.devnull
            self.channel_map['errors'] = self.stderr
            self.channel_map['tracebacks'] = self.devnull
        elif self.verbose >= 2 and self.get_max_threads() == 1:
            self.channel_map['status_bar'] = self.devnull
            self.channel_map['connection'] = self.stdout
            self.channel_map['errors'] = self.stderr
            self.channel_map['tracebacks'] = self.stderr
        elif self.verbose >= 2:
            self.channel_map['status_bar'] = self.stdout
            self.channel_map['connection'] = self.devnull
            self.channel_map['errors'] = self.stderr
            self.channel_map['tracebacks'] = self.stderr

    def _write(self, channel, msg):
        self.channel_map[channel].write(msg)
        self.channel_map[channel].flush()

    def _create_pipe(self):
        """
        Creates a new pipe and returns the child end of the connection.
        To request an account from the pipe, use::

            pipe = queue._create_pipe()

            # Let the account manager choose an account.
            pipe.send(('acquire-account-for-host', host))
            account = pipe.recv()
            ...
            pipe.send(('release-account', account.id()))

            # Or acquire a specific account.
            pipe.send(('acquire-account', account.id()))
            account = pipe.recv()
            ...
            pipe.send(('release-account', account.id()))

            pipe.close()
        """
        child = _PipeHandler()
        self.pipe_handlers[id(child)] = child
        child.start()
        return child.to_parent

    def _del_status_bar(self):
        if self.status_bar_length == 0:
            return
        self._write('status_bar', '\b \b' * self.status_bar_length)
        self.status_bar_length = 0

    def get_progress(self):
        """
        Returns the progress in percent.

        @rtype:  float
        @return: The progress in percent.
        """
        if self.total == 0:
            return 0.0
        return 100.0 / self.total * self.completed

    def _print_status_bar(self, exclude=None):
        if self.total == 0:
            return
        percent = 100.0 / self.total * self.completed
        progress = '%d/%d (%d%%)' % (self.completed, self.total, percent)
        jobs = self.workqueue.get_running_jobs()
        running = '|'.join([j.name for j in jobs if j.name != exclude])
        if not running:
            self.status_bar_length = 0
            return
        rows, cols = get_terminal_size()
        text = 'Plugin Manager: [{}] {}'.format(running, progress)
        overflow = len(text) - cols
        if overflow > 0:
            cont = '...'
            overflow += len(cont) + 1
            strlen = len(running)
            partlen = (strlen / 2) - (overflow / 2)
            head = running[:partlen]
            tail = running[-partlen:]
            running = head + cont + tail
            text = 'Plugin Manager: [{}] {}'.format(running, progress)

        self._write('status_bar', text)
        self.status_bar_length = len(text)

    def _print(self, channel, msg):
        self._del_status_bar()
        self._write(channel, msg + '\n')
        self._print_status_bar()

    def _dbg(self, level, msg):
        if level > self.verbose:
            return
        self._print('debug', "Plugin Manager: {}".format(msg))

    def _on_job_init(self, job):
        if job.data is None:
            job.data = {}
        job.data['pipe'] = self._create_pipe()
        job.data['stdout'] = self.channel_map['connection']

    def _on_job_destroy(self, job):
        job.data['pipe'].close()

    def _on_job_started(self, job):
        message = "{}\n{}\n{}: Plugin started for node '{}'".format(
            "+" * 80,
            time.asctime(),
            self.task.name,
            job.name)
        self._print('status_bar', message)
        self._del_status_bar()
        self._print_status_bar()

    def _on_job_error(self, job, exc_info):
        msg = "{}: {} error: {}".format(
            self.task.name,
            job.name,
            str(exc_info[1])
        )
        trace = ''.join(format_exception(*exc_info))
        self._print('errors', msg)
        if _is_recoverable_error(exc_info[0]):
            self._print('tracebacks', trace)
        else:
            self._print('fatal_errors', trace)

    def _on_job_succeeded(self, job):
        message = "{}: Plugin succeeded for node '{}'".format(
            self.task.name,
            job.name)

        #    job.data['job_name'])

        self._on_job_destroy(job)
        self.completed += 1
        self._print('status_bar', message)
        self._del_status_bar()
        self._print_status_bar(exclude=job.name)

    def _on_job_aborted(self, job):
        message = "{}: Plugin execution for node '{}' finally failed".format(
            self.task.name,
            job.name)

        self._on_job_destroy(job)
        self.completed += 1
        self.failed += 1
        if not self.options.ignore_errors:
            self.failed_devices.add(job.data['device'])
        self._print('errors', message)
        self._del_status_bar()
        self._print_status_bar(exclude=job.name)

    def set_max_threads(self, n_connections):
        """
        Sets the maximum number of concurrent connections.

        @type  n_connections: int
        @param n_connections: The maximum number of connections.
        """
        self.workqueue.set_max_threads(n_connections)
        self._update_verbosity()

    def get_max_threads(self):
        """
        Returns the maximum number of concurrent threads.

        @rtype:  int
        @return: The maximum number of connections.
        """
        return self.workqueue.get_max_threads()

    def is_completed(self):
        """
        Returns True if the task is completed, False otherwise.
        In other words, this methods returns True if the queue is empty.

        @rtype:  bool
        @return: Whether all tasks are completed.
        """
        return self.workqueue.get_length() == 0

    def join(self):
        """
        Waits until all jobs are completed.
        """
        self._dbg(2, 'Waiting for the queue to finish.')
        self.workqueue.wait_until_done()
        for child in self.pipe_handlers.values():
            child.join()
        self._del_status_bar()
        self._print_status_bar()
        gc.collect()

    def shutdown(self, force=False):
        """
        Stop executing any further jobs. If the force argument is True,
        the function does not wait until any queued jobs are completed but
        stops immediately.

        After emptying the queue it is restarted, so you may still call run()
        after using this method.

        @type  force: bool
        @param force: Whether to wait until all jobs were processed.
        """
        if not force:
            self.join()

        self._dbg(2, 'Shutting down queue...')
        self.workqueue.shutdown(True)
        self._dbg(2, 'Queue shut down.')
        self._del_status_bar()

    def destroy(self, force=False):
        """
        Like shutdown(), but also removes all accounts, hosts, etc., and
        does not restart the queue. In other words, the queue can no longer
        be used after calling this method.

        @type  force: bool
        @param force: Whether to wait until all jobs were processed.
        """
        try:
            if not force:
                self.join()
        finally:
            self._dbg(2, 'Destroying queue...')
            self.workqueue.destroy()
            self.completed = 0
            self.total = 0
            self.failed = 0
            self.status_bar_length = 0
            self._dbg(2, 'Queue destroyed.')
            self._del_status_bar()

    def reset(self):
        """
        Remove all accounts, hosts, etc.
        """
        self._dbg(2, 'Resetting queue...')
        self.workqueue.shutdown(True)
        self.completed = 0
        self.total = 0
        self.failed = 0
        self.status_bar_length = 0
        self._dbg(2, 'Queue reset.')
        self._del_status_bar()

    def _run(self, plugin, devices, callback, queue_function, *args):
        self.total += len(devices)
        callback = _prepare_plugin(callback)
        self.task = Task(plugin.DESCRIPTION, self.workqueue)
        for device in devices:
            if device in self.failed_devices:
                continue
            data = {
                'device': device
            }
            job_id = queue_function(callback, device.name, *args, data=data)
            if job_id is not None:
                self.task.add_job_id(job_id)

        if self.task.is_completed():
            self._dbg(2, 'No jobs enqueued.')

    def run(self, attempts=1):
        """
        Add the given function to a queue, and call it once for each host
        according to the threading options.
        Use decorators.bind() if you also want to pass additional
        arguments to the callback function.

        Returns an object that represents the queued task, and that may be
        passed to is_completed() to check the status.

        @type  hosts: string|list(string)|Host|list(Host)
        @param hosts: A hostname or Host object, or a list of them.
        @type  function: function
        @param function: The function to execute.
        @type  attempts: int
        @param attempts: The number of attempts on failure.
        @rtype:  object
        @return: An object representing the task.
        """
        # Enable logging.
        mode = self.options.overwrite_logs and 'w' or 'a'
        log_decorator = log_to_file(
            self.options.logdir, mode, self.options.delete_logs
        )

        pre_upgrade_decorator = pre_upgrade(self.options.preupgradeset)
        post_upgrade_decorator = post_upgrade(self.options.postupgradeset)
        upgrade_decorator = upgrade(self.options.upgradeset)
        cli_cmd_decorator = cli_cmd_file(self.options.cli_file)
        if hasattr(self.options,'repository_path'):
            repository_decorator = repository(self.options.repository_path)
    
        if hasattr(self.options,'pkg_file'):
            if isinstance(self.options.pkg_file, str):
                pkg_list = pkglist.get_pkgs(self.options.pkg_file)
            else:
                pkg_list = self.options.pkg_file
            pkg_file_decorator = pkg_file(pkg_list)

        turbo_boot_decorator = turbo_boot(self.options.turboboot)

        if hasattr(self.options,'issu'):
            issu_decorator = issu(self.options.issu)

        if hasattr(self.options,'best_effort_config'):
            best_effort_config_decorator = best_effort_config(self.options.best_effort_config)

        plugins_types = "ALL"
           
        if hasattr(self.options,'addset') and self.options.addset:
            plugins_types = "ADD"
        if self.options.pkg_state:
            plugins_types = "POLL"
        if self.options.commitset:
            plugins_types = "COMMIT"
        if self.options.preupgradeset:
            plugins_types = "PRE_UPGRADE"
        elif self.options.upgradeset:
            plugins_types = "UPGRADE"
        elif self.options.postupgradeset:
            plugins_types = "POST_UPGRADE"
        elif self.options.deactivateset:
            plugins_types = "DEACTIVATE"
        elif self.options.removeset:
            plugins_types = "REMOVE"
        elif self.options.pre_migrateset:
            plugins_types = "PRE_MIGRATE"
        elif self.options.migrate_system_set:
            plugins_types = "MIGRATE_SYSTEM"
        elif self.options.post_migrate_set:
            plugins_types = "POST_MIGRATE"
        elif self.options.all_for_migrate_set:
            plugins_types = "ALL_FOR_MIGRATE"

        for pno, plugin in enumerate(plugin_map[plugins_types], start=1):
            msg = "{} ({:0>2}) {} {}".format(
                HEADER, pno, plugin.DESCRIPTION, ENDC
            )
            #print("{0}{1:+<60}".format("+" * 20, msg))
            function = plugin._start

            function = log_decorator(function)
            function = pre_upgrade_decorator(function)
            function = upgrade_decorator(function)
            function = post_upgrade_decorator(function)
            function = cli_cmd_decorator(function)
            if hasattr(self.options,'repository_path'):
                function = repository_decorator(function)
            if hasattr(self.options,'pkg_file'):
                function = pkg_file_decorator(function)
            function = turbo_boot_decorator(function)
            if hasattr(self.options,'issu'):
                function = issu_decorator(function)
            if hasattr(self.options,'best_effort_config'):
                function = best_effort_config_decorator(function)

            self._run(
                plugin,
                self.devices,
                function,
                self.workqueue.enqueue,
                attempts
            )
            self.join()
            if self.failed == len(self.devices):
                break
            self.reset()

        # for device in self.devices:
        #    device.session_log.succeeded()
        #    device.stderr.succeeded()

        #self._dbg(2, 'All jobs enqueued.')

    def run_or_ignore(self, hosts, function, attempts=1):
        """
        Like run(), but only appends hosts that are not already in the
        queue.

        @type  hosts: string|list(string)|Host|list(Host)
        @param hosts: A hostname or Host object, or a list of them.
        @type  function: function
        @param function: The function to execute.
        @type  attempts: int
        @param attempts: The number of attempts on failure.
        @rtype:  object
        @return: A task object, or None if all hosts were duplicates.
        """
        return self._run(hosts,
                         function,
                         self.workqueue.enqueue_or_ignore,
                         attempts)

    def priority_run(self, hosts, function, attempts=1):
        """
        Like run(), but adds the task to the front of the queue.

        @type  hosts: string|list(string)|Host|list(Host)
        @param hosts: A hostname or Host object, or a list of them.
        @type  function: function
        @param function: The function to execute.
        @type  attempts: int
        @param attempts: The number of attempts on failure.
        @rtype:  object
        @return: An object representing the task.
        """
        return self._run(hosts,
                         function,
                         self.workqueue.priority_enqueue,
                         False,
                         attempts)

    def priority_run_or_raise(self, hosts, function, attempts=1):
        """
        Like priority_run(), but if a host is already in the queue, the
        existing host is moved to the top of the queue instead of enqueuing
        the new one.

        @type  hosts: string|list(string)|Host|list(Host)
        @param hosts: A hostname or Host object, or a list of them.
        @type  function: function
        @param function: The function to execute.
        @type  attempts: int
        @param attempts: The number of attempts on failure.
        @rtype:  object
        @return: A task object, or None if all hosts were duplicates.
        """
        return self._run(hosts,
                         function,
                         self.workqueue.priority_enqueue_or_raise,
                         False,
                         attempts)

    def force_run(self, hosts, function, attempts=1):
        """
        Like priority_run(), but starts the task immediately even if that
        max_threads is exceeded.

        @type  hosts: string|list(string)|Host|list(Host)
        @param hosts: A hostname or Host object, or a list of them.
        @type  function: function
        @param function: The function to execute.
        @type  attempts: int
        @param attempts: The number of attempts on failure.
        @rtype:  object
        @return: An object representing the task.
        """
        return self._run(hosts,
                         function,
                         self.workqueue.priority_enqueue,
                         True,
                         attempts)

    def enqueue(self, function, name=None, attempts=1):
        """
        Places the given function in the queue and calls it as soon
        as a thread is available. To pass additional arguments to the
        callback, use Python's functools.partial().

        @type  function: function
        @param function: The function to execute.
        @type  name: string
        @param name: A name for the task.
        @type  attempts: int
        @param attempts: The number of attempts on failure.
        @rtype:  object
        @return: An object representing the task.
        """
        self.total += 1
        task = Task(self.workqueue)
        job_id = self.workqueue.enqueue(function, name, attempts)
        if job_id is not None:
            task.add_job_id(job_id)
        self._dbg(2, 'Function enqueued.')
        return task
