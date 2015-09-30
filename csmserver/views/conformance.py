from flask import Blueprint
from flask import render_template, jsonify, abort, send_file
from flask.ext.login import login_required, current_user
from flask import request, redirect, url_for

from wtforms import Form
from wtforms import TextField
from wtforms import SelectField
from wtforms import TextAreaField
from wtforms import RadioField
from wtforms import HiddenField
from wtforms.validators import Length, required

from models import logger
from models import SoftwareProfile
from models import SystemOption
from models import ConformanceReport
from models import ConformanceReportEntry

from common import get_last_successful_inventory_elapsed_time
from common import get_host_active_packages 
from common import get_host_inactive_packages 
from common import fill_servers
from common import fill_regions 
from common import get_server_list
from common import get_host

from database import DBSession

from constants import JobStatus
from constants import get_temp_directory

from conformance_report import XLSWriter 
from filters import get_datetime_string

import re

conformance = Blueprint('conformance', __name__, url_prefix='/conformance')

@conformance.route('/')
def home(): 
    conformance_report_dialog_form = ConformanceReportDialogForm(request.form)
    export_conformance_report_form = ExportConformanceReportForm(request.form)
    export_conformance_report_form.include_host_packages.data = True
    
    fill_regions(conformance_report_dialog_form.region.choices)
    
    return render_template('conformance/index.html', form=conformance_report_dialog_form,             
        export_conformance_report_form=export_conformance_report_form)

@conformance.route('/software_profile/create' , methods=['GET','POST'])
@login_required
def software_profile_create():
    #if not can_create_user(current_user):
    #    abort(401)
    db_session = DBSession()  
    
    form = SoftwareProfileForm(request.form)
    server_dialog_form = ServerDialogForm(request.form)   
     
    fill_servers(server_dialog_form.server_dialog_server.choices, get_server_list(db_session), False)
    
    if request.method == 'POST' and form.validate():

        software_profile = get_software_profile(db_session, form.profile_name.data)

        if software_profile is not None:
            return render_template('conformance/profile_edit.html', 
                form=form, system_option=SystemOption.get(db_session), duplicate_error=True)
        
        software_profile = SoftwareProfile(
            name=form.profile_name.data,
            description=form.description.data,
            packages = get_comma_delimited_packages(form.software_packages.data),
            created_by=current_user.username)
        
        db_session.add(software_profile)
        db_session.commit()
            
        return redirect(url_for('conformance.home'))
    else:

        return render_template('conformance/profile_edit.html', 
            form=form, server_dialog_form=server_dialog_form, 
            system_option=SystemOption.get(db_session))

@conformance.route('/software_profile/<profile_name>/edit' , methods=['GET','POST'])
@login_required
def software_profile_edit(profile_name):
    db_session = DBSession()
    
    software_profile = get_software_profile(db_session, profile_name)
    if software_profile is None:
        abort(404)
        
    form = SoftwareProfileForm(request.form)
    server_dialog_form = ServerDialogForm(request.form)
    fill_servers(server_dialog_form.server_dialog_server.choices, get_server_list(db_session), False)
    
    if request.method == 'POST' and form.validate():
        if profile_name != form.profile_name.data and \
            get_software_profile(db_session, form.profile_name.data) is not None:
            return render_template('conformance/profile_edit.html', 
                form=form, system_option=SystemOption.get(db_session), duplicate_error=True)
        
        software_profile.name = form.profile_name.data       
        software_profile.description = form.description.data
        software_profile.packages = get_comma_delimited_packages(form.software_packages.data)

        db_session.commit()
        
        return redirect(url_for('conformance.home'))
    else:
        form.profile_name.data = software_profile.name
        form.description.data = software_profile.description
        if software_profile.packages is not None:
            form.software_packages.data = '\n'.join(software_profile.packages.split(','))
    
    return render_template('conformance/profile_edit.html',
        form=form, server_dialog_form=server_dialog_form, system_option=SystemOption.get(db_session))

def get_comma_delimited_packages(form_software_packages):
    comma_list = ''
    software_packages = form_software_packages.splitlines()
    for software_package in software_packages:
        comma_list += software_package + ','

    return comma_list.rstrip(',')
            
@conformance.route('/api/get_software_profiles')
@login_required
def api_get_software_profiles():
    rows = []
    db_session = DBSession()
    
    software_profiles = db_session.query(SoftwareProfile)
    for software_profile in software_profiles:
        row = {}
        row['id'] = software_profile.id
        row['profile_name'] = software_profile.name
        row['description'] = software_profile.description
        row['packages'] = software_profile.packages
        row['created_by'] = software_profile.created_by

        rows.append(row)
 
    return jsonify( **{'data':rows} )

@conformance.route('/software_profile/<profile_name>/delete', methods=['DELETE'])
@login_required
def software_profile_delete(profile_name):
    # if not can_delete(current_user):
    #    abort(401)
        
    db_session = DBSession()

    software_profile = get_software_profile(db_session, profile_name)
    if software_profile is None:
        abort(404)
    
    db_session.delete(software_profile)
    db_session.commit()
        
    return jsonify({'status':'OK'})

def get_conformance_report_by_id(db_session, id):
    return db_session.query(ConformanceReport).filter(ConformanceReport.id == id).first()
    
@conformance.route('/api/rerun_conformance_report/<int:id>')
@login_required
def api_rerun_conformance_report(id): 
    db_session = DBSession()
    
    conformance_report = get_conformance_report_by_id(db_session, id)
    if conformance_report is not None:
        return run_conformance_report(conformance_report.software_profile, 
            conformance_report.match_criteria, conformance_report.hostnames);
    else:
        jsonify({'status':'Unable to locate the conformance report with id = %d' % id})
    
    return jsonify({'status':'OK'})

@conformance.route('/api/run_conformance_report')
@login_required
def api_run_conformance_report():
    profile_name = request.args.get('software_profile_name')
    match_criteria = request.args.get('match_criteria')
    hostnames = request.args.get('selected_hosts')
    
    return run_conformance_report(profile_name, match_criteria, hostnames)

def run_conformance_report(profile_name, match_criteria, hostnames):
    host_not_in_conformance = 0
    host_out_dated_inventroy = 0
    
    db_session = DBSession()
    
    software_profile = get_software_profile(db_session, profile_name)
    if software_profile is not None:
        # software_profile_packages = 
        conformance_report = ConformanceReport(
            software_profile=software_profile.name,
            software_profile_packages=','.join(sorted(software_profile.packages.split(',')) ),
            match_criteria=match_criteria,
            hostnames=hostnames,
            user_id=current_user.id,
            created_by=current_user.username)
        
        for hostname in hostnames.split(','):
            host = get_host(db_session, hostname)
            if host:
                if host.software_platform is not None and host.software_version is not None:
                    platform_software = host.software_platform + ' ' + host.software_version
                else:
                    platform_software = 'Unknown'
                    
                inventory_job = host.inventory_job[0]
                if inventory_job is not None and inventory_job.last_successful_time is not None:
                    last_successful_retrieval = get_last_successful_inventory_elapsed_time(host)
                    inventory_status =  inventory_job.status
                else:
                    last_successful_retrieval = ''
                    inventory_status = ''
                    
                if inventory_status != JobStatus.COMPLETED:
                    host_out_dated_inventroy += 1
                                              
                host_packages = []        
                if match_criteria == 'inactive':
                    host_packages = get_host_inactive_packages(hostname)
                elif match_criteria == 'active':
                    host_packages = get_host_active_packages(hostname)
                
                missing_packages = get_missing_packages(hostname, host_packages, software_profile.packages.split(','), match_criteria)
                if missing_packages:
                    host_not_in_conformance += 1
                    
                conformance_report_entry = ConformanceReportEntry(
                    hostname=hostname,
                    platform_software=platform_software,
                    inventory_status=inventory_status,
                    last_successful_retrieval=last_successful_retrieval,
                    host_packages=','.join(sorted(host_packages)),
                    missing_packages=','.join(sorted(missing_packages)) )                    
            else:
                # Flag host not found condition
                host_out_dated_inventroy += 1 
                host_not_in_conformance += 1
                
                conformance_report_entry = ConformanceReportEntry(
                    hostname=hostname,
                    platform_software='MISSING',
                    inventory_status='MISSING',
                    last_successful_retrieval='MISSING',
                    host_packages='MISSING',
                    missing_packages='MISSING' ) 
                
            conformance_report.entries.append(conformance_report_entry)
            
        conformance_report.host_not_in_conformance = host_not_in_conformance
        conformance_report.host_out_dated_inventory = host_out_dated_inventroy
        
        db_session.add(conformance_report)
        db_session.commit()
    else:
        return jsonify({'status':'Unable to locate the software profile %s' % profile_name })
    
    purge_old_conformance_reports(db_session)
    
    return jsonify({'status':'OK'})

def purge_old_conformance_reports(db_session):
    conformance_reports = get_conformance_report_by_user(db_session, current_user.username)
    if len(conformance_reports) > 10:
        try:
            # delete the earliest conformance report.
            db_session.delete(conformance_reports[-1]) 
            db_session.commit()
        except Exception:
            logger.exception('purge_old_conformance_reports hit exception')
    
def get_missing_packages(hostname, host_packages, software_profile, match_criteria):
    conformance_result = []
    
    for package in software_profile:
        # Might require more stripping for other platforms.
        # Currently, this works for ASR9K and CRS
        match_package = package.replace('.pie','') 
        
        matched = False
        for host_package in host_packages:
            if re.search(match_package, host_package) is not None:
                matched = True
                break
            
        if not matched:
            conformance_result.append(package)
            
    return conformance_result

@conformance.route('/api/export_conformance_report/<int:id>')
@login_required
def api_export_conformance_report(id):
    locale_datetime = request.args.get('locale_datetime')
    include_host_packages = request.args.get('include_host_packages')
    db_session = DBSession()
   
    filename = get_temp_directory() + current_user.username + '_report.xls'
        
    conformance_report = get_conformance_report_by_id(db_session, id)
    if conformance_report is not None:
        xls_writer = XLSWriter(conformance_report, filename, 
            locale_datetime=locale_datetime, include_host_packages=bool(int(include_host_packages)))
        xls_writer.write_report()
    
    return send_file(filename, as_attachment=True)
   
    
@conformance.route('/api/get_conformance_report_summary/<int:id>')
@login_required
def api_get_conformance_report_summary(id):
    db_session = DBSession()
    conformance_report = get_conformance_report_by_id(db_session, id)
    if conformance_report is not None:
        return jsonify( **{'data': [ 
            {'host_not_in_conformance': conformance_report.host_not_in_conformance,
             'host_out_dated_inventory': conformance_report.host_out_dated_inventory }
            ] } )
    else:
        return jsonify({'status':'Failed'})

@conformance.route('/api/get_conformance_report_datetime/<int:id>')
@login_required
def api_get_conformance_report_datetime(id):
    conformance_report_datetime = None
    db_session = DBSession()
    
    conformance_report = get_conformance_report_by_id(db_session, id)
    if conformance_report is not None:
        conformance_report_datetime = get_datetime_string(conformance_report.created_time)

    return jsonify( **{'data': [ 
            {'conformance_report_datetime': conformance_report_datetime }
            ] } )
             
@conformance.route('/api/get_conformance_report/<int:id>')
@login_required
def api_get_conformance_report(id):
    rows = []
    db_session = DBSession()
    
    conformance_report = get_conformance_report_by_id(db_session, id)
    if conformance_report is not None:
        entries = conformance_report.entries;
        for entry in entries:
            row = {}
            row['hostname'] = entry.hostname
            row['platform_software'] = entry.platform_software
            row['last_successful_retrieval'] = entry.last_successful_retrieval
            row['inventory_status'] = entry.inventory_status
            row['missing_packages'] = entry.missing_packages
            
            rows.append(row)
    
    return jsonify( **{'data':rows} )


@conformance.route('/api/get_conformance_report_dates')
@login_required
def api_get_conformance_report_dates():
    rows = []
    db_session = DBSession()
    
    conformance_reports = get_conformance_report_by_user(db_session, current_user.username)
    if conformance_reports:
        for conformance_report in conformance_reports:
            row = {}
            row['id'] = conformance_report.id
            row['software_profile'] = conformance_report.software_profile
            row['created_time'] = conformance_report.created_time
            
            rows.append(row)
    
    return jsonify( **{'data':rows} )

"""
Returns the conformance report in descending order of creation date by user.
"""
def get_conformance_report_by_user(db_session, username):
    return db_session.query(ConformanceReport).filter(ConformanceReport.created_by == username).order_by(ConformanceReport.created_time.desc()).all()

@conformance.route('/api/get_software_profile_names')
@login_required
def api_get_software_profile_names():
    rows = []
    db_session = DBSession()
    
    software_profile_names = get_software_profile_names(db_session)
    if len(software_profile_names) > 0:
        for software_profile_name in software_profile_names:
            rows.append({ 'software_profile_name' : software_profile_name })
    
    return jsonify( **{'data':rows} )

def get_software_profile(db_session, profile_name):
    return db_session.query(SoftwareProfile).filter(SoftwareProfile.name == profile_name).first()

def get_software_profile_names(db_session):
    return db_session.query(SoftwareProfile.name).order_by(SoftwareProfile.name.asc()).all()

class ServerDialogForm(Form):
    server_dialog_target_software = TextField('Target Software Release')
    server_dialog_server = SelectField('Server Repository', coerce=int, choices = [(-1, '')]) 
    server_dialog_server_directory = SelectField('Server Directory', coerce=str, choices = [('', '')])
    
class SoftwareProfileForm(Form):
    profile_name = TextField('Profile Name', [required(), Length(max=30)])
    description = TextField('Description', [required(), Length(max=100)])
    software_packages = TextAreaField('Software Packages', [required()])
    
class ConformanceReportDialogForm(Form):
    conformance_reports = SelectField('Conformance Reports', coerce=int, choices = [(-1, '')]) 
    conformance_report_dialog_software_profile = SelectField('Software Profile', coerce=str, choices = [('', '')]) 
    match_criteria = RadioField('Match Criteria', 
        choices=[('inactive','Packages that have not been activated'),
                 ('active','Packages that are currently in active state')], default='active')
    region = SelectField('Region', coerce=int, choices = [(-1, '')]) 
    role = SelectField('Role', coerce=str, choices = [('Any', 'Any')]) 
    software = SelectField('Software Version', coerce=str, choices = [('Any', 'Any')]) 
    
class ExportConformanceReportForm(Form):
    include_host_packages = HiddenField("Include Host packages on the report")