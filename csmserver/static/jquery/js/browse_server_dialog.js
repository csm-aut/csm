function reset_server_directory(browse_spinner, server_id, server_directory_selector, server_directory, file_list_table) {
  if (server_directory == '') {
    return;
  }
        
  bootbox.confirm('Reset the server directory to use the server repository base directory?', function(result) {
    if (result) {
      retrieve_directory_and_file_list(browse_spinner, server_id, server_directory_selector, '', file_list_table)
    }
  });   
}
      
function retrieve_directory_and_file_list(browse_spinner, server_id, server_directory_selector, server_directory, file_list_table) { 
  server_directory_selector.html('');

  if (server_id == -1) {
    if (file_list_table.length) {        
      file_list_table.html('');
    }
    return;
  }
               
  server_directory_selector.append('<option value="' + server_directory  +'">' + server_directory + '</option>');       
  browse_spinner.show();

  $.ajax({
    url: "/api/get_server_file_dict/" + server_id,
    dataType: 'json',
    data: { server_directory: server_directory} ,
    success: function (response) {          
      if (response.status == 'Failed') {
        if (file_list_table.length) {        
          file_list_table.html('');
        }
        bootbox.alert("Either the server repository is not reachable or server directory does not exist.");
      } else {
        var html = '';
        $.each(response, function(index, element) {
          for (i = 0; i < element.length; i++) {          
            if (element[i].is_directory == true) {
              server_directory_selector.append('<option value="' + element[i].filename + '">' + element[i].filename + '</option>');
            } else {
              html += '<tr><td>' + element[i].filename + '</td></tr>';
            }
          }
        }); 
         
        if (file_list_table.length) { 
          file_list_table.html(html);
        }
      }       
      browse_spinner.hide();
    },
    error: function(XMLHttpRequest, textStatus, errorThrown) { 
      bootbox.alert("Unable to list files. Error=" + errorThrown);
      browse_spinner.hide();
    }  
  });      
}