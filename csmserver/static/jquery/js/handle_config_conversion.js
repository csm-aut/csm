/**
 * This file is for handle the config_conversion.html
 * The following js files must be included by the caller.
 *
 * <script src="/static/jquery/js/select_file_from_server.js"></script>
 */


function config_handler(input_filename, err_msg) {
    $('[data-toggle="tooltip"]').tooltip();
    var browse_spinner = $('#browse-spinner');
    var upload_spinner = $('#progress_upload');
    var progressSpan = $('#progress span');
    var upload_success = $('#upload_success');
    browse_spinner.hide();
    upload_spinner.hide();
    upload_success.hide();
    progressSpan.html('');

    $('[data-toggle="popover_upload"]').popover({
        trigger : 'click',
        placement : 'top',
        html : true,
        content : function() {
            return $('#popover_upload_config').html()
        }
    });


    var can_show_modal_directly = true;

    $('#hidden_submit_config_form').val('False');

    $(document).on('change', '.btn-file :file', function() {
        var input = $(this),
        numFiles = input.get(0).files ? input.get(0).files.length : 1,
        label = input.val().replace(/\\/g, '/').replace(/.*\//, '');
        input.trigger('fileselect', [numFiles, label]);
    });

    $('.btn-file :file').on('fileselect', function(event, numFiles, label) {
        can_show_modal_directly = false;
        var input = $(this).parents('.input-group').find(':text'),
        log = numFiles > 1 ? numFiles + ' files selected' : label;

        if( $('#selected_file_name').length ) {
            $('#selected_file_name').val(log);
        }
    });

    $('#select-server-move-up').on('click', function(e) {
        upload_success.hide();
    });

    $('#select_server').on('change', function(e) {
        upload_success.hide();
    });

    $('#select_server_directory').on('change', function(e) {
        upload_success.hide();
    });

    $('#select-server-reset-server-directory').on('click', function(e) {
        upload_success.hide();
    });


    function get_input_config() {

      $.ajax({
           url : "api/get_analysis",
           data : {filename : input_filename},
           dataType: "text",
           success : function (response) {
               document.getElementById('input_config').innerHTML = response;
               get_output_config();


           }
      });

    }
    function get_input_config_directly() {
      browse_spinner.show();
      progressSpan.html('Loading the files.');
      $.ajax({
           url : "api/get_file",
           data : {file_number : 1, filename : input_filename},
           dataType: "text",
           success : function (response) {
               document.getElementById('input_config').innerHTML = response;
               get_output_config();


           }
      });

    }
    function get_output_config() {
        $.ajax({
           url : "api/get_file",
           data : {file_number : 2, filename : input_filename},
           dataType: "text",
           success : function (data) {
                $.ajax({
                     url : "api/get_file",
                     data : {file_number : 3, filename : input_filename},
                     dataType: "text",
                     success : function (data2) {
                         document.getElementById('output_config').innerHTML = '<pre style="background-color:white;border:none;word-wrap:initial;">' + data + data2 + '</pre>';
                         browse_spinner.hide();
                         progressSpan.html('');
                         document.getElementById("filter_supported").checked = true;
                         document.getElementById("filter_unsupported").checked = true;
                         document.getElementById("filter_unprocessed").checked = true;
                         document.getElementById("filter_unrecognized").checked = true;
                         document.getElementById("filter_unimplemented").checked = true;
                         document.getElementById("filter_syntaxerrors").checked = true;

                         $('#config-output-dialog').modal({show: true, backdrop: 'static'});

                     }
                 });
           }
       });
    }

    function convert_config() {
        browse_spinner.show();
        $.ajax({
            url: "api/convert_config_file",
            dataType: 'json',
            data: {filename : input_filename},
            success: function(data) {
                if (data.status == 'OK') {
                    job_id = data.job_id;
                    update_progress(job_id);
                } else {
                    bootbox.alert('<img src="/static/error.png">&nbsp;Following errors were encountered: <br><br>' + comma2br(data.status));
                }
            },

            error: function(XMLHttpRequest, textStatus, errorThrown) {
                browse_spinner.hide();
                alert(errorThrown);
            }
        });
    }

    function update_progress(job_id){
        $.ajax({
            url: "api/get_config_conversion_progress",
            dataType: 'json',
            data: {
                job_id: job_id
            },
            success: function(data) {
                if(data.progress != "completed" && data.progress != "failed"){
                    if(data.progress != null){
                        progressSpan.html(data.progress);
                    }
                    setTimeout(function(){update_progress(job_id);}, 10000);
                } else if (data.progress == "failed"){
                      browse_spinner.hide();
                      progressSpan.html('');
                      $(window).unbind('beforeunload');
                      bootbox.alert("Configuration conversion has encountered an error and failed! Please check Tools > System Logs for more details.");
                } else {
                      progressSpan.html('Conversion completed. Loading the files.');
                      $(window).unbind('beforeunload');
                    get_input_config();

                }
            }
        });
    }

    function upload_config() {
        upload_spinner.show();
        upload_success.hide();
        $.ajax({
           url : "upload_config_to_server_repository",
           data : {server_id : $('#select_server').val(), server_directory : $('#select_server_directory').val(), filename : input_filename},
           dataType: "json",
           success : function (data) {
               upload_spinner.hide();
               if (data.status == 'OK') {
                    upload_success.show();
                } else {
                    bootbox.alert('<img src="/static/error.png">&nbsp;Following errors were encountered: <br><br>' + comma2br(data.status));
                }
           }
       });
    }

    if (input_filename) {
        $('#selected_file_name').val(input_filename);

        if (err_msg == null || err_msg == "") {
            convert_config();
        }
    }

    if (err_msg != null && err_msg != "") {
        bootbox.alert(err_msg);
        can_show_modal_directly = false;
        $('#selected_file_name').val("");
    }

    $('#convert').on('click', function (e) {
        if($('#selected_file_name').val() == ''){
            bootbox.alert("Please select a configuration file.");
            return false;
        }
        if (can_show_modal_directly) {
            get_input_config_directly();

            return false;
        }
        $('#hidden_submit_config_form').val('True');
        //return false;
        $('#form').submit();

    });

    $('#upload_config').on('click', function (e) {
        upload_config();
    });

    $('#filter_unprocessed').change(function() {
      checkbox_on_click(this, ".unprocessed");
    });
    $('#filter_supported').change(function() {
      checkbox_on_click(this, ".supported");
    });
    $('#filter_unsupported').change(function() {
      checkbox_on_click(this, ".unsupported");
    });
    $('#filter_unrecognized').change(function() {
      checkbox_on_click(this, ".unrecognized");
    });
    $('#filter_unimplemented').change(function() {
      checkbox_on_click(this, ".unimplemented");
    });
    $('#filter_syntaxerrors').change(function() {
      checkbox_on_click(this, ".syntaxerrors");
    });


    function checkbox_on_click(checkbox, element) {
        if ( $(checkbox).is(":checked")) {
          //not using jquery - $(element).show(); - because the number of elements is too large - maximum stack exceeded
          [].forEach.call(document.querySelectorAll(element), function (el) {
            el.style.display = 'block';
            });
        } else {
            // if not checked ...
          //not using jquery - $(element).hide(); - same reason
            [].forEach.call(document.querySelectorAll(element), function (el) {
            el.style.display = 'none';
            });
        }
    }

  }