/**
 * This file requires a corresponding templates/share/cisco_software_dialog.html.
 * The following js files must be included by the caller.
 *
 * <script type="text/javascript" src="/static/jquery/js/common-utils.js"></script>
 * <script src="/static/bootbox-4.2.0/js/bootbox.js"></script>
 * <script src="/static/jquery-cookie-master/jquery.cookie.js"></script>
 * <script src="/static/jquery/js/smu_info_dialog.js"></script>
 */
 
var cisco_software_dialog_spinner;
var cisco_software_timer;

$(function() {

    var platform = '';
    var release = '';

    cisco_software_dialog_spinner = $('#cisco-software-dialog-browse-spinner');
    cisco_software_dialog_spinner.hide()

    var filter_option = $.cookie('platforms-and-releases-filter-option') == null ? 'Optimal' : $.cookie('platforms-and-releases-filter-option');
    $("#filter-selector option[value='" + filter_option + "']").attr('selected', 'selected');

    
    $('#smu-list-tab').tab();
    $('#smu-list-tab a:first').tab('show');
    
    var smu_table = $("#smu-datatable").dataTable({
        "order": [
            [1, "desc"]
        ],
        "scrollX": true,
        "scrollY": 400,
        "pageLength": 100,
        "fnCreatedRow": function(nRow, aData, iDataIndex) {
            var date_diff = date_diff_in_days(new Date($('td:eq(1)', nRow).text()), new Date());
            if (date_diff <= 7) {
                $('td', nRow).css('background-color', '#FFFFCC');
            }
        },
        "columnDefs": [{
            "sortable": false,
            "targets": 0,
            "data": 'package_name',
            "render": function(data, type, row) {
                return '<center><input type="checkbox" value="' + data + '" class="check"></center>';
            }
        }, {
            "targets": 1,
            "data": 'posted_date'
        }, {
            "targets": 2,
            "data": 'id',
            "render": function(data, type, row) {
                return '<a class="show-smu-info" smu_id="' + data + '" href="javascript://">' + data + '</a>'
            }
        }, {
            "targets": 3,
            "data": 'ddts_url'
        }, {
            "targets": 4,
            "data": 'type'
        }, {
            "targets": 5,
            "width": "42%",
            "data": 'description'
        }, {
            "targets": 6,
            "width": "10%",
            "data": 'impact'
        }, {
            "targets": 7,
            "width": "10%",
            "data": 'functional_areas'
        }, {
            "targets": 8,
            "data": 'status'
        }, {
            "targets": 9,
            "width": "20%",
            "data": 'package_bundles'
        }, ],

    }).on('draw.dt', function(e, settings, json) {
        var rows = 0;

        if (smu_table.api().ajax.json() != null) {
            rows = smu_table.api().ajax.json().data.length;
        }

        $('#badge-smu-list').html(rows);
        get_retrieval_elapsed_time();
    });

    var sp_table = $("#sp-datatable").dataTable({
        "order": [
            [1, "desc"]
        ],
        "scrollX": true,
        "scrollY": 400,
        "pageLength": 100,
        "fnCreatedRow": function(nRow, aData, iDataIndex) {
            var date_diff = date_diff_in_days(new Date($('td:eq(1)', nRow).text()), new Date());
            if (date_diff <= 7) {
                $('td', nRow).css('background-color', '#FFFFCC');
            }
        },
        "columnDefs": [{
            "sortable": false,
            "targets": 0,
            "data": 'package_name',
            "render": function(data, type, row) {
                return '<center><input type="checkbox" value="' + data + '" class="check"></center>';
            }
        }, {
            "targets": 1,
            "data": 'posted_date'
        }, {
            "targets": 2,
            "data": 'id',
            "render": function(data, type, row) {
                return '<a class="show-smu-info" smu_id="' + data + '" href="javascript://">' + data + '</a>'
            }
        }, {
            "targets": 3,
            "data": 'ddts_url'
        }, {
            "targets": 4,
            "data": 'type'
        }, {
            "targets": 5,
            "width": "42%",
            "data": 'description'
        }, {
            "targets": 6,
            "width": "10%",
            "data": 'impact'
        }, {
            "targets": 7,
            "data": 'functional_areas'
        }, {
            "targets": 8,
            "data": 'status'
        }, {
            "targets": 9,
            "width": "9%",
            "data": 'package_bundles'
        }, ],
    }).on('draw.dt', function(e, settings, json) {
        var rows = 0;
        if (sp_table.api().ajax.json() != null) {
            rows = sp_table.api().ajax.json().data.length;
        }
        $('#badge-sp-list').html(rows);
    });


    $('#cisco-dialog-move-up').on('click', function(e) {
        retrieve_file_list(
            $('#cisco_dialog_server').val(),
            $('#cisco_dialog_server_directory'),
            get_parent_folder($('#cisco_dialog_server_directory').val()));
    });

    $('#cisco_dialog_server').on('change', function(e) {
        server_id = $('#cisco_dialog_server option:selected').val();
        if (server_id == -1) {
            $('#cisco_dialog_server_directory').html('');
        } else {
            retrieve_file_list(server_id, $('#cisco_dialog_server_directory'), '')
        }
    });

    $('#cisco_dialog_server_directory').on('change', function(e) {
        retrieve_file_list(
            $('#cisco_dialog_server').val(), 
            $('#cisco_dialog_server_directory'), 
            $('#cisco_dialog_server_directory').val() );
    });
    
    $('#cisco-dialog-reset-server-directory').on('click', function(e) {
        reset_server_directory(
            $('#cisco_dialog_server').val(),
            $('#cisco_dialog_server_directory'),
            $('#cisco_dialog_server_directory').val() );
    });
    
    function reset_server_directory(server_id, server_directory_selector, server_directory) {
        if (server_directory != '') {    
            bootbox.confirm('Reset the server directory to use the server repository base directory?', function(result) {
                if (result) {
                    retrieve_file_list(server_id, server_directory_selector, '')
                }
            });
        }
    }
    
    $("#dropdown-cisco-menu").on("click", ".selected-platform-and-release", function() {
        platform = $(this).attr('platform');
        release = $(this).attr('release');
        refresh_tables();
    });


    function refresh_tables() {
        if (platform.length > 0 && release.length > 0) {
            $('#platform-and-release').html(beautify_platform(platform) + "-" + release + " > SMUs &nbsp;");
            //cisco_software_dialog_spinner.show();
            refresh_smu_list_table();
            refresh_sp_list_table();
        }
    }

    function refresh_smu_list_table() {
        if (platform.length > 0 && release.length > 0) {
            smu_table.api().ajax.url("/api/get_smu_list/platform/" + platform + "/release/" + release +
                "?filter=" + filter_option).load();
        }
    }

    function refresh_sp_list_table() {
        if (platform.length > 0 && release.length > 0) {
            sp_table.api().ajax.url("/api/get_sp_list/platform/" + platform + "/release/" + release +
                "?filter=" + filter_option).load();
        }
    }

    // Sets the correct filter icon color
    toggle_filter_icon_color(filter_option);

    $('#filter-selector').on('change', function(e) {
        filter_option = $(this).val();
        $.cookie('platforms-and-releases-filter-option', filter_option);
        toggle_filter_icon_color(filter_option);
        refresh_tables();
    });


    function toggle_filter_icon_color(filter_option) {
        if (filter_option == 'Optimal') {
            $('#filter-icon').addClass("DarkGreen");
            $('#filter-icon').removeClass("Red");
        } else {
            $('#filter-icon').removeClass("DarkGreen");
            $('#filter-icon').addClass("Red");
        }
    }

    $('#smu-check-all').click(function() {
        toggle_check_all(smu_table, this);
    });

    $('#sp-check-all').click(function() {
        toggle_check_all(sp_table, this);
    });

    function toggle_check_all(data_table, this_instance) {
        var filtered_rows = data_table.$('tr', {
            "filter": "applied"
        });
        
        for (var i = 0; i < filtered_rows.length; i++) {
            $(filtered_rows[i]).find('.check').prop('checked', this_instance.checked);
        }
    }

    /*----------                    Begin SMU Details                    ----------*/

    // Use delegate pattern for event
    $("#smu-datatable").on("click", ".show-smu-info", function() {
        display_smu_info_dialog($(this).attr('smu_id'));
    });

    $("#sp-datatable").on("click", ".show-smu-info", function() {
        display_smu_info_dialog($(this).attr('smu_id'));
    });

    function display_smu_info_dialog(smu_id) {
        init_history(smu_id);
        $('#smu-info-dialog').modal({
            show: true
        })
        display_smu_details($('#smu-details-table'), $('#smu-name-title'), smu_id)
    }

    // Use delegate pattern for event
    // This happens when the user clicks a pre-requisite/supersedes/superseded by SMU 
    // on the SMU info dialog.
    $("#smu-info-dialog").on("click", ".show-smu-hyperlink-details", function() {
        display_smu_details($('#smu-details-table'), $('#smu-name-title'), $(this).attr('smu_id'));
        add_to_history($(this).attr('smu_id'));
    });

    $("#move-back").on("click", function() {
        move_back($('#smu-details-table'), $('#smu-name-title'));
    });

    $("#move-forward").on("click", function() {
        move_forward($('#smu-details-table'), $('#smu-name-title'));
    });

    /*----------                    End SMU Details                    ----------*/
    
    $('#cisco-software-dialog').on('shown.bs.modal', function(e) {
        cisco_software_timer = setInterval( function () {
            get_retrieval_elapsed_time();
        }, 10000 ); 
    });
    
    $('#cisco-software-dialog').on('hidden.bs.modal', function(e) {
      clearInterval(cisco_software_timer);
    });
    
    function get_retrieval_elapsed_time() {
        if (platform.length > 0 && release.length > 0) {
            //var cco_lookup_enabled = "{{ system_option.enable_cco_lookup }}";
            //if (cco_lookup_enabled) {
                $.ajax({
                    url: "/api/get_smu_meta_retrieval_elapsed_time/platform/" + platform + "/release/" + release,
                    dataType: 'json',
                    success: function(response) {
                        $.each(response, function(index, element) {
                            $('#retrieval-elapsed-time').html('Retrieved: ' + element[0].retrieval_elapsed_time);
                        });
                    }
                });
            //}
        }
    }
    
    // The SP table has problem with the table layout
    $('#smu-list-tab a[href="#sp-tab"]').click(function() {
        setTimeout(function() {
            refresh_sp_list_table();
        }, 300);
    });
    
      
});

function display_cisco_software_dialog(server_id, server_directory) {
    create_menu();
      
    $('#smu-check-all').prop('checked', false)
    $('#sp-check-all').prop('checked', false);
  
    $('#cisco-software-dialog').modal({show:true, backdrop:'static'})
    
    if (server_id && server_id != -1) {
        $('#cisco_dialog_server').val(server_id);
        retrieve_file_list(server_id, $('#cisco_dialog_server_directory'), server_directory);
    }
}

function retrieve_file_list(server_id, server_directory_selector, server_directory) {
    server_directory_selector.html('');
    server_directory_selector.append('<option value="' + server_directory + '">' + server_directory + '</option>');

   cisco_software_dialog_spinner.show();
      
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
                    populate_file_list(element, server_directory_selector, server_directory);
                });
            }

             cisco_software_dialog_spinner.hide();
        },
        error: function(XMLHttpRequest, textStatus, errorThrown) {
            bootbox.alert("Unable to list files. Server repository may not be visible by CSM Server.");
            cisco_software_dialog_spinner.hide();
        }
    });
}
    
function populate_file_list(element, server_directory_selector, server_directory) {
    for (i = 0; i < element.length; i++) {
        var filename = element[i].filename;
        var is_directory = element[i].is_directory;

        if (is_directory == true) {
            server_directory_selector.append('<option value="' + filename + '">' + filename + '</option>');
        }
    }
}
    
function create_menu() {
    $.ajax({
        url: "/api/get_catalog",
        dataType: 'json',
        success: function(data) {
            var html = '';

            $.each(data, function(index, element) {
                for (i = 0; i < element.length; i++) {
                    var beautified_platform = element[i].beautified_platform
                    var platform = element[i].platform;
                    var releases = element[i].releases;

                    html += '<li class="dropdown-submenu">' +
                        '<a href="javascript://">' + beautified_platform + '</a>' +
                        '<ul class="dropdown-menu">';

                    for (var j = 0; j < releases.length; j++) {
                        html += '<li><a class="selected-platform-and-release" href="javascript://" \
                            platform="' + platform + '" \
                            release="' + releases[j] + '">' + releases[j] + '</a></li>'
                    }
                    html += '</ul>' + '</li>'
                }
            });
          
            $('#dropdown-cisco-menu').html(html);
        },
        error: function(XMLHttpRequest, textStatus, errorThrown) {
            //bootbox.alert("Unable to retrieve catalog data");
        }
    });
}
