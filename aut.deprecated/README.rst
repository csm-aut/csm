
1) What are Pre-requisites for running script?
   a) you need python version 2.7.4 or higher (not 3.xxx)


2) How to install Accelerated Upgrade ?
   python install -d <directory where AU is to be installed>
   e.g. python install -d /users/MyuserName/AUtool 

3) How to run Accelerated Upgrade ?
====================================
CLI : 
/<path where AU is installed>/accelerated_upgrade -r <repository where packages are kept > -f pkglist.txt --urls devices.txt --verbose  5

   Note :(1) pkglist.txt => is text file containing package names to be installed
             sample icontent is :
              cat pkglist.txt 
              #Comment the package which you don’t want with “#"
              #asr9k-mini-px.vm-4.3.2
              asr9k-px-4.3.2.sp2.pie
              asr9k-mpls-px.pie-4.3.2
              asr9k-mgbl-px.pie-4.3.2
              asr9k-mcast-px.pie-4.3.2
              asr9k-mini-px.pie-4.3.2
         (2) devices.txt => is text file containing device urls where the package should 
             be installed , sample content is :
               cat devices.txt 
               telnet://root:root@10.64.67.90:2043
               #telnet://lab:lab@10.76.239.15:2031
               #telnet://root:root123@10.64.67.90:2045
               #telnet://root:root@10.64.67.90:2045

             Syntax of URL is : protocol://username:password@devices_address
             protocol could be telnet or ssh. 


4) How to run pre upgrade steps only 
=====================================
    Use the option : --pre-upgrade

5) How to run upgrade steps only 
=====================================
    Use the option : --upgrade

6) How to run post upgrade steps only 
=====================================
    Use the option : --post-upgrade
