/**
 * This file requires a corresponding templates/share/server_software_dialog.html.
 * The following js files must be included by the caller.
 *
 * <script type="text/javascript" src="/static/jquery/js/common-utils.js"></script>
 * <script src="/static/bootbox-4.2.0/js/bootbox.js"></script>
 * <script src="/static/duallistbox/dist/dual-list-box.js"></script>
 */
 
var server_software_hostname;
var server_software_dialog_spinner;
var server_software_selector;

var config_selector;

$(function() {

    server_software_dialog_spinner = $('#server-software-dialog-browse-spinner');
    server_software_dialog_spinner.hide();
    
    server_software_selector = $('#server-software-selector').DualListBox();

    config_selector = $('#config_filename');
    
    $('#server-dialog-auto-select-software').on('click', function(e) {
        // Cancel default behavior
        e.preventDefault(); 
        auto_select_software(server_software_hostname, server_software_selector, $('#server_dialog_target_software').val(), false);
    });
  
    $('#server_dialog_server').on('change', function(e) {
        server_id = $('#server_dialog_server').val();
        if (server_id == -1) {
            $('#server_dialog_server_directory').html('');
        } else {
            server_software_retrieve_file_list(server_id, $('#server_dialog_server_directory'), '')
        }
    });

    $('#server_dialog_server_directory').on('change', function(e) {
        server_software_retrieve_file_list(
            $('#server_dialog_server').val(), 
            $('#server_dialog_server_directory'), 
            $('#server_dialog_server_directory').val() );
    });
    
    
    // Move up one folder (i.e. parent folder)   
    $('#server-dialog-move-up').on('click', function(e) {
        server_software_retrieve_file_list(
            $('#server_dialog_server').val(), 
            $('#server_dialog_server_directory'), 
            get_parent_folder($('#server_dialog_server_directory').val()) );
    });
    
    $('#server-dialog-reset-server-directory').on('click', function(e) {
        reset_server_directory(
            $('#server_dialog_server').val(),
            $('#server_dialog_server_directory'), 
            $('#server_dialog_server_directory').val() );
    }); 

    function reset_server_directory(server_id, server_directory_selector, server_directory) {
        if (server_directory != '') {    
            bootbox.confirm('Reset the server directory to use the server repository base directory?', function(result) {
                if (result) {
                    server_software_retrieve_file_list(server_id, server_directory_selector, '')
                }
            });
        }
    }
 
 });
 
 function display_server_software_dialog(hostname_list, server_id, server_directory, target_software) {

     if (hostname_list.length == 1) {
         server_software_hostname = hostname_list[0];
         $('#server-dialog-auto-select-software-panel').show();
         $('#server-dialog-title').html('> Host: <span style="color: Gray;">' + server_software_hostname + '</span>');
     } else {
         $('#server-dialog-auto-select-software-panel').hide();
         $('#server-dialog-title').html('');
     }
     
     $('#server_dialog_target_software').val(target_software);
     $('#server-software-dialog').modal({ show: true, backdrop:'static' })  

     if (server_id && server_id != -1) {
        $('#server_dialog_server').val(server_id);
        server_software_retrieve_file_list(server_id, $('#server_dialog_server_directory'), server_directory);
    }
 }
 
function server_software_retrieve_file_list(server_id, server_directory_selector, server_directory) {
    server_directory_selector.html('');
    server_directory_selector.append('<option value="' + server_directory + '">' + server_directory + '</option>');

    server_software_dialog_spinner.show();

    $.ajax({
        url: "/api/get_server_file_dict/" + server_id,
        dataType: 'json',
        data: {
          server_directory: server_directory
        },
        success: function(response) {
            if (response.status == 'Failed') {
                bootbox.alert("Either the server repository is not reachable or server directory does not exist.");
            } else {
                $.each(response, function(index, element) {
                    server_software_populate_file_list(element, server_directory_selector, server_directory);
                });
            }

            server_software_dialog_spinner.hide();
        },
        error: function(XMLHttpRequest, textStatus, errorThrown) {
            bootbox.alert("Unable to list files. Server repository may not be visible by CSM Server.");
            server_software_dialog_spinner.hide();
        }
    });
}
    
function server_software_populate_file_list(element, server_directory_selector, server_directory) {
    var available_software = [];

    for (i = 0; i < element.length; i++) {
        var filename = element[i].filename;
        var is_directory = element[i].is_directory;

        if (is_directory == true) {
            server_directory_selector.append('<option value="' + filename + '">' + filename + '</option>');
        } else {
            available_software.push({
               'id': filename,
                'name': filename
            });
        }
    }
    server_software_selector.initialize(available_software, []);

    if (config_selector != null) {

        config_selector.html("");
        config_selector.append("<option value=\"\" disabled selected style=\"display: none;\">Optional</option>");
        config_selector.append("<option value=\"\"></option>");
        $(available_software).each(function (i) { //populate child options
            config_selector.append("<option value=\""+available_software[i].id +"\">"+available_software[i].name + "</option>");
        });
    }

        // In edit mode.
    if ($('#hidden_edit') != null && $('#hidden_edit').val() == 'True' && $('#hidden_software_packages') != null) {
        var previously_selected_packages = $('#hidden_software_packages').val().split(',');
        //console.log("previously_selected_packages = " + String(previously_selected_packages));
        server_software_selector.select_exact_match(previously_selected_packages);
    }

    if ($('#hidden_edit') != null && $('#hidden_edit').val() == 'True' && $('#hidden_config_filename') != null) {
        $('#config_filename').val($('#hidden_config_filename').val());
        //console.log("config_filename = " + $('#config_filename').val());
    }
}
 