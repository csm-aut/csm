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
    return shuffling(encrypt, password, ENCRYPT)

def decode(encrypt, password):
    return shuffling(encrypt, password, DECRYPT)

import base64

if __name__ == '__main__': 
    print('encode', base64.b64encode('test'.encode('utf-8')))
    print('decode', bytes.decode(base64.b64decode('dGVzdA==')))