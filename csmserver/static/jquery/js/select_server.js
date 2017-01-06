/**
 * This file requires a corresponding templates/shared/select_server.html.
 * The following js files must be included by the caller.
 *
 * <script src="/static/jquery-cookie-master/jquery.cookie.js"></script>
 * <script src="/static/bootbox-4.2.0/js/bootbox.js"></script>
 *
 * To initialize the server selector, call either
 *   initialize_server_by_hostname(hostname)
 *   initialize_server_by_region(region_id)
 *
 * To retrieve the selected server ID
 *     $('#select_server').val()
 *
 * To retrieve the selected server name
 *     $('#select_server').text()
 *
 * To retrieve the selected server directory
 *     $('#select_server_directory').val()
 */

var select_server_spinner;

$(function() {

    select_server_spinner = $('#select-server-spinner');
    select_server_spinner.hide()

    $('#select-server-move-up').on('click', function(e) {
        retrieve_file_list(
            $('#select_server').val(),
            $('#select_server_directory'),
            get_parent_folder($('#select_server_directory').val()));
    });

    $('#select_server').on('change', function(e) {
        server_id = $('#select_server option:selected').val();
        if (server_id == -1) {
            $('#select_server_directory').html('');
        } else {
            retrieve_file_list(server_id, $('#select_server_directory'), '')
        }
    });

    $('#select_server_directory').on('change', function(e) {
        retrieve_file_list(
            $('#select_server').val(),
            $('#select_server_directory'),
            $('#select_server_directory').val() );
    });

    $('#select-server-reset-server-directory').on('click', function(e) {
        reset_server_directory(
            $('#select_server').val(),
            $('#select_server_directory'),
            $('#select_server_directory').val() );
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

    function retrieve_file_list(server_id, server_directory_selector, server_directory) {
        server_directory_selector.html('');
        server_directory_selector.append('<option value="' + server_directory + '">' + server_directory + '</option>');

        select_server_spinner.show();

        $.ajax({
            url: "/install/api/get_server_file_dict/" + server_id,
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

                select_server_spinner.hide();
            },
            error: function(XMLHttpRequest, textStatus, errorThrown) {
                bootbox.alert("Unable to list files. Server repository may not be visible by CSM Server.");
                select_server_spinner.hide();
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

});

function initialize_server_by_hostname(hostname) {
    // Now, gets the servers for the selected region
    $('#select_server').empty().append('<option value=-1></option>');

    $.ajax({
        url: "/api/get_servers/host/" + hostname,
        dataType: 'json',
        success: function(data) {
            $.each(data, function(index, element) {
                for (i = 0; i < element.length; i++) {
                    var server_id = element[i].server_id;
                    var hostname = element[i].hostname;

                    $('#select_server').append('<option value="' + server_id + '">' + hostname + '</option>');
                }
            });
        },
        error: function(xhr, status, errorThrown) {
            bootbox.alert("Unable to retrieve server list. Error=" + errorThrown);
        }
    });
}

function initialize_server_by_region(region_id) {
    // Now, gets the servers for the selected region
    $('#select_server').empty().append('<option value=-1></option>');

    $.ajax({
        url: "/api/get_servers/region/" + region_id,
        dataType: 'json',
        success: function(data) {
            $.each(data, function(index, element) {
                for (i = 0; i < element.length; i++) {
                    var server_id = element[i].server_id;
                    var hostname = element[i].hostname;

                    $('#select_server').append('<option value="' + server_id + '">' + hostname + '</option>');
                }
            });
        },
        error: function(xhr, status, errorThrown) {
            bootbox.alert("Unable to retrieve server list. Error=" + errorThrown);
        }
    });
}