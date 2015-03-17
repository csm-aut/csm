# CSM Server

CSM Server is an automation and orchestration framework for IOS-XR devices.  It provides the ability to simultaneouly deploy IOS-XR software or SMUs across multiple routers in a scheduled manner through a simple point and click Web interface.  It leverages the Accelerated Upgrade Tool (AUT) to automate and relieve customers of having to perform tedious and maual install steps themselves.

# Getting the Latest Code

Click the Download ZIP button on the right to download csm-master.zip.  

# For a New Installation

Consult the Installation Guide to install CSM Server.

# For Upgrading to Latest Code

This section assumes you have already installed CSM Server and wanted to get the latest code.  CSM Server should have  been installed on /usr/local/csm.  Copy csm-master.zip to /usr/local and unzip its contents.

```shell
$ cd /usr/local
$ unzip csm-master.zip
```

## Shut Down Existing CSM Server

```shell
$ cd /usr/local/csm/csmserver
$ ./csmserver stop
```

## Copy the Data Directories

```shell
$ cd /usr/local/csm/csmserver
$ ./csmserver stop
```

