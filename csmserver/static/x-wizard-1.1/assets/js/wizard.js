searchVisible = 0;
transparent = true;

$(document).ready(function(){
    /*  Activate the tooltips      */
    $('[rel="tooltip"]').tooltip();
      
    $('.wizard-card').bootstrapWizard({
        'tabClass': 'nav nav-pills',
        'nextSelector': '.btn-next',
        'previousSelector': '.btn-previous',
        'lastSelector': '.btn-finish',
         
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
            if ($('.nav-tabs .active').text() == "Select Host") {
                return validateSelectHost();
            } else if ($('.nav-tabs .active').text() == "Pre-Migrate") {
                return validateSelectPackages();
            }

        },
        onTabClick : function(tab, navigation, index){
            // Disable the posibility to click on tabs
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

    // Prepare the preview for profile picture
    $("#wizard-picture").change(function(){
        readURL(this);
    });
    
    $('[data-toggle="wizard-radio"]').click(function(){
        wizard = $(this).closest('.wizard-card');
        wizard.find('[data-toggle="wizard-radio"]').removeClass('active');
        $(this).addClass('active');
        $(wizard).find('[type="radio"]').removeAttr('checked');
        $(this).find('[type="radio"]').attr('checked','true');
    });
    
    $('[data-toggle="wizard-checkbox"]').click(function(){
        if( $(this).hasClass('active')){
            $(this).removeClass('active');
            $(this).find('[type="checkbox"]').removeAttr('checked');
        } else {
            $(this).addClass('active');
            $(this).find('[type="checkbox"]').attr('checked','true');
        }
    });
    
    $height = $(document).height();
    $('.set-full-height').css('height',$height);
    
    
});

function validateSelectHost(){

    if (host_selector.get_selected_items().length < 1) {
        bootbox.alert("Please select at least one host.");
        return false
    }

    if ($('#region option:selected').val() == -1) {
        bootbox.alert("Region has not been specified.");
        return false
    } else if (has_one_of_these($("#install_action").val(), ['Pre-Migrate']))  {
      var server = $.cookie('region-' + $('#region option:selected').val() + '-server');
      var server_directory = $.cookie('region-' + $('#region option:selected').val() + '-server-directory');

      $('#hidden_server').val(server == null ? -1 : server);
      $('#hidden_server_directory').val(server_directory == null ? '' : server_directory);


        if (server != null && server != -1) {
            $('#server_dialog_server').val(server);
            server_software_retrieve_file_list(server, $('#server_dialog_server_directory'), server_directory);
        } else {
            server_software_selector.initialize([], []);
        }

    }

	return true
}

function validateSelectPackages(){

    //code here for second step
    if ($('#server_dialog_server').val() == -1) {
        bootbox.alert("Please select server repository");
        return false
    }
    var selected_image = 0;
    var selected_smu = 0;
    var selected_config = false;
    var selected_items = server_software_selector.get_selected_items();
    var unselected_items = server_software_selector.get_unselected_items();

    for (var index in selected_items) {
        if (selected_items[index].match("asr9k.*\.tar.*")) {
            selected_image++;
        }
        if (selected_items[index].match("asr9k.*\.pie.*")) {
            selected_smu++;
        }
        if ($('#config_filename').val() != "" && selected_items[index] == $('#config_filename').val()) {
            selected_config = true;
        }

    }
    if (selected_image < 1) {
        bootbox.alert("Please select the tar file containing ASR9K-X64 image and boot files before continuing.");
        return false
    } else if (selected_image > 1) {
        bootbox.alert("Please select only one tar file for ASR9K-X64 image and boot files before continuing.");
        return false
    }
    if (selected_smu < 1) {
        bootbox.alert("Please select the ASR9K unified FPD SMU for your ASR9K-X64 image before continuing.");
        return false
    }else if (selected_smu > 1) {
        bootbox.alert("Too many packages selected. Please select only the ASR9K-X64 image and the ASR9K unified FPD SMU before continuing.");
        return false
    }

    if ($('#config_filename').val() != "" && $('#config_filename').val() != null) {
        if (!selected_config) {
            for (var index in unselected_items) {
                if (unselected_items[index] == $('#config_filename').val()) {
                    selected_config = true;
                }
            }
        }
        if (!selected_config) {
            bootbox.alert("The config filename provided - '" + $('#config_filename').val() + "' - is not found in the 'Available Packages' column.");
            return false
        }

    }
    $('#hidden_server').val($('#server_dialog_server').val());
    $('#hidden_server_name').val($('#server_dialog_server option:selected').text());
    $('#hidden_server_directory').val($('#server_dialog_server_directory').val());

    region_id = $('#region option:selected').val();
    $.cookie('region-' + region_id + '-server', $('#hidden_server').val(), { path: '/' });
    $.cookie('region-' + region_id + '-server-directory', $('#hidden_server_directory').val(), { path: '/' });

	return true

}


 //Function to show image before upload

function readURL(input) {
    if (input.files && input.files[0]) {
        var reader = new FileReader();

        reader.onload = function (e) {
            $('#wizardPicturePreview').attr('src', e.target.result).fadeIn('slow');
        };
        reader.readAsDataURL(input.files[0]);
    }
}


