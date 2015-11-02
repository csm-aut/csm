searchVisible = 0;
transparent = true;

$(document).ready(function(){
    /*  Activate the tooltips      */
    $('[rel="tooltip"]').tooltip();
      
    $('.wizard-card').bootstrapWizard({
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
            if ($('.nav-tabs .active').text() == "Select Host") {
                return validateFirstStep();
            } else if ($('.nav-tabs .active').text() == "Pre-Migrate") {
                return validateSecondStep();
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

function validateFirstStep(){

    console.log("Validating first step: ");
    if (host_selector.get_selected_items().length < 1) {
        bootbox.alert("Please select at least one host.")
        return false
    }

    if ($('#region option:selected').val() == -1) {
        bootbox.alert("Region has not been specified.");
        return false;
    } else  {
      var server = $.cookie('region-' + $('#region option:selected').val() + '-server');
      var server_directory = $.cookie('region-' + $('#region option:selected').val() + '-server-directory');

      $('#hidden_server').val(server == null ? -1 : server);
      $('#hidden_server_directory').val(server_directory == null ? '' : server_directory);
    }


	return true;
}

function validateSecondStep(){
   
    //code here for second step
    console.log($('#server_dialog_server').val())
    if ($('#server_dialog_server').val() == -1) {
        bootbox.alert("Please select server repository");
        return false
    }
    var selected_ISO = false;
    var selected_items = server_software_selector.get_selected_items();

    for (var index in selected_items) {
        if (selected_items[index] == "asr9k-mini-x64.iso" || selected_items[index] == "asr9k-full-x64.iso") {
            selected_ISO = true;
        }
    }
    if (!selected_ISO) {
        bootbox.alert("Please select at least the eXR ISO image 'asr9k-mini-x64.iso' or 'asr9k-full-x64.iso' before continuing. The FPD SMU is also needed if your release version is below 6.0.0.");
        return false
    }
    $.cookie('region-' + region_id + '-server', $('#hidden_server').val(), { path: '/' });
    $.cookie('region-' + region_id + '-server-directory', $('#hidden_server_directory').val(), { path: '/' });


	return true;
    
}


 //Function to show image before upload

function readURL(input) {
    if (input.files && input.files[0]) {
        var reader = new FileReader();

        reader.onload = function (e) {
            $('#wizardPicturePreview').attr('src', e.target.result).fadeIn('slow');
        }
        reader.readAsDataURL(input.files[0]);
    }
}
    












