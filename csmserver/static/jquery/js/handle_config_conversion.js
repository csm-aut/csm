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

        if( input.length ) {
            input.val(log);
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

    //$('input[type=file]').change(function(e){
    //    can_show_modal_directly = false;
    //    console.log($(this).val().split('\\'));
    //    $('#selected_file_name').text($(this).val().split('\\').pop());
    //});


    //var input_config_name = "{{ input_config }}";
    //var output_config_name = "{{ output_config }}";
    //var input_filename = "{{ input_filename }}";
    console.log(input_filename);

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
                //progressSpan.html('Job Submitted.');
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
                    console.log("still in progress");
                    if(data.progress != null){
                        progressSpan.html(data.progress);
                    }
                    setTimeout(function(){update_progress(job_id);}, 10000);
                } else if (data.progress == "failed"){
                    console.log("failed!");
                      browse_spinner.hide();
                      progressSpan.html('');
                      $(window).unbind('beforeunload');
                      bootbox.alert("Config conversion has encountered an error and failed!");
                } else {
                    console.log("completed!");
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
        var input = $('.btn-file :file').parents('.input-group').find(':text');
        input.val(input_filename);

        //$('#selected_file_name').text(input_filename);
        if (err_msg == null || err_msg == "") {
            convert_config();
            //get_input_config([]);
            //get_output_config();

            //$('#config-output-dialog').modal({show: true, backdrop: 'static'});
        }
    }

    if (err_msg != null && err_msg != "") {
        bootbox.alert(err_msg);
        can_show_modal_directly = false;
        var input = $('.btn-file :file').parents('.input-group').find(':text');
        input.val("");
        //$('#selected_file_name').text("");
    }

    $('#convert').on('click', function (e) {
        if($('.btn-file :file').val() == ''){
            bootbox.alert("Please select a configuration file.");
            return false;
        }

        //if ($('#selected_file_name').text() == null || $('#selected_file_name').text() == "") {
        //    bootbox.alert("Please select a configuration file.");
        //    return false;
        //}
        //$('#input-config-upload').attr("href", "{{ url_for('exr_migrate.upload_config_to_server_repository') }}?file_path=" + input_filename);
        if (can_show_modal_directly) {
            console.log("getting input html directly.");
            get_input_config_directly();

            return false;
        }
        console.log($('#hidden_submit_config_form').val());
        $('#hidden_submit_config_form').val('True');
        console.log($('#hidden_submit_config_form').val());
        //return false;
        $('#form').submit();

    });

    $('#upload_config').on('click', function (e) {
        upload_config();
    });

    $('#filter_unprocessed').change(function() {
      //element.trigger("custom_event");
        //var all = document.getElementsByClassName('unprocessed');
        //console.log(all);
        //myElements = document.querySelectorAll(".unprocessed");
        //console.log(myElements);
        //for (var i = 0; i < myElements.length; i++) {
        //    console.log(myElements[i].style);
        //    console.log(myElements[i].style.display);
        //    myElements[i].style.display = 'none';

        //}
        //for (element in myElements) {
        //    element.classList.add("hide_class");
            //console.log(element.style);
            //console.log(element.style.display);
            //element.style.display = 'hide';
        //}

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
          console.log("show!");
          //$(element).show();
          [].forEach.call(document.querySelectorAll(element), function (el) {
            el.style.display = 'block';
            });
        } else {
            // if not checked ...
          console.log("hide!");
          //$(element).hide();
            [].forEach.call(document.querySelectorAll(element), function (el) {
            el.style.display = 'none';
            });
        }
    }

  }