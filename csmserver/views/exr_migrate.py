from flask import Blueprint
from flask import jsonify, render_template, redirect, url_for

exr_migrate = Blueprint('exr_migrate', __name__, url_prefix='/exr_migrate')

@exr_migrate.route('/schedule_migrate')
def schedule_migrate(): 
    return render_template('exr_migrate/schedule_migrate.html')
