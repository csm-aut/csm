/**
 * This file requires a corresponding templates/conformance/conformance_report_dialog.html.
 * The following js files must be included by the caller.
 *
 * <script src="/static/bootbox-4.2.0/js/bootbox.js"></script>
 * <link href="http://netdna.bootstrapcdn.com/font-awesome/4.1.0/css/font-awesome.css" rel="stylesheet"> 
 * <link href="/static/x-wizard-1.1/assets/css/gsdk-base.css" rel="stylesheet" /> 
 * 
 * <!--  More information about jquery.validate here: http://jqueryvalidation.org/	 -->
 * <script src="/static/x-wizard-1.1/assets/js/wizard.js"></script>
 */
 
var software_profile_selector;
var saved_software_profile;
 
$(function() {
    software_profile_selector = $('#conformance_report_dialog_software_profile');
    
    software_profile_selector.on('change', function(e) {
        saved_software_profile = software_profile_selector.val();
    });
    
});

function display_conformance_report_dialog() {
    $('#conformance-report-dialog').modal({
        show: true,
        backdrop: 'static'
    });
    
    get_software_profiles();
}

function get_software_profiles() {
    software_profile_selector.empty().append('<option value=""></option>');
    
    $.ajax({
        url: "/conformance/api/get_software_profile_names",
        dataType: 'json',
        success: function(response) {
            $.each(response, function(index, element) {
                for (i = 0; i < element.length; i++) {
                    var software_profile = element[i].software_profile_name;
                    software_profile_selector.append('<option value="' + software_profile + '">' + software_profile + '</option>');
                }
            });
            
            if (saved_software_profile) {
                software_profile_selector.val(saved_software_profile);
            }
        }
    });
}