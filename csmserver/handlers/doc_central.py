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
from sqlalchemy import and_

from models import SystemOption
from models import InstallJobHistory

from constants import InstallAction
from constants import get_log_directory
from constants import get_doc_central_directory

import os
import json
import requests
import datetime


def handle_doc_central_logging(ctx, logger):
    system_option = SystemOption.get(ctx.db_session)
    if system_option.doc_central_path:
        try:
            upload_to_doc_central = ctx.install_job.load_data('upload_to_doc_central')
            if upload_to_doc_central:
                if ctx.install_job.install_action == InstallAction.POST_UPGRADE:
                    aggregate_and_upload_log(ctx)
        except Exception:
            logger.exception('handle_doc_central_feature hit exception - hostname = %s, install job =  %s',
                             ctx.host.hostname if ctx.host is not None else 'Unknown', ctx.install_job.id)


def aggregate_and_upload_log(ctx):
    chain = get_dependency_chain(ctx.db_session, ctx.install_job)

    filename_template = "%s_%s_%s-to-%s-%s.txt"
    platform = ctx.host.software_platform
    hostname = ctx.host.hostname.replace(' ', '_')

    from_release = get_from_release(ctx.db_session, chain)
    to_release = ctx.host.software_version

    timestamp = datetime.datetime.strftime(datetime.datetime.now(), "%Y_%m_%d_%H_%M_%S")
    filename = filename_template % (platform, hostname, from_release, to_release, timestamp)

    # "<software_platform>-<CSM hostname>-<from release>- to - <to release>.<time stamp>.txt"
    output_file = os.path.join(get_doc_central_directory(), filename)

    with open(output_file, 'w') as outfile:
        for job_id in chain:
            install_job = ctx.db_session.query(InstallJobHistory).filter(InstallJobHistory.id == job_id).first()
            if install_job.install_action == InstallAction.POST_UPGRADE:
                install_job.save_data('doc_central_log_file_path', filename)
                ctx.db_session.commit()

            log_directory = os.path.join(get_log_directory(), install_job.session_log)
            job_logs = os.listdir(log_directory)
            for log in job_logs:
                if ('.txt' in log or '.log' in log) and log not in ['plugins.log', 'condoor.log'] and '.html' not in log:
                    with open(os.path.join(log_directory, log)) as f:
                        outfile.write('#' * 50 + "\n")
                        outfile.write("%s: %s \n" % (install_job.install_action, log))
                        outfile.write('#' * 50 + "\n")
                        outfile.write(f.read())
                        outfile.write("\n\n")


    #doc_central_url = "https://docs-services.cisco.com/docservices/upload"
    # url =  "https://docs-services-stg.cisco.com/docservices/upload"

    #preferences = Preferences.get(ctx.db_session, ctx.install_job.id)
    #username = preferences.cco_username
    #password = preferences.cco_password

    #headers = {'userid': username,
    #           'password': password
    #           }

    #system_option = SystemOption.get(ctx.db_session)
    #path = system_option.doc_central_path + '/' + to_release

    #metadata = {
    #    "fileName": output_file,
    #    "title": "CSM Log File",
    #    "description": "CSM Log File",
    #    "docType": "Cisco Engineering Document",
    #    "securityLevel": " ",
    #    "theatre": " ",
    #    "status": " ",
    #    "parent": path
    #}

    #doc_central_url = doc_central_url + "?metadata=" + json.dumps(metadata)

    #files = {'file': open(output_file, 'rb')}

    #resp = requests.post(doc_central_url, headers=headers, files=files)

    #print "Status Code:", resp.status_code
    #print "Headers:", resp.headers
    #print
    #print resp.content

    #return
    #return jsonify(**{ENVELOPE: {'dependency_chain': str(chain)}})


def get_dependency_chain(db_session, install_job):
    install_job_ids = db_session.query(InstallJobHistory.id).\
        filter(and_(InstallJobHistory.scheduled_time == install_job.scheduled_time,
                    InstallJobHistory.host_id == install_job.host_id)).all()

    # install_job_ids is a list of tuples (e.g. [(1283,), (1284,)])
    return [i[0] for i in install_job_ids]


def get_from_release(db_session, chain):
    """
    Expects to receive a list of ids, will check each for from_release in the data field.
    """
    for id in chain:
        install_job = db_session.query(InstallJobHistory).filter(InstallJobHistory.id == id).first()
        if install_job:
            from_release = install_job.load_data("from_release")
            if from_release:
                return from_release

    return 'unknown'
