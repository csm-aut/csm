# =============================================================================
# Copyright (c)  2015, Cisco Systems, Inc
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
from models import logger
import requests
import json
 
CLIENT_ID = "bt58rttvtqj7f85qqbk752mt"
CLIENT_SECRET = "yHgCNwx2NaXuhqyB73cJ6mcK"
HTTP_METADATA_URL = "https://api.cisco.com/software/v2.0/metadata/"
HTTP_DOWNLOAD_URL = "https://api.cisco.com/software/v2.0/downloads/urls/"
HTTP_EULA_URL = "https://api.cisco.com/software/v2.0/compliance/forms/eula"
HTTP_K9_URL = "https://api.cisco.com/software/v2.0/compliance/forms/k9"
HTTP_ACCESS_TOKEN_URL = "https://cloudsso.cisco.com/as/token.oauth2"
HTTP_SN2INFO_URL = "https://api.cisco.com/product/v1.0/coverage/status/serial_numbers/"
HTTP_DOWNLOAD_STATISTICS_URL = "https://api.cisco.com/software/841/downloads/statistics"

BSD_ACCESS_TOKEN = "access_token"
BSD_EXCEPTION_MESSAGE = "exception_message" 
BSD_METADATA_TRANS_ID = "metadata_trans_id"
BSD_IMAGE_DETAILS = "image_details"
BSD_IMAGE_NAME = "image_name"
BSD_IMAGE_GUID = "image_guid"
BSD_IMAGE_SIZE = "image_size"
BSD_DOWNLOAD_SESSION_ID = "download_session_id"
BSD_DOWNLOAD_URL = "download_url"
BSD_EULA_FORM = "eula_form_details"
BSD_K9_FORM = "k9_form_details_response"
BSD_FIELD_DETAILS = "field_details"
BSD_FIELD_ID = "field_id"
BSD_FIELD_VALUE = "field_value"
    
class BSDServiceHandler(object):
    def __init__(self, username, password, MDF_ID, software_type_ID, PID, image_name):
        self.username = username
        self.password = password
        self.image_name = image_name
        self.PID = PID
        self.MDF_ID = MDF_ID
        self.software_type_ID = software_type_ID
    
    @classmethod
    def get_sn_2_info(cls, access_token, serial_numbers):
        print('ACCESS TOKEN', access_token)
        url_string = HTTP_SN2INFO_URL + serial_numbers
        print('URL', url_string)
        headers = {'Authorization': 'Bearer ' + access_token}
        return requests.get(url_string, headers=headers)
    
    @classmethod
    def get_access_token(cls, username, password):
        payload = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'username' : username, 'password' : password, 'grant_type' : 'password' }
        response = requests.post(HTTP_ACCESS_TOKEN_URL, params=payload)
        return json.loads(response.text)[BSD_ACCESS_TOKEN]

    def debug_print(self, heading, data):
        print(heading, data)
        
    def download(self, output_file_path, callback=None):
        access_token = self.get_access_token(self.username, self.password)
         
        UDI = "PID: " + self.PID + " VID: V01 SN: FOX1316G5R5"        
        response = self.send_meta_data_request(access_token, UDI)
        if response is not None:
            self.debug_print('response', response.text) 
            
            json_text = response.json() 
            metadata_trans_ID = self.get_json_value(json_text, BSD_METADATA_TRANS_ID)          
            image_GUID = self.get_json_value(json_text, BSD_IMAGE_GUID)
            image_size = self.get_json_value(json_text, BSD_IMAGE_SIZE)
            exception_message = self.get_json_value(json_text, BSD_EXCEPTION_MESSAGE)
            
            if exception_message is None:          
                if metadata_trans_ID is not None and image_GUID is not None:
                    response = self.send_download_request(access_token, UDI, self.MDF_ID, metadata_trans_ID, image_GUID)
                    if response is not None:
                        self.debug_print('response', response.text)
                        
                        json_text = response.json() 
                        download_url = self.get_json_value(json_text, BSD_DOWNLOAD_URL) 
                        download_session_ID = self.get_json_value(json_text, BSD_DOWNLOAD_SESSION_ID) 
                        
                        # When download_url is null, it may be that the user needs to
                        # acknowledge the EULA or K9 agreement.
                        if download_url is None:
                            eula = self.get_json_value(json_text, BSD_EULA_FORM)
                            k9 = self.get_json_value(json_text, BSD_K9_FORM)
                            if eula is not None:
                                response = self.send_EULA_request(access_token, download_session_ID);
                                self.debug_print('EULA response', response.text)
                            elif k9 is not None:
                                response = self.send_K9_request(access_token, download_session_ID);
                                self.debug_print('K9 response', response.text)
                                
                            response = self.send_download_request(access_token, UDI, self.MDF_ID, metadata_trans_ID, image_GUID)
                            if response is not None:
                                self.debug_print('After accepting EULA or K9', response.text)
                                
                                json_text = response.json() 
                                download_url = self.get_json_value(json_text, BSD_DOWNLOAD_URL) 
                                download_session_ID = self.get_json_value(json_text, BSD_DOWNLOAD_SESSION_ID) 
                        
                        self.debug_print('download_url', download_url)
                        self.debug_print('download_session', download_session_ID) 
                         
                        if download_url is not None and download_session_ID is not None:
                            self.send_get_image(access_token, download_url, output_file_path, self.image_name, image_size, callback)
                        else:                      
                            message = 'User "' + self.username + '" may not have software download privilege on cisco.com.'       
                            raise Exception(message)
                            
            else:
                logger.error('bsd_service hit exception %s', exception_message)
                raise Exception(exception_message)
    
    def send_EULA_request(self, access_token, download_session_ID):
        headers = {'Authorization': 'Bearer ' + access_token}
        return requests.post(HTTP_EULA_URL + "?download_session_id=" + download_session_ID +
            "&user_action=Accepted", headers=headers)
        
    def send_K9_request(self, access_token, download_session_ID):
        headers = {'Authorization': 'Bearer ' + access_token}
        return requests.post(HTTP_K9_URL + "?download_session_id=" + download_session_ID + 
            "&user_action=Accepted", headers=headers)
        
    def send_download_statistics(self, access_token, download_session_ID, image_guid, image_size):
        headers = {'Authorization': 'Bearer ' + access_token}
        return requests.post(HTTP_DOWNLOAD_STATISTICS_URL + 
            "?download_session_id=" + download_session_ID + 
            "&image_guid=" + image_guid + 
            "&download_status=Success" + 
            "&download_file_size=" + image_size, headers=headers)
          
    def send_get_image(self, access_token, url_string, output_file_path, image_name, image_size, callback=None):
        # Segment is 1 MB.  For 40 MB files, there will be about 40 updates (i.e. database writes)
        chunk_list= get_chunks((int)(image_size), (int)(image_size) / 1048576)
   
        headers = {'Authorization': 'Bearer ' + access_token}
        r = requests.get(url_string, headers=headers, stream=True)
        
        total_byte_count = 0
        with open(output_file_path, 'wb') as fd:
            for chunk in r.iter_content(8192):
                fd.write(chunk)
                total_byte_count += 8192
                if len(chunk_list) > 0 and total_byte_count > chunk_list[0]:    
                    if callback is not None:
                        callback('Downloading ' + str(total_byte_count) + ' of ' + image_size + ' bytes.')
                    # Pop the first entry out
                    del chunk_list[0]

            # Create a file which contains the size of the image file.
            size_file = open(output_file_path + '.size', 'w')
            size_file.write(image_size)
            size_file.close()       
        
    def send_meta_data_request(self, access_token, UDI):
        url_string = HTTP_METADATA_URL + \
            "udi/" + UDI + "/" + \
            "mdf_id/" + self.MDF_ID + "/" + \
            "software_type_id/" + self.software_type_ID + "/" + \
            "image_names/" + self.image_name

        headers = {'Authorization': 'Bearer ' + access_token}
        return requests.get(url_string, headers=headers)
    
    def send_download_request(self, access_token, UDI, MDF_ID, metadata_trans_ID, image_GUID):
        url_string = HTTP_DOWNLOAD_URL + \
            "udi/" + UDI + "/" + \
            "mdf_id/" + MDF_ID + "/" + \
            "metadata_trans_id/" + metadata_trans_ID + "/" + \
            "image_guids/" + image_GUID;
            
        headers = {'Authorization': 'Bearer ' + access_token}
        return requests.get(url_string, headers=headers)

    def get_json_value(self, json_object, key):
        if isinstance(json_object, dict):
            for k, v in json_object.items():
                if k == key:
                    return v
                value = self.get_json_value(v, key)
                if value is not None:
                    return value
        elif isinstance(json_object, list):
            for v in json_object:
                value = self.get_json_value(v, key)
                if value is not None:
                    return value
        else:
            return None

def get_chunks(image_size, segments):
    chunk_list = []
    if segments == 0:
        chunk_list.append(image_size)
    else:
        chunk = (int)(image_size / segments)   
        for i in range((int)(segments)):
            chunk_list.append(chunk * (i + 1))
    
    return chunk_list

                   
if __name__ == '__main__':  
    print(BSDServiceHandler.get_sn_2_info(BSDServiceHandler.get_access_token("alextang", "xx"), "FOX1316G5R5"))
    
