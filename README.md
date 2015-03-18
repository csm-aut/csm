# CSM Server

CSM Server is an automation and orchestration framework for IOS-XR devices.  It provides the ability to simultaneouly deploy IOS-XR software or SMUs across multiple routers in a scheduled manner through a simple point and click Web interface.  It leverages the Accelerated Upgrade Tool (AUT) to automate and relieve customers of having to perform tedious and maual install steps themselves.

# Getting the Latest Code

Click the Download ZIP button on the right to download csm-master.zip.  

# New Installation

Consult the Installation Guide to install CSM Server.

# Upgrading to the Latest Code

This section assumes that CSM Server has been installed on /usr/local/csm and you wanted to get the latest code.  Copy csm-master.zip to /usr/local and unzip its contents.

```shell
$ cd /usr/local
$ unzip csm-master.zip
```

## Edit csmserver launch script and database.ini

If previously, you have made modifications to csmserver launch script (e.g. use a different python interpreter) or database.ini (e.g. use different uesrname and password to connect to the database), you will need to make the same changes here.

```shell
$ vi /usr/local/csm-master/csmserver/csmserver
$ vi /usr/local/csm-master/csmserver/database.ini
```

## Use the Latest Code

Before you do that, be sure to shutdown CSM Server.

```shell
$ cd /usr/local
$ mv csm csm_old              
$ mv csm-master csm
```

