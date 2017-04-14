/***
  * Usage:
  *  var select_server = $('#select-server').SelectServerRepo();
  *
  * Markup:
  *  <div><div id="select-server" data-name="select-server"></div></div>
  **/

(function ( $ ) {
    "use strict";

    var select_server_spinner;

    $.fn.SelectServerRepo = function(options) {
        return this.each(function () {

            var defaults = {
                element:  $(this).context,
                name:     $(this).data('name'),
            };

            var options = $.extend({}, defaults, options);

            options['parent'] = 'select-server-repo-' + options.name;
            options['parent_element'] = '#' + options.parent;

            $(this).data('options', options);

            create_gui(options);

            select_server_spinner = $('.select-server-spinner').hide();

            $(options.parent_element + ' .select_server').on('change', function(e) {
                var select_server_directory_ui = $(options.parent_element + ' .select_server_directory');

                var server_id = $(this).val();
                if (server_id == -1) {
                    select_server_directory_ui.html('');
                } else {
                    retrieve_file_list(server_id, select_server_directory_ui, '')
                }
            });

            $(options.parent_element + ' .select_server_directory').on('change', function(e) {
                var select_server_ui = $(options.parent_element + ' .select_server');

                retrieve_file_list(
                            select_server_ui.val(),
                            $(this),
                            $(this).val() );
            });

            $(options.parent_element + ' .select-server-move-up').on('click', function(e) {
                var select_server_ui = $(options.parent_element + ' .select_server');
                var select_server_directory_ui = $(options.parent_element + ' .select_server_directory');

                retrieve_file_list(
                    select_server_ui.val(),
                    select_server_directory_ui,
                    get_parent_folder(select_server_directory_ui.val()));
            });

            $(options.parent_element + ' .select-server-reset-server-directory').on('click', function(e) {
                var select_server_ui = $(options.parent_element + ' .select_server');
                var select_server_directory_ui = $(options.parent_element + ' .select_server_directory');

                reset_server_directory(
                    select_server_ui.val(),
                    select_server_directory_ui,
                    select_server_directory_ui.val());
            });

        })
    };

    $.fn.get_server_id = function() {
        var options = $(this).data('options');
        return $(options.parent_element + ' .select_server option:selected').val();
    };

    $.fn.get_server_name = function() {
        var options = $(this).data('options');
        return $(options.parent_element + ' .select_server option:selected').text();
    };

    $.fn.get_server_directory = function() {
        var options = $(this).data('options');
        return $(options.parent_element + ' .select_server_directory option:selected').val();
    };

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

    function reset_server_directory(server_id, server_directory_ui, server_directory) {
        if (server_directory != '') {
            bootbox.confirm('Reset the server directory to use the server repository base directory?', function(result) {
                if (result) {
                    retrieve_file_list(server_id, server_directory_ui, '')
                }
            });
        }
    }

    function retrieve_file_list(server_id, server_directory_ui, server_directory) {
        server_directory_ui.html('');
        server_directory_ui.append('<option value="' + server_directory + '">' + server_directory + '</option>');

        select_server_spinner.show();

        $.ajax({
            url: "/install/api/get_server_file_dict/" + server_id,
            dataType: 'json',
            data: {
                server_directory: server_directory
            },
            success: function(response) {
                if (response.status == 'Failed') {
                    bootbox.alert("NOTE: The selected server repository is not browsable by CSM Server.");
                } else {
                    $.each(response, function(index, element) {
                        populate_file_list(element, server_directory_ui, server_directory);
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

    function populate_file_list(element, server_directory_ui, server_directory) {
        for (i = 0; i < element.length; i++) {
            var filename = element[i].filename;
            var is_directory = element[i].is_directory;

            if (is_directory == true) {
                server_directory_ui.append('<option value="' + filename + '">' + filename + '</option>');
            }
        }
    }

    function create_gui(options) {
         $(options.element).parent().attr('id', options.parent);

         $(options.parent_element).addClass('row').append(
             '<div class="form-group ">' +
                 '<label class="col-sm-4 control-label">Server Repository</label>' +
                 '<div class="col-sm-7">' +
                     '<select class="form-control select_server"><option value="-1"></option></select>' +
                 '</div>' +
                 '<span class="select-server-spinner">' +
                     '<img src="/static/spinner.gif">' +
                 '</span>' +
             '</div>' +
             '<div class="form-group ">' +
                 '<label class="col-sm-4 control-label">Server Directory</label>' +
                 '<div class="col-sm-7">' +
                     '<select class="form-control select_server_directory"><option value=""></select>' +
                 '</div>' +
                 '<a href="javascript://">' +
                     '<img class="select-server-move-up" src="/static/up_arrow.png" title="Go to Parent Folder">' +
                     '<img class="select-server-reset-server-directory" src="/static/remove.png" title="Reset Server Directory">' +
                 '</a>' +
             '</div>'
         );
    }

    /**
     * Initialize the plugin with all the available system server repositories.
     **/
    $.fn.initialize_servers = function() {
        $(this).initialize_servers_by_region(0);
    }

    /**
     * Initialize the plugin with server repositories that are available to this host (i.e. for the region).
     **/
    $.fn.initialize_servers_by_hostname = function(hostname) {
        var options = $(this).data('options');
        var select_server_ui = $(options.parent_element + ' .select_server');
        var select_server_directory_ui = $(options.parent_element + ' .select_server_directory');

        select_server_ui.empty().append('<option value=-1></option>');
        select_server_directory_ui.empty().append('<option value=""></option>');

        $.ajax({
            url: "/api/get_servers/host/" + hostname,
            dataType: 'json',
            success: function(data) {
                $.each(data, function(index, element) {
                    for (i = 0; i < element.length; i++) {
                        var server_id = element[i].server_id;
                        var hostname = element[i].hostname;

                        select_server_ui.append('<option value="' + server_id + '">' + hostname + '</option>');
                    }
                });
            },
            error: function(xhr, status, errorThrown) {
                bootbox.alert("Unable to retrieve server list. Error=" + errorThrown);
            }
        });
    }

    /**
     * Initialize the plugin with server repositories that are available to this region.
     **/
    $.fn.initialize_servers_by_region = function (region_id) {
        var options = $(this).data('options');
        var select_server_ui = $(options.parent_element + ' .select_server');
        var select_server_directory_ui = $(options.parent_element + ' .select_server_directory');

        select_server_ui.empty().append('<option value=-1></option>');
        select_server_directory_ui.empty().append('<option value=""></option>');

        $.ajax({
            url: "/api/get_servers/region/" + region_id,
            dataType: 'json',
            success: function(data) {
                $.each(data, function(index, element) {
                    for (i = 0; i < element.length; i++) {
                        var server_id = element[i].server_id;
                        var hostname = element[i].hostname;

                        select_server_ui.append('<option value="' + server_id + '">' + hostname + '</option>');
                    }
                });
            },
            error: function(xhr, status, errorThrown) {
                bootbox.alert("Unable to retrieve server list. Error=" + errorThrown);
            }
        });
    }

}( jQuery ));