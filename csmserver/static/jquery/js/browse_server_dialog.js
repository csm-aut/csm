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
    if (file_list_table != null) {
      file_list_table.api().clear().draw();
    }
    return;
  }
               
  server_directory_selector.append('<option value="' + server_directory  +'">' + server_directory + '</option>');       
  browse_spinner.show();
  
  if (file_list_table != null) {
    file_list_table.api().clear().draw();
  }
 
  $.ajax({
    url: "/api/get_server_file_dict/" + server_id,
    dataType: 'json',
    data: { server_directory: server_directory} ,
    success: function (response) {          
      if (response.status == 'Failed') {
        if (file_list_table != null) {
          file_list_table.api().clear().draw();
        }
        bootbox.alert("Either the server repository is not reachable or server directory does not exist.");
      } else {
        $.each(response, function(index, element) {
          for (i = 0; i < element.length; i++) {          
            if (element[i].is_directory == true) {
              server_directory_selector.append('<option value="' + element[i].filename + '">' + element[i].filename + '</option>');
            } else {
              if (file_list_table != null) {
                file_list_table.api().row.add([element[i].filename]);
              }
            }
          }
        }); 
      }       
      browse_spinner.hide();
      
      if (file_list_table != null) {
        file_list_table.api().draw();
      }
      
    },
    error: function(XMLHttpRequest, textStatus, errorThrown) { 
      bootbox.alert("Unable to list files. Error=" + errorThrown);
      browse_spinner.hide();
    }  
  });      
}