# =============================================================================
# fabfile.py
#
# Copyright (c)  2016, Cisco Systems
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

from fabric.api import *
from fabric.utils import warn
from fabric.api import run
from fabric.contrib.files import exists


remote_csm_dir = '/opt/csm'
remote_app_dir = '/opt/csm/csmserver'
github_repo = 'https://github.com/csm-aut/csm.git'
sql_pass = 'root'

def detect_os():
    if 'OS' in env:
        return env.OS
    output = run('python -c "import platform; print platform.dist()"')
    distname, version, osid = eval(output)
    puts("{} {} {} detected".format(distname, version, osid))
    env.OS = distname
    env.OS_VER = str(version)
    return

def _install_python27():
    output = run("python -V")
    if "2.7" in output:
        warn("Python 2.7 already installed")
        return

    with cd("/usr/src"):
        sudo("wget https://www.python.org/ftp/python/2.7.10/Python-2.7.10.tgz")
        sudo("tar xzf Python-2.7.10.tgz")
        with cd("/usr/src/Python-2.7.10"):
            sudo("./configure")
            sudo("make install")

def install_requirements():
    """ Install required Linux packages."""
    if env.OS == "centos":
        if env.OS_VER.startswith("6"):
            _install_python27()

        packages = "git python-setuptools python-devel python-crypto gcc python-virtualenv gunicorn"
        yum(packages)
        sudo("easy_install pip")

    elif env.OS in ["debian", "Ubuntu"]:
        packages = "git python-pip python-dev python-virtualenv gunicorn"
        apt_get(packages)

def apt_get(*packages):
    return sudo('apt-get -y --no-upgrade install %s' % ' '.join(packages), shell=False)

def yum(*packages):
    return sudo('yum -y install {}'.format(' '.join(packages)), shell=False)


def install_mysql():
    """ Install mysql server """

    with settings(hide('warnings', 'stderr'), warn_only=True):

        if env.OS == "centos":
                if env.OS_VER.startswith("7"):
                    result = sudo("rpm -q mysql-community-release-el7-5.noarch")
                elif env.OS_VER.startswith("6"):
                    result = sudo("rpm -q mysql-server-5.1.73-5.el6_6.x86_64")
                    #result = yum(["mysql-server"])
        elif env.OS in ["debian", "Ubuntu"]:
            with settings(hide('warnings', 'stderr'), warn_only=True):
                result = sudo('mysql --version')

    if result.failed is False:
        warn('MySQL is already installed')
        return

    mysql_password = sql_pass if sql_pass else prompt('Please enter MySQL root password:')

    if env.OS == "centos":
        if env.OS_VER.startswith("7"):
            sudo("rpm -Uvh http://dev.mysql.com/get/mysql-community-release-el7-5.noarch.rpm")
        sudo("yum -y update")
        result = yum("mysql-server")
        sudo("/sbin/service mysqld start")
        queries = [
            "DELETE FROM mysql.user WHERE User='';",
            "DELETE FROM mysql.user WHERE User='root' "
            "AND Host NOT IN ('localhost', '127.0.0.1', '::1');",
            "FLUSH PRIVILEGES;",
            "ALTER USER 'root'@'localhost' IDENTIFIED BY '{}';".format(mysql_password),
            "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('{}');".format(mysql_password),
            ]

        with warn_only():
            for query in queries:
                run('mysql -u root -e "%s"' % query)

        sudo('chkconfig mysqld on')

    elif env.OS in ["debian", "Ubuntu"]:
        sudo('echo "mysql-server-5.0 mysql-server/root_password password ' \
                                  '%s" | debconf-set-selections' % mysql_password)
        sudo('echo "mysql-server-5.0 mysql-server/root_password_again password ' \
                                  '%s" | debconf-set-selections' % mysql_password)
        apt_get('mysql-server')


def install_pip_requirements():
    """ Install required python modules """
    with cd(remote_app_dir):
        if not exists("env"):
            if env.OS == 'centos' and env.OS_VER.startswith("6"):
                sudo('pip install virtualenv')
                sudo('virtualenv --python=/usr/local/bin/python2.7 env')
            else:
                sudo('virtualenv env')
        with virtualenv():
            if hasattr(env, "proxy"):
                cmd = "pip install --proxy {} -r requirements.txt".format(env.proxy)
            else:
                cmd = "pip install -r requirements.txt"
            sudo(cmd)

def install_csm():
    """ Install CSM Server from github. Clone or pull if already exists. """
    if hasattr(env, "proxy"):
        print("Proxy")
        sudo('git config --global --add http.proxy {}'.format(env.proxy))

    if exists(remote_app_dir) is False:
        sudo('git clone {} {}'.format(github_repo, remote_csm_dir))
    else:
        with cd(remote_csm_dir):
            try:
                sudo('git pull')
            except:
                pass

def virtualenv():
    """
    Context manager. Use it for perform actions with virtualenv activated::

        with virtualenv():
            # virtualenv is active here

    """
    return prefix('source {}/env/bin/activate'.format(remote_app_dir))


def vagrant():
    """ Setup the environment for vagrant. """
    # change from the default user to 'vagrant'
    env.user = 'vagrant'
    # connect to the port-forwarded ssh
    env.hosts = ['127.0.0.1:2222']
    # use vagrant ssh key
    result = local('vagrant ssh-config | grep IdentityFile', capture=True)
    env.key_filename = result.split()[1]
    # env.proxy = "https://proxy-ams-1.cisco.com:8080"

def install():
    """ Install CSM Server """
    detect_os()
    install_requirements()
    install_mysql()
    install_csm()
    install_pip_requirements()
    start()
    local("open http://localhost:5000")


def deploy():
    """ Deploy changes and restart CSM Server """
    commit_message = prompt("Commit message?")
    local('git commit -am "{0}"'.format(commit_message))
    local('git push origin master')
    stop()
    install_csm()
    start()

def restart():
    """ Start CSM Server """
    with cd(remote_app_dir):
        with virtualenv():
            sudo('./csmserver restart')


def start():
    """ Start CSM Server """
    with cd(remote_app_dir):
        with virtualenv():
            result = sudo('./csmserver start', pty=False)



    #sudo('supervisorctl restart all')
def stop():
    """ Stop CSM Server """
    with cd(remote_app_dir):
        with virtualenv():
            sudo('./csmserver stop', pty=False)


def uname():
    """ Run uname on server """
    run('uname -a')
