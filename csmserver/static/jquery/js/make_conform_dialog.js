/**
 * This file requires a corresponding templates/conformance/make_conform_dialog.html.
 * The following js files must be included by the caller.
 *
 * <link rel="stylesheet" href="/static/datetimepicker/css/bootstrap-datetimepicker.min.css">
 * <script src="/static/datetimepicker/js/bootstrap-datetimepicker.min.js"></script>
 *
 * <script src="/static/jquery/js/select_server_dialog.js"></script>
 */

var make_conform_dialog_spinner;
var host_software_platform = null;
var host_software_version = null;

$(function() {

    make_conform_dialog_spinner = $('#make-conform-dialog-spinner');
    make_conform_dialog_spinner.hide()
    $('#custom-command-profile-panel').hide();

    var server_time_as_locale_time = convertToLocaleString($('#make-conform-dialog').attr('data-server-time'));

    $("#install_action").select2({});

    $("#custom_command_profile").select2({
        placeholder: 'Optional'
    });

    var datetimepicker = $(".form_datetime").datetimepicker({
        format: "mm/dd/yyyy HH:ii P",
        showMeridian: true,
        autoclose: true,
        todayBtn: true,
        pickerPosition: "top-left",
        todayHighlight: true
    });

    $('#install_action').on('change', function(e) {
        var install_actions = $(this).val();
        if (has_one_of_these(install_actions, ['ALL'])) {
            $("#install_action").val(['Pre-Upgrade', 'Add', 'Activate', 'Post-Upgrade', 'Commit']).trigger('change');
        }
        if (has_one_of_these(install_actions, ['Pre-Upgrade', 'Post-Upgrade', 'ALL'])) {
            $('#custom-command-profile-panel').show();
        } else {
            $('#custom-command-profile-panel').hide();
        }
    });

    $('#make-conform-dialog-wizard').bootstrapWizard({
        'tabClass': 'nav nav-pills',
        'nextSelector': '.btn-next',
        'previousSelector': '.btn-previous',

        onInit : function(tab, navigation, index){
            //check number of tabs and fill the entire row
            var $total = navigation.find('li').length;
            $width = 100/$total;
            $display_width = $(document).width();

            if($display_width < 600 && $total > 3){
                $width = 50;
            }
            navigation.find('li').css('width',$width + '%');
        },
        onNext: function(tab, navigation, index){
            if (index == 1){
                if ($('#install_action').val() == null) {
                    bootbox.alert("Install Action has not been specified.");
                    return false;
                }
            }
        },
        onTabClick : function(tab, navigation, index){
            // Disable the possibility to click on tabs
            return false;
        },
        onTabShow: function(tab, navigation, index) {
            var $total = navigation.find('li').length;
            var $current = index+1;

            var wizard = navigation.closest('.wizard-card');

            // If it's the last tab then hide the last button and show the finish instead
            if($current >= $total) {
                $(wizard).find('.btn-next').hide();
                $(wizard).find('.btn-finish').show();
            } else {
                $(wizard).find('.btn-next').show();
                $(wizard).find('.btn-finish').hide();
            }
        }
    });

    $('#on-finish-submit').on('click', function(e) {
        // Only Install Add requires a server repository
        if ($('#select_server').val() == -1 &&
            has_one_of_these($('#install_action').val(), ['Install Add'])) {

            bootbox.alert('Server repository has not been specified.');
            return false;
        }

        var software_packages = $('#software_packages').val().trim();
        if (!validate_package_count_restriction(host_software_platform, host_software_version, software_packages)) {
            return false;
        }

        on_submit_install_jobs();

        return false;
    });

    function on_submit_install_jobs() {
        var hostname = $('#make-conform-dialog').data('hostname');
        var cco_lookup_enabled = $('#make-conform-dialog').data('cco-lookup-enabled') == 'True';

        var validate_object = {
            form: null,
            hostname: hostname,
            server_id: $('#select_server').val(),
            server_directory: $('#select_server_directory').val(),
            software_packages: $('#software_packages').val(),
            spinner: make_conform_dialog_spinner,
            install_actions: $('#install_action').val(),
            check_missing_file_on_server: $('#select_server').val() > -1,
            callback: submit_install_jobs,
            pending_downloads: null,
            cco_lookup_enabled: cco_lookup_enabled
        };

        if (has_one_of_these($('#install_action').val(), ['Install Add'])) {
            on_validate_prerequisites_and_files_on_server(validate_object);
        } else if (has_one_of_these($('#install_action').val(), ['Activate'])) {
            // Check for packages that may cause router to reload during Activate.
            // Turn off check_missing_file_on_server as it is only used for
            // Install Add.
            validate_object.check_missing_file_on_server = false;
            check_need_reload(validate_object);

        } else {
            submit_install_jobs(validate_object);
        }
    }

    function submit_install_jobs(validate_object) {
        if (use_utc_timezone) {
            $('#scheduled-time-UTC').val($('#scheduled-time').val());
        } else {
            $('#scheduled-time-UTC').val(convertToUTCString($('#scheduled-time').val()));
        }

        // Update the software packages textarea
        $('#software_packages').val(validate_object.software_packages);

        var hostname = $('#make-conform-dialog').data('hostname');
        var install_action = $('#install_action').val();

        if ($('#custom_command_profile').val() != null) {
            var custom_command_string = $('#custom_command_profile').val().join(",");
        } else {
            var custom_command_string = $('#custom_command_profile').val();
        }

        $.ajax({
            url: "/conformance/api/create_install_jobs",
            dataType: 'json',
            type: "POST",
            data: {
                hostname: hostname,
                install_action: install_action,
                scheduled_time_UTC: $('#scheduled-time-UTC').val(),
                software_packages: trim_lines($('#software_packages').val()),
                server: $('#select_server').val(),
                server_directory: $('#select_server_directory').val(),
                pending_downloads: validate_object.pending_downloads,
                custom_command_profile: custom_command_string
            },
            success: function(data) {
                if (data.status == 'OK') {
                    if (install_action.length == 1) {
                        bootbox.alert('The request scheduled installation has been submitted for ' + hostname + '.');
                    } else {
                        bootbox.alert('The request scheduled installations have been submitted for ' + hostname + '.');
                    }
                    $('#make-conform-dialog').modal('hide');
                } else {
                    bootbox.alert('<img src="/static/error.png">&nbsp;ERROR: Unable to schedule installation.  ' + data.status);
                }
            }
        });
    }

});

function display_make_conform_dialog(hostname, software_platform, software_version, missing_packages) {
    host_software_platform  = software_platform;
    host_software_version = software_version;

    // Reset variables
    $("#install_action").val(null).trigger("change");
    $('#select_server').val(-1);
    $('#select_server_directory').val('');

    $('#make-conform-dialog').data('hostname', hostname)
    $('#make-conform-dialog-title').html(hostname);
    $('#software_packages').val(comma2newline(missing_packages));

    // Initialize the server repository selector
    initialize_server_by_hostname(hostname);

    // Go to the first page especially when the dialog is re-used.
    $('a[href="#dialog_general"]').tab('show');

    $('#make-conform-dialog').modal({
        show: true,
        backdrop: 'static'
    });
}