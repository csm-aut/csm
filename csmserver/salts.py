# =============================================================================
# Copyright (c) 2015, Cisco Systems, Inc
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
ENCRYPT = 0
DECRYPT = 1

def get_int(data, base):
    #based on a key, generate an int in the range [0, base-1]
    sum = 0
    for index in range(len(data)):
        sum += ord(data[index])
        
    return sum % base

def transform(c, from_str, to_str):   
    for index in range(len(from_str)):
        if c == to_str[index]:
            return from_str[index]        
    return c

def shuffling(encrypt, input, operation):
    output = ''
    string1 = encrypt['string1']
    string2 = encrypt['string2']
    
    shifted_by = get_int(encrypt['key'] + str(len(input)), len(string1)); 
    to_str = string2[shifted_by:] + string2[:shifted_by]

    for index in range(len(input)):
        if operation == ENCRYPT:
            ch = transform(input[index], to_str, string1)    
        else:
            ch = transform(input[index], string1, to_str)   
        output += ch

    return output

def encode(encrypt, password):
    return None if password is None else shuffling(encrypt, password, ENCRYPT)

def decode(encrypt, password):
    return None if password is None else shuffling(encrypt, password, DECRYPT)

import base64

if __name__ == '__main__': 
    print('encode', base64.b64encode('test'.encode('utf-8')))
    print('decode', bytes.decode(base64.b64decode('dGVzdA==')))