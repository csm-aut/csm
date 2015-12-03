#!/usr/bin/env python

import condor
import sys

import logging

logging.basicConfig(
        format='%(asctime)-15s %(levelname)8s: %(message)s',
        level=logging.DEBUG)

 
class Host():
    def __init__(self, hostname, platform, urls):
        self.hostname = hostname
        self.platform = platform
        self.urls = urls
 
class Context():
    def __init__(self, host):
        self.host = host
 

test_devices = []

def test():


    test_devices.append(
        ['telnet://root:root@172.27.41.45:2034']
    )

    #test_devices.append(
    #    ['telnet://cisco:cisco@172.28.98.3']
    #)





    #23 test cases

    for no, urls in enumerate(test_devices, start=1):
        print("---------- Test no: {} ----------".format(no))
        print(urls)
        print("=====")
        host = Host('mercy', 'generic', urls)
        ctx = Context(host)

        conn = condor.make_connection_from_context(ctx)
        #conn.connect(sys.stderr)
        #conn.connect()
        #output = conn.send('sh install inactive summary')
        #print output
        #output = conn.send('sh install active summary')
        #print output
        #output = conn.send('sh install committed summary')
        #print output

        #output = conn.send('conf t', wait_for_string="RP/0/RSP0/CPU0:nv-cluster-escalation(config)#")
        #print output
        #output = conn.send('logging console debugging')
        #print output
        #output = conn.send('commit')
        #print output
        #output = conn.send('exit')
        #print output

        for i in range(1):
            print("\n========================== {} ==========================".format(i))
            print("CONNECTED: {}".format(conn.connect(sys.stderr)))
            #conn.connect()


            output = conn.send('clear configuration inconsistency', timeout=10)
            print("CLEAR CONFIGURATION INCONSTENCY:")
            print output
            if "terminal" in output:
                print("OUTPUT: '{}'".format(output))
                raise Exception

            output = conn.send('admin clear configuration inconsistency')
            print("ADMIN CLEAR CONFIGURATION INCONSTENCY:")
            print output
            if "terminal" in output:
                print("OUTPUT: '{}'".format(output))
                raise Exception

            #output = conn.send('admin')
            #print output
            #output = conn.send('show platform', wait_for_string="RP/0/RSP0/CPU0:nv-cluster-escalation(admin)#")
            #print output
            #output = conn.send('exit')
            #print output
            #output = conn.send('conf t')
            #print output
            #output = conn.send('exit')
            #print output
            conn.disconnect()



        #output = conn.send('configure', wait_for_string="(config)#")
        #print output
        #output = conn.send('router isis 1', wait_for_string="(config-isis)#")
        #print output
        #output = conn.send('commit', wait_for_string="(config-isis)#")
        #print output
        #output = conn.send('end')
        #print output



        #conn.disconnect()

        """
            with connections.ConnectionAgent(
                connections.Connection(
                    'host', urls)) as conn:
                try:
                    output = conn.send('sh install inactive summary')
                    print output
                    output = conn.send('sh install active summary')
                    print output
                    output = conn.send('sh install committed summary')
                    print output
                except CommandSyntaxError:
                    print 'unknown'
            """

if __name__ == "__main__":

    test()
