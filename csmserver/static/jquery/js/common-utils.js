/*
Given the field and value, returns the html code for a table row.
The argument value may contain ','.  In that case, it will be displayed
as multiple lines.
*/
function create_html_table_row(field, value) {
    var html_code = '';
    if (value != null && value.length > 0) {
        var an_array = value.split(',');
        for (var i = 0; i < an_array.length; i++) {
            if (i == 0) {
                html_code = '<tr><td>' + field + '</td><td>' + an_array[i] + '</td></tr>';
            } else {
                html_code += '<tr><td>&nbsp;</td><td>' + an_array[i] + '</td></tr>';
            }
        }
        return html_code;
    } else {
        return '';
    }
}

function create_html_table_row_with_commas(field, value){
    var html_code = '';
    if (value != null && value.length > 0){
        html_code += '<tr><td>' + field + '</td><td class="value">' + value + '</td></tr>';
    }

    return html_code;
}

function get_acceptable_string(input_string) {
    return input_string.replace(/[^a-z0-9()._-\s]/gi, '').replace(/\s+/g, " ");
}

function get_acceptable_string_message(field, old_value, new_value) {
    return field + " '" + old_value + "' contains invalid characters.  It is recommended that it be changed to '" + new_value + "'.  Change?";
}

function read_cookie_value(key, default_value) {
    var value = $.cookie(key);
    return (value == null ? (default_value == null ? value : default_value) : value);
}

function write_cookie_value(key, value) {
    $.cookie(key, value);
}

/*
 * Trims all whitespaces from lines include blank lines and returns result as separate lines
 */
function trim_lines(lines) {
    if (lines == null) return lines;

    var result = '';
    temp = lines.split('\n');
    for (var i = 0; i < temp.length; i++) {
        line = temp[i].replace(/\s+/g,' ').trim();
        if (line.length > 0) {
            result += (i == temp.length - 1) ? line : line + '\n';
        }
    }
    return result;
}

function beautify_platform(platform) {
    return platform.toUpperCase().replace('_', '-');
}

/**
 * Converts comma delimited string to HTML line break delimited.
 */
function comma2br(s) {
    return s.replace(/,/g, "<br>")
}

/**
 * Converts comma delimited string to line break ('\n') delimited.
 */
function comma2newline(s) {
    return s.replace(/,/g, "\n")
}

/**
 * Converts new line characters to html line break (<br>).
 */
function newline2linebreak(s) {
    return s.replace(/\n/g, "<br>")
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

var _MS_PER_DAY = 1000 * 60 * 60 * 24;

// a and b are javascript Date objects
function date_diff_in_days(a, b) {
    // Discard the time and time-zone information.
    var utc1 = Date.UTC(a.getFullYear(), a.getMonth(), a.getDate());
    var utc2 = Date.UTC(b.getFullYear(), b.getMonth(), b.getDate());

    return Math.floor((utc2 - utc1) / _MS_PER_DAY);
}

function has_one_of_these(items_list, search_items) {
    if (items_list != null) {
        for (i = 0; i < items_list.length; i++) {
            if ($.inArray(items_list[i], search_items) > -1) {
                return true;
            }
        }
    }
    return false;
}

function has_one_of_these_only(items_list, search_items) {
    if (items_list != null) {
        for (i = 0; i < items_list.length; i++) {
            if ($.inArray(items_list[i], search_items) == -1) {
                return false;
            }
        }
        return true;
    }
    return false;
}

/**
 * Converts the lines which are separated by a newline character
 * into a list.  Each line will be trimmed and if the line is
 * empty,  it will be removed.
 */
function convert_lines_to_list(lines) {
    var result_list = new Array();

    lines = lines.split('\n');

    $.each(lines, function() {
        var line = this.trim();
        if (line.length > 0) {
            result_list.push(line);
        }
    });

    return result_list;
}

/**
 * Converts a list of string into lines separated by a '\n' character.
 */
function convert_list_to_lines(list) {
    var lines = '';

    for (i = 0; i < list.length; i++) {
        if (list[i].trim().length > 0) {
            lines += list[i].trim() + '\n';
        }
    }

    return lines;
}


/*
 The validate_object should be initialized as below in order to use this function.

 var validate_object = {
   form: current_form,
   hostname: hostname,
   server_id: $('#hidden_server').val(),
   server_directory: $('#hidden_server_directory').val(),
   software_packages: $('#software-packages').val(),
   spinner: submit_spinner,
   install_actions: $('#install_action').val(),
   check_missing_file_on_server: true,
   callback: on_finish_validate,
   pending_downloads: null
 };
*/
function on_validate_prerequisites_and_files_on_server(validate_object) {
    check_missing_prerequisite(validate_object);
}

function check_missing_prerequisite(validate_object) {
    if (validate_object.spinner != null ) validate_object.spinner.show();

    // Only '.pie' or '.tar' files should be checked

    $.ajax({
        url: "/install/api/get_missing_prerequisite_list",
        dataType: 'json',
        data: {
            smu_list: trim_lines(validate_object.software_packages),
            hostname: validate_object.hostname
        },
        success: function(data) {
            var missing_prerequisite_list = '';
            var missing_prerequisite_annotated_list = ''
            $.each(data, function(index, element) {
                for (i = 0; i < element.length; i++) {
                    var description = (element[i].description.length > 0) ? ' - ' + element[i].description : '';
                    missing_prerequisite_list += element[i].smu_entry + '<br>';
                    missing_prerequisite_annotated_list += element[i].smu_entry + description + '<br>';
                }
            });

            if (missing_prerequisite_list.length == 0) {
                if (validate_object.check_missing_file_on_server) {
                    // Check the reload packages only if install actions has 'Activate' in it.
                    if (has_one_of_these(validate_object.install_actions, ['Activate'])) {
                        check_need_reload(validate_object);
                    } else {
                        check_missing_files_on_server(validate_object);
                    }
                } else {
                    validate_object.callback(validate_object);
                }
            } else {
                display_missing_prerequisite_dialog(validate_object, missing_prerequisite_list, missing_prerequisite_annotated_list);
            }

        },
        error: function(XMLHttpRequest, textStatus, errorThrown) {
            if (validate_object.spinner != null )  validate_object.spinner.hide();
        }
    });
}

function check_need_reload(validate_object) {
    $.ajax({
        url: "/install/api/get_reload_list",
        dataType: 'json',
        data: {
            package_list: trim_lines(validate_object.software_packages)
        },
        success: function(data) {
            var reload_list = '';
            $.each(data, function(index, element) {
                for (i = 0; i < element.length; i++) {
                    var description = (element[i].description.length > 0) ? ' - ' + element[i].description : '';
                    reload_list += element[i].entry + description + '<br>';
                }
            });

            // If there is no reload packages
            if (reload_list.length == 0) {
                if (validate_object.check_missing_file_on_server) {
                    check_missing_files_on_server(validate_object);
                } else {
                    validate_object.callback(validate_object);
                }
            } else {
                display_package_reload_dialog(validate_object, reload_list);
            }
        },
        error: function(XMLHttpRequest, textStatus, errorThrown) {
            if (validate_object.spinner != null ) validate_object.spinner.hide();
        }
    });
}

function display_package_reload_dialog(validate_object, reload_list) {

    bootbox.dialog({
        message: reload_list,
        title: "<span style='color:red;'>Following software packages may cause the router to reload during 'Activate'.</span>",
        buttons: {
            primary: {
                label: "Continue",
                className: "btn-primary",
                callback: function() {
                    if (validate_object.check_missing_file_on_server) {
                        check_missing_files_on_server(validate_object);
                    } else {
                        validate_object.callback(validate_object);
                    }
                }
            },
            main: {
                label: "Cancel",
                className: "btn-default",
                callback: function() {
                    if (validate_object.spinner != null ) validate_object.spinner.hide();
                }
            }
        }
    });

}

function display_missing_prerequisite_dialog(validate_object, missing_prerequisite_list, missing_prerequisite_annotated_list) {

    bootbox.dialog({
        message: missing_prerequisite_annotated_list,
        title: "Following pre-requisite(s) were not selected, but should be included.",
        buttons: {
            primary: {
                label: "Include Pre-requisites",
                className: "btn-primary",
                callback: function() {
                    // Add the missing pre-requisites
                    validate_object.software_packages =
                        trim_lines(validate_object.software_packages + '\n' + missing_prerequisite_list.replace(/<br>/g, "\n"))

                    if (validate_object.check_missing_file_on_server) {
                        // Check the reload packages only if install actions has 'Activate' in it.
                        if (has_one_of_these(validate_object.install_actions, ['Activate'])) {
                            check_need_reload(validate_object);
                        } else {
                            check_missing_files_on_server(validate_object);
                        }
                    } else {
                        validate_object.callback(validate_object);
                    }
                }
            },
            success: {
                label: "Ignore",
                className: "btn-success",
                callback: function() {
                    if (validate_object.check_missing_file_on_server) {
                        if (has_one_of_these(validate_object.install_actions, ['Activate'])) {
                            check_need_reload(validate_object);
                        } else {
                            check_missing_files_on_server(validate_object);
                        }
                    } else {
                        validate_object.callback(validate_object);
                    }
                    if (validate_object.spinner != null ) validate_object.spinner.hide();
                }
            },
            main: {
                label: "Cancel",
                className: "btn-default",
                callback: function() {
                    if (validate_object.spinner != null ) validate_object.spinner.hide();
                }
            }
        }
    });

}

function check_missing_files_on_server(validate_object) {
    if (validate_object.spinner != null ) validate_object.spinner.show();

    // Only '.pie' or '.tar' files should be checked

    $.ajax({
        url: "/install/api/get_missing_files_on_server/" + validate_object.server_id,
        dataType: 'json',
        data: {
            smu_list: trim_lines(validate_object.software_packages),
            server_directory: validate_object.server_directory
        },
        success: function(response) {
            if (response.status == 'Failed') {
                display_server_unreachable_dialog(validate_object);
            } else {
                var missing_file_count = 0;
                var missing_file_list = '';
                var downloadable_file_list = '';

                $.each(response, function(index, element) {
                    missing_file_count = element.length;
                    for (i = 0; i < element.length; i++) {
                        var description = (element[i].description.length > 0) ? ' - ' + element[i].description : '';
                        if (element[i].is_downloadable) {
                            missing_file_list += element[i].smu_entry + ' (Downloadable) ' + description + '<br>';
                            downloadable_file_list += element[i].cco_filename + '\n';
                        } else {
                            missing_file_list += '<font color="red">' + element[i].smu_entry + ' (Not Downloadable) ' + description + '</font><br>';
                        }
                    }
                });

                // There is no missing files, go ahead and submit
                if (missing_file_count == 0) {
                    validate_object.callback(validate_object);
                    // Scheduled Install will not reach the message below as the above function will cause a form submission.
                    // This message is intended for the Platforms menu since there is no form submission (i.e. form == null).
                    if (validate_object.form == null) {
                        bootbox.alert("Requested file(s) already on the selected server repository.  No download is needed.");
                    }
                } else {
                    if (validate_object.cco_lookup_enabled) {
                        display_downloadable_files_dialog(validate_object, missing_file_list, downloadable_file_list);
                    } else {
                        display_unable_to_download_dialog(validate_object, missing_file_list);
                    }
                }
            }
        },
        error: function(XMLHttpRequest, textStatus, errorThrown) {
            if (validate_object.spinner != null ) validate_object.spinner.hide();
        }
    });
}

function check_tars_downloadable(validate_object) {
    if (validate_object.spinner != null ) validate_object.spinner.show();

    // Only '.pie' or '.tar' files should be checked

    $.ajax({
        url: "/install/api/check_is_tar_downloadable",
        dataType: 'json',
        data: {
            smu_list: trim_lines(validate_object.software_packages)
        },
        success: function(response) {
            var missing_file_count = 0;
            var missing_file_list = '';
            var downloadable_file_list = '';

            $.each(response, function(index, element) {
                missing_file_count = element.length;
                for (i = 0; i < element.length; i++) {
                    var description = (element[i].description.length > 0) ? ' - ' + element[i].description : '';
                    if (element[i].is_downloadable) {
                        missing_file_list += element[i].smu_entry + ' (Downloadable) ' + description + '<br>';
                        downloadable_file_list += element[i].cco_filename + '\n';
                    } else {
                        missing_file_list += element[i].smu_entry + ' (Not Downloadable) ' + description + '<br>';
                    }
                }
            });

            // There is no missing files, go ahead and submit
            if (missing_file_count == 0) {
                validate_object.callback(validate_object);
            } else {
                display_downloadable_tar_files(validate_object, missing_file_list, downloadable_file_list);
            }
        },
        error: function(XMLHttpRequest, textStatus, errorThrown) {
            if (validate_object.spinner != null ) validate_object.spinner.hide();
        }
    });
}

function display_unable_to_download_dialog(validate_object, missing_file_list) {
    bootbox.dialog({
        message: missing_file_list,
        title: "<span style='color:red;'>Following files are missing on the server repository.  Files that are marked as 'Downloadable' " +
            "will not be downloaded because the administrator has disabled outgoing CCO connection.</span>",
        buttons: {
            success: {
                label: "Ignore",
                className: "btn-success",
                callback: function() {
                    if (validate_object.spinner != null ) validate_object.spinner.hide();
                    validate_object.callback(validate_object);
                }
            },
            main: {
                label: "Cancel",
                className: "btn-default",
                callback: function() {
                    if (validate_object.spinner != null ) validate_object.spinner.hide();
                }
            }
        }
    });
}

function display_downloadable_files_dialog(validate_object, missing_file_list, downloadable_file_list) {
    bootbox.dialog({
        message: missing_file_list,
        title: "Following files are missing on the server repository.  Those that are identified as 'Downloadable' can be downloaded from CCO.  If there is an scheduled installation that depends on these files, " +
            "it will not proceed until the files are successfully downloaded and copied to the server repository.",
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
                    if (validate_object.spinner != null ) validate_object.spinner.hide();
                    validate_object.callback(validate_object);
                }
            },
            main: {
                label: "Cancel",
                className: "btn-default",
                callback: function() {
                    if (validate_object.spinner != null ) validate_object.spinner.hide();
                }
            }
        }
    });
}

function check_cisco_authentication(validate_object) {
    $.ajax({
        url: "/cco/api/check_cisco_authentication/",
        type: "POST",
        dataType: 'json',
        success: function(response) {
            if (response.status == 'OK') {
                validate_object.callback(validate_object);
            } else {
                bootbox.alert("Cisco user authentication information has not been entered.  Go to Tools - User Preferences to enter it.");
                if (validate_object.spinner != null ) validate_object.spinner.hide();
            }
        },
        error: function(XMLHttpRequest, textStatus, errorThrown) {
            if (validate_object.spinner != null ) validate_object.spinner.hide();
        }
    });
}

function display_server_unreachable_dialog(validate_object) {
    bootbox.dialog({
        message: "CSM Server is unable to verify the existence of the software packages on the server repository.   " +
            "Either there is a network intermittent issue or the server repository is not reachable or browsable.  " +
            "You can still proceed if the device can reach the server repository.",
        title: "Server repository is not reachable",
        buttons: {
            primary: {
                label: "Continue",
                className: "btn-primary",
                callback: function() {
                    if (validate_object.spinner != null ) validate_object.spinner.hide();
                    validate_object.callback(validate_object);
                }
            },
            main: {
                label: "Cancel",
                className: "btn-default",
                callback: function() {
                    if (validate_object.spinner != null ) validate_object.spinner.hide();
                }
            }
        }
    });
}

function validate_package_count_restriction(software_platform, software_version, software_packages) {
    // For ASR9K/CRS, software version above 5.3.2 can support up to 27 pies.
    // Prior to this release, only 16 pies are supported.
    if (software_platform != null && software_version != null && software_packages != null &&
       (software_platform == 'ASR9K' || software_platform == 'CRS')) {
        var version = software_version;
        // Normalize the version from 5.3.3.23I -> 5.3.3
        if (version.length > 5) {
            version.substring(0, 5);
        }

        version = parseInt(version.replace(/\./g,''));
        if (!isNaN(version)) {
            var package_count = trim_lines(software_packages).split('\n').length;
            if (version >= 532 && package_count > 27) {
                bootbox.alert("Due to the limitation of the Install Manager on the device, " +
                    "it can only handle a maximum of 27 software packages for Release " + software_version + ".  " +
                    "For Install Add, use a tar archive file instead.");
                return false;
            } else if (version < 532 && package_count > 16) {
                bootbox.alert("Due to the limitation of the Install Manager on the device, " +
                    "it can only handle a maximum of 16 software packages for Release " + software_version + ".  " +
                    "For Install Add, use a tar archive file instead.");
                return false;
            }
        }
    }
    return true;
}

/**
 * platform_ui is just a regular selector
 */
function populate_host_platforms(platform_ui) {
    platform_ui.find('option').remove();
    platform_ui.append('<option value=""></option>');
    $.ajax({
        url: "/api/get_distinct_host_platforms",
        dataType: 'json',
        success: function(data) {
            $.each(data, function(index, element) {
                for (i = 0; i < element.length; i++) {
                    var platform = element[i].platform;
                    if (platform != 'Unknown') {
                        platform_ui.append('<option value="' + platform + '">' + platform + '</option>');
                    }
                }
            });
        }
    });
}

/**
 * platform_ui is just a regular selector
 * software_ui is a Select2 selector
 */
function populate_host_software_versions(platform_ui, software_ui) {
    software_ui.find('option').remove();
    software_ui.append('<option value="ALL">ALL</option>');
    $.ajax({
        url: "/api/get_distinct_host_software_versions/platform/" + platform_ui.val(),
        dataType: 'json',
        success: function(data) {
            $.each(data, function(index, element) {
                for (i = 0; i < element.length; i++) {
                    var software_version = element[i].software_version;
                    software_ui.append('<option value="' + software_version + '">' + software_version + '</option>');;
                }
            });
        }
    });
}

/**
 * platform_ui is just a regular selector
 * software_ui is a Select2 selector
 * region_ui is a Select2 selector
 */
function populate_host_regions(platform_ui, software_ui, region_ui) {
    region_ui.find('option').remove();
    region_ui.append('<option value="ALL">ALL</option>');
    $.ajax({
        url: "/api/get_distinct_host_regions/platform/" + platform_ui.val() +
             "/software_versions/" + (software_ui.val() == null ? 'ALL' : software_ui.val()),
        dataType: 'json',
        success: function(data) {
            $.each(data, function(index, element) {
                for (i = 0; i < element.length; i++) {
                    region_ui.append('<option value="' + element[i].region_id + '">' + element[i].region_name + '</option>');;
                }
            });
        }
    });
}

/**
 * platform_ui is just a regular selector
 * software_ui is a Select2 selector
 * region_ui is a Select2 selector
 * roles_ui is a Select2 selector
 */
function populate_host_roles(platform_ui, software_ui, region_ui, roles_ui) {
    roles_ui.find('option').remove();
    roles_ui.append('<option value="ALL">ALL</option>');
    $.ajax({
        url: "/api/get_distinct_host_roles/platform/" + platform_ui.val() +
             "/software_versions/" + (software_ui.val() == null ? 'ALL' : software_ui.val()) +
             "/region_ids/" +  ((region_ui.val() == null || region_ui.val() == -1) ? 'ALL' : region_ui.val()),
        dataType: 'json',
        success: function(data) {
            $.each(data, function(index, element) {
                for (i = 0; i < element.length; i++) {
                    roles_ui.append('<option value="' + element[i].role + '">' + element[i].role + '</option>');;
                }
            });
        }
    });
}
