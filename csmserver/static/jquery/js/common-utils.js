
/*
Trim all spaces from lines
*/
function trim_lines(lines) {
  var result = '';
  var temp = lines.split("\n");
  for (var i = 0; i < temp.length; i++) {
    var line = temp[i].replace(/ /g,'');
    if (line.length > 0) {
      if (i == temp.length -1) {
        result += line;
      } else {
        result += line + "\n";
      }
    }  
  }
  return result;
}

function packages_contains_tar_file(selected_packages) {
  if (selected_packages.indexOf('.tar') == -1) {
    return false
  }
  return true
}
  
function beautify_platform(platform) {
  return platform.toUpperCase().replace('_','-');
}

function get_parent_folder(directory) {
  if (directory != null) {
    var pos = directory.lastIndexOf('/');
    if (pos == -1) {
      return '';
    } else {
      return directory.substring(0, pos);
    }
  }
  return '';
}

/*
 The validate_object should be initialized as below in order to use this function.
        
 var validate_object = {
   form: current_form,
   hostname: hostname,
   server_id: $('#server').val(),
   server_directory: $('#hidden_server_directory').val(),
   software_packages: $('#software-packages').val(),
   spinner: submit_spinner,
   check_missing_file_on_server: $('#install_action').val() == 'Install Add',
   callback: on_finish_validate
 };
*/
function on_validate_prerequisites_and_files_on_server(validate_object) {      
  check_missing_prerequisite(validate_object);     
}
      
function check_missing_prerequisite(validate_object) {               
  validate_object.spinner.show();
        
  $.ajax({
     url: "/api/get_missing_prerequisite_list",
     dataType: 'json',
     data: { smu_list: trim_lines(validate_object.software_packages) , hostname: validate_object.hostname },
     success: function (data) { 
       var missing_prerequisite_list = '';
       $.each(data, function(index, element) {
         for (i = 0; i < element.length; i++) {
           missing_prerequisite_list += element[i].smu_entry + '<br>';          
         }
       });

       // There is no missing pre-requisites
       if (missing_prerequisite_list.length == 0) {
         if (validate_object.check_missing_file_on_server && validate_object.server_id > -1) {
           check_missing_files_on_server(validate_object);               
         } else {
           validate_object.callback(validate_object);
         }
       } else {
         display_missing_prerequisite_dialog(validate_object, missing_prerequisite_list);
       }        
     },
     error: function(XMLHttpRequest, textStatus, errorThrown) { 
       validate_object.spinner.hide();
     }   
   }); 
 }
      
function display_missing_prerequisite_dialog(validate_object, missing_prerequisite_list) {
     
  bootbox.dialog({
    message: missing_prerequisite_list,
    title: "Following pre-requisite(s) were not selected, but should be included.",
    buttons: {
      primary: {
        label: "Include Pre-requisites",
        className: "btn-primary",
        callback: function() {
          // Add the missing pre-requisites
          validate_object.software_packages = 
            trim_lines( validate_object.software_packages + '\n' + missing_prerequisite_list.replace(/<br>/g, "\n") )

          if (validate_object.check_missing_file_on_server && validate_object.server_id > -1) {
            check_missing_files_on_server(validate_object);
          } else {
            validate_object.callback(validate_object);
          }
        }
      }, 
      success: {
        label: "Ignore",
        className: "btn-success",
        callback: function() {
          if (validate_object.check_missing_file_on_server && validate_object.server_id > -1) {
            check_missing_files_on_server(validate_object);
          } else {
            validate_object.callback(validate_object);
          }
          validate_object.spinner.hide();
        }
      },
      main: {
        label: "Cancel",
        className: "btn-default",
        callback: function() {
          validate_object.spinner.hide();
        }
      }
    }       
  });

}
      
function check_missing_files_on_server(validate_object) {
  validate_object.spinner.show();
     
  $.ajax({
     url: "/api/get_missing_files_on_server/" + validate_object.server_id,
     dataType: 'json',
     data: { smu_list: trim_lines(validate_object.software_packages), server_directory:validate_object.server_directory },
     success: function (response) { 
       if (response.status == 'Failed') {
         display_server_unreachable_dialog(validate_object);
       } else {        
         var missing_file_count = 0;
         var missing_file_list = '';
         var downloadable_file_list = '';
           
         $.each(response, function(index, element) {
           missing_file_count = element.length;
           for (i = 0; i < element.length; i++) {               
             if (element[i].is_downloadable) {
               missing_file_list += element[i].smu_entry + ' (needs ' + element[i].cco_filename + ')<br>';
               downloadable_file_list += element[i].cco_filename + '\n';
             } else {
               missing_file_list += element[i].smu_entry + ' (Unfortunately, it is not on cisco.com)<br>';
             }          
           }
         });

         // There is no missing files, go ahead and submit
         if (missing_file_count  == 0) {
           validate_object.callback(validate_object);
           // Scheduled Install will not reach the message below as the above function will cause a form submission.
           // This message is intended for the Platforms menu since there is no form submission.
           if (validate_object.form == null) {
             bootbox.alert("Requested file(s) already on the selected server repository.  No download is needed.");
           }
         } else {
           display_missing_files_dialog(validate_object, missing_file_list, downloadable_file_list);
         }
       }
     },
     error: function(XMLHttpRequest, textStatus, errorThrown) { 
       validate_object.spinner.hide();
     }
   });   
}
  
function display_missing_files_dialog(validate_object, missing_file_list, downloadable_file_list) {
  bootbox.dialog({
    message: missing_file_list,
    title: "Following files are missing on the server repository.  If you choose to download them, " + 
        "the scheduled installation will not proceed until the files are successfully downloaded and copied to the server repository.",
    buttons: {
      primary: {
        label: "Download",
        className: "btn-primary",
        callback: function() { 
          validate_object.pending_downloads = downloadable_file_list
          check_cisco_authentication(validate_object)
        }
      }, 
      success: {
        label: "Ignore",
        className: "btn-success",
        callback: function() {
          validate_object.spinner.hide();
          validate_object.callback(validate_object);
        }
      },
      main: {
        label: "Cancel",
        className: "btn-default",
        callback: function() {
          validate_object.spinner.hide();
        }
      }
    }
  });
 }
  
function check_cisco_authentication(validate_object) { 
  $.ajax({
    url: "/api/check_cisco_authentication/",
    type: "POST",
    dataType: 'json',
    success: function (response) { 
      if (response.status == 'OK') {
        validate_object.callback(validate_object);
      } else {
        bootbox.alert("Cisco user authentication information has not been entered.  Go to Tools - User Preferences.");
        validate_object.spinner.hide();
      }
    },
    error: function(XMLHttpRequest, textStatus, errorThrown) { 
      validate_object.spinner.hide();
    }
  });  
}
  
function display_server_unreachable_dialog(validate_object) {
  bootbox.dialog({
    message: "CSM Server is unable to verify the existence of the software packages on the server repository.   " +
        "Either there is a network intermittent issue or the server repository is not reachable.  " +
        "If it is a network issue, click Cancel, then Schedule to retry the verification or click Continue to schedule the installation without verification.",
    title: "Server repository is not reachable", 
    buttons: {
      primary: {
        label: "Continue",
        className: "btn-primary",
        callback: function() {
          validate_object.spinner.hide(); 
          validate_object.callback(validate_object);
        }
      },
      main: {
        label: "Cancel",
        className: "btn-default",
        callback: function() {
          validate_object.spinner.hide();
        }
      }
    }
  });
}