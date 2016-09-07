# CSM Server

CSM Server is an automation and orchestration framework for IOS-XR devices.  It provides the ability to simultaneouly deploy IOS-XR software or SMUs across multiple routers in a scheduled manner through a simple point and click Web interface.  It provides the automation to relieve customers of having to perform tedious and maual install steps themselves.

# Getting the Latest Code


Click the <a href="https://github.com/csm-aut/csm/releases">releases</a> link and select the latest release and download the source code zip file.
The file is called csm-x.x.zip where x.x is the release number.

# New Installation

For new installation, consult the Install Guide to install CSM Server.  The Install Guide, install_guide.pdf, can be found in the csm directory after you unzip the zip file.

# Upgrade to the Latest Code

This section assumes that CSM Server has been installed on /usr/local and you wanted to upgrade to the latest code.  Copy csm-x.x.zip to /usr/local and unzip its contents.

```shell
$ cd /usr/local
$ unzip csm-x.x.zip
```

## Shutdown CSM Server

```shell
$ cd /usr/local/csm/csmserver
$ sudo ./csmserver stop
```

## Install New Python Modules

If you are using a virtual environment, make sure you are inside the virtual environment before proceeding. 

The following modules need to be installed for CSM Server built prior to 12/23/2015.

```shell
$ sudo pip install csmpe==0.1.3
$ sudo pip install xlutils==1.7.1
```

## Edit the Launch Script and database.ini

If you have previously made modifications to csmserver launch script (e.g., use a different python interpreter) or database.ini (e.g., use different username and password to connect to the database), you will need to make the same changes here.

```shell
$ sudo vi /usr/local/csm/csmserver/csmserver
$ sudo vi /usr/local/csm/csmserver/database.ini
```

## Switch to the Latest Code

Rename the current CSM Server directory to csm_old and the csm-x.x to csm.  

```shell
$ cd /usr/local
$ mv csm csm_old              
$ mv csm-x.x csm
```

### Restart CSM Server

```shell
$ cd /usr/local/csm/csmserver
$ sudo ./csmserver start
```

### Restart CSM Server - Inside a virtual environment

Follow these steps only if you are running CSM Server inside a virtual environment.  Copy the virtual environment directory (e.g. env) that contains python interpreter and library modules from the old application directory to the new application directory.

```shell
$ cd /usr/local/csm/csmserver
$ cp –R /usr/local/csm_old/csmserver/env .
$ source env/bin/activate
$ sudo ./csmserver start
```
