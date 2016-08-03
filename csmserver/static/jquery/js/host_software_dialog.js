/**
 * This file requires a corresponding templates/share/host_software_dialog.html.
 * The following js files must be included by the caller.
 *
 * <script src="/static/duallistbox/dist/dual-list-box.js"></script>
 * <script type="text/javascript" src="/static/jquery/js/common-utils.js"></script>
 * <script src="/static/duallistbox/dist/dual-list-box.js"></script>
 */

var host_software_timer;
var host_software_selector;  
var host_software_package_filter;
var host_software_saved_software;
var host_software_dialog_spinner;

// Do not modify these string definitions as they have meaning on the backend.
var FILTER_ACTIVATE = "inactive,inactive-committed";
var FILTER_REMOVE = "inactive";
var FILTER_DEACTIVATE = "active,active-committed";   
    
var TITLE_ACTIVATE = "Install Action: Activate";
var TITLE_REMOVE = "Install Action: Remove";
var TITLE_DEACTIVATE = "Install Action: Deactivate";

$(function() {
    host_software_dialog_spinner = $('#host-software-dialog-browse-spinner');
    host_software_dialog_spinner.hide()
    
    host_software_selector = $('#host-software-selector').DualListBox(); 
    
    $('#host_software_dialog_host').on('change', function(e) {
        var selected_host = $('#host_software_dialog_host option:selected').val();
        if (selected_host.length > 0) {
            refresh_host_software(selected_host);
        } 
    }); 
    
    
    $('#host-software-dialog-auto-select-software').on('click', function(e) {
        // Cancel default behavior
        e.preventDefault(); 
        
        var hostname = $('#host_software_dialog_host').val();
        if (hostname.length > 0) {
            auto_select_software(hostname, host_software_selector, $('#host_software_dialog_target_software').val(), true);
        } else {
            bootbox.alert("Host has not been specified.");
        }
    });
    
    $('#host-software-retrieve-software').on('click', function(e) {
        host_software_dialog_spinner.show();
        
        var hostname = $('#host_software_dialog_host').val();
        if (hostname != null && hostname.length > 0) {
            $.ajax({
                url: '/api/get_software/' + hostname,
                success: function(response) {
                    if (response.status == 'OK') {
                        refresh_host_software(hostname);
                    } else {
                        bootbox.alert("<img src='/static/error.png'> &nbsp;A similar request may be in progress.");
                    }
                }
            });
        }
    });
    
    
    $('#host-software-dialog').on('shown.bs.modal', function(e) {
        host_software_timer = setInterval( function () {
            var hostname = $('#host_software_dialog_host').val();
            if (hostname != null && hostname.length > 0) {
                refresh_host_software(hostname);
            }
        }, 10000 ); 
    });
    
    $('#host-software-dialog').on('hidden.bs.modal', function(e) {
        clearInterval(host_software_timer);
    });
        
});

        
function initialize_host_software_dialog() {
    host_software_dialog_spinner.hide()
    host_software_saved_software = [];
    $('#host_software_dialog_host').empty();
    $('<option>', {value: '', text: ''}).appendTo($('#host_software_dialog_host')); 
    $('#host_software_dialog_last_successful_inventory_elapsed_time').val('');
    host_software_selector.initialize([], []);
}

function display_host_software_dialog(region_id, hostname_list, filter, target_release) {
    initialize_host_software_dialog();
          
    $('#host_software_dialog_target_software').val(target_release);
    
    var dialog_title = "";
    var selector_title = "";
      
    if (filter == FILTER_ACTIVATE) {
        dialog_title = TITLE_ACTIVATE;
        selector_title = "Inactive-Packages";
    } else if (filter == FILTER_REMOVE) {
        dialog_title = TITLE_REMOVE;
        selector_title = "Inactive-Packages";
    } else if (filter == FILTER_DEACTIVATE) {
        dialog_title = TITLE_DEACTIVATE;
        selector_title = "Active-Packages";
    }
    
    host_software_package_filter = filter;
      
    // Set the title text
    $('#host-software-dialog-title').html(dialog_title);
    host_software_selector.set_title(selector_title);
     
    // Only Install Activate will have auto-select of software packages.
    if (filter == FILTER_ACTIVATE) {
        $('#host-software-dialog-auto-select-software-panel').show();
    } else {
        $('#host-software-dialog-auto-select-software-panel').hide();
    }
      
    $('#host-software-dialog').modal({show:true, backdrop:'static'});

    if (hostname_list.length == 1) {
        var hostname = hostname_list[0];
        
        $('<option>', {value: hostname, text: hostname, selected: true}).appendTo($('#host_software_dialog_host'));
        if (filter == FILTER_REMOVE || filter == FILTER_DEACTIVATE) {
            refresh_host_software(hostname)
        } else {
            refresh_host_software(hostname)
        }
        
    } else {
        for (i = 0; i < hostname_list.length; i++) {
            $('<option>', {value: hostname_list[i], text: hostname_list[i]}).appendTo($('#host_software_dialog_host')); 
        }
    }
}

function refresh_host_software(hostname) {
    // Update the last successful inventory elapsed time
    $.ajax({
        url: '/api/hosts/' + hostname + '/last_successful_inventory_elapsed_time',  
        dataType: 'json',
        success: function(data) {
            $.each(data, function(index, element) {
                var elapsed_time = element[0].last_successful_inventory_elapsed_time;
                
                $('#host_software_dialog_last_successful_inventory_elapsed_time').val(elapsed_time);
                if (element[0].status == 'failed') {
                    $('#host_software_dialog_last_successful_inventory_elapsed_time').css({'color' : 'red'});
                } else {
                    $('#host_software_dialog_last_successful_inventory_elapsed_time').removeAttr('style');
                }   
                
                if (elapsed_time.indexOf('Pending') == -1) {
                    host_software_dialog_spinner.hide();  
                } else {
                    host_software_dialog_spinner.show(); 
                }                     
            });
        }
    });
       
    var host_software = [];
        
    $.ajax({
        url: '/api/hosts/' + hostname + '/packages',
        dataType: 'json',
        data: { package_state: host_software_package_filter} ,
        success: function(data) {
            $.each(data, function(index, element) {
                for (i = 0; i < element.length; i++) {
          
                    var software_package = element[i].package;             
                    // Remove the location string if exists.
                    var n = software_package.search(":"); 
                    if (n > 0) {
                        software_package = software_package.substring(n + 1);
                    }
                    // filter out the xr and sysadmin packages
                    if (software_package.indexOf("-xr-") > -1 || software_package.indexOf("-sysadmin-") > -1) {
                        // If it's a SMU, we do display the package
                        if (software_package.indexOf("CSC") == -1) {
                            continue;
                        }
                    }
                    host_software.push({
                        'id': software_package,
                        'name': software_package
                    });
                }
            });
          
            if (!is_same_software(host_software) ) {
                host_software_selector.initialize(host_software);
                save_host_software(host_software);
            }
        },
        error: function(XMLHttpRequest, textStatus, errorThrown) {
            bootbox.alert("Unable to retrieve host software. Error=" + errorThrown);
        }
    });      
}
    
function is_same_software(host_software) {
    for (i = 0; i < host_software.length; i++) {
        if ($.inArray(host_software[i].name, host_software_saved_software) == -1) {
          return false;
        }
    }
    return (host_software.length == host_software_saved_software.length);
}
  
function save_host_software(host_software) {
    host_software_saved_software = [];
      
    for (i = 0; i < host_software.length; i++) {
        host_software_saved_software.push(host_software[i].name);
    }
}


    
    