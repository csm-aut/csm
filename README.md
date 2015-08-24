# CSM Server

CSM Server is an automation and orchestration framework for IOS-XR devices.  It provides the ability to simultaneouly deploy IOS-XR software or SMUs across multiple routers in a scheduled manner through a simple point and click Web interface.  It leverages the Accelerated Upgrade Tool (AUT) to automate and relieve customers of having to perform tedious and maual install steps themselves.

# Getting the Latest Code

Click the releases link and select the latest release and download the Source code zip file.
The file is called csm-x.x.zip wehre x.x is the release number.

# New Installation

Consult the Installation Guide to install CSM Server.

# Upgrade to the Latest Code

This section assumes that CSM Server has been installed on /usr/local/csm and you wanted to upgrade to the latest code.  Copy csm-x.x.zip to /usr/local and unzip its contents.

```shell
$ cd /usr/local
$ unzip csm-x.x.zip
```

## Shut down CSM Server

```shell
$ cd /usr/local/csm/csmserver
$ ./csmserver stop
```

## Edit csmserver launch script and database.ini

If you have previously made modifications to csmserver launch script (e.g. use a different python interpreter) or database.ini (e.g. use different username and password to connect to the database), you will need to make the same changes here.

```shell
$ vi /usr/local/csm-master/csmserver/csmserver
$ vi /usr/local/csm-master/csmserver/database.ini
```

## Switch to the latest code

Rename the current CSM Server directory to csm_old and the csm-master to csm.  

```shell
$ cd /usr/local
$ mv csm csm_old              
$ mv csm-x.x csm
```

### Restart CSM Server

```shell
$ cd /usr/local/csm/csmserver
$ ./csmserver start
```

### Restart CSM Server - inside a virtual environment

Copy the virtual environment directory (e.g. env) which contains python interpreter and library modules, to the new application directory.

```shell
$ cd /usr/local/csm/csmserver
$ cp –R /usr/local/csm_old/csmserver/env .
$ source env/bin/activate
$ ./csmserver start
```
