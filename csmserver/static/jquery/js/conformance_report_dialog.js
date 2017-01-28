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
    software_profile_selector = $('#software_profile');
    
    software_profile_selector.on('change', function(e) {
        saved_software_profile = software_profile_selector.val();
    });

    $('#conformance-report-dialog-wizard').bootstrapWizard({
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
                if (software_profile_selector.val() == 0) {
                    bootbox.alert("Software Profile has not been specified.");
                    return false;
                }
                var val = $("input[name=host_selection_criteria]:checked").val();
                if (val == 'auto') {
                    $('#manual-select-hosts-panel').hide();
                    $('#auto-select-hosts-panel').show();
                } else {
                    $('#auto-select-hosts-panel').hide();
                    $('#manual-select-hosts-panel').show();
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

function display_conformance_report_dialog() {
    // Go to the first page especially when the dialog is re-used.
    $('a[href="#dialog_software_profile"]').tab('show');

    // Initialize the software profiles

    $('#conformance-report-dialog').modal({
        show: true,
        backdrop: 'static'
    });
    
    populate_software_profiles(software_profile_selector, saved_software_profile);
}
