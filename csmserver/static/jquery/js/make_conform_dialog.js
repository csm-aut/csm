/**
 * This file requires a corresponding templates/conformance/make_conform_dialog.html.
 * The following js files must be included by the caller.
 *
 * <link rel="stylesheet" href="/static/datetimepicker/css/bootstrap-datetimepicker.min.css">
 * <script src="/static/datetimepicker/js/bootstrap-datetimepicker.min.js"></script>
 *
 * <script src="/static/jquery/js/select_server_dialog.js"></script>
 */

$(function() {
    var server_time_as_locale_time = convertToLocaleString($('#make-conform-dialog').attr('data-server-time'));

    $("#install_action").select2({});

    // Convert the UTC time to Locale time
    $('#scheduled-time-UTC').val(function(index, value) {
        if (value == 'None' || value.length == 0) {
            $('#scheduled-time').val(server_time_as_locale_time);
        } else {
            $('#scheduled-time').val(convertToLocaleString(value));
        }
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
            $("#install_action").val(['Pre-Upgrade', 'Install Add', 'Activate', 'Post-Upgrade', 'Commit']).trigger('change');
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

});

function display_make_conform_dialog(hostname, missing_packages) {
    $('#make-conform-dialog').data('data-hostname', hostname)
    $('#make-conform-dialog-title').html(hostname);
    $('#software_packages').val(comma2newline(missing_packages));

    initialize_server_by_hostname(hostname);

    $('#make-conform-dialog').modal({
        show: true,
        backdrop: 'static'
    });
}