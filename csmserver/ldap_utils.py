# =============================================================================
# Copyright (c) 2016, Cisco Systems, Inc
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
from utils import is_empty
from csm_exceptions import CSMLDAPException


def ldap_auth(system_option, username, password):
    """
    Use LDAP server to authenticate the user.

    ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
    con = ldap.initialize("ldap://ds.cisco.com:389")
    con.start_tls_s()
    con.simple_bind_s(user, password)

    or

    ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
    con = ldap.initialize("ldaps://ds.cisco.com")
    con.simple_bind_s(user, password)

    """
    # First check if LDAP authentication has been enabled
    if not system_option.enable_ldap_auth:
        return False

    ldap_server_url = system_option.ldap_server_url
    if is_empty(ldap_server_url):
        raise CSMLDAPException("ldap_auth: The LDAP server URL is not specified.")

    if is_empty(username) or is_empty(password):
        raise CSMLDAPException("ldap_auth: The username or password is not specified.")

    try:
        import ldap
    except ImportError:
        raise CSMLDAPException("ldap_auth: Unable to import ldap")
 
    ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
    try:
        con = ldap.initialize(ldap_server_url)
        if 'cisco' in ldap_server_url and is_empty(system_option.ldap_server_distinguished_names):
            username = '{}@cisco.com'.format(username)

        if not is_empty(system_option.ldap_server_distinguished_names):
            username = system_option.ldap_server_distinguished_names.format(username)

        con.bind_s(username, password)
        return True
    except ldap.INVALID_CREDENTIALS:
        raise CSMLDAPException("ldap_auth: The username or password is incorrect.")
    except ldap.LDAPError as e:
        if type(e.message) == dict and e.message.has_key('desc'):
            raise CSMLDAPException("ldap_auth: " + e.message['desc'])
        else: 
            raise CSMLDAPException("ldap_auth() hit exception")

    return False

