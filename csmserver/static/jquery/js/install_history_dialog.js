/**
 * This file requires a corresponding templates/share/install_history_dialog.html.
 * The following js files must be included by the caller.
 *
 * <script type="text/javascript" src="/static/jquery/js/common-utils.js"></script>
 */

var install_history_table;

$(function() {

     $('#install_history_dialog_host').on('change', function(e) {
         var selected_host = $('#install_history_dialog_host option:selected').val();
         if (selected_host.length > 0) {
             refresh_install_history(selected_host);
         } 
     }); 
    
     install_history_table = $("#install-history-datatable").dataTable({
         "order": [[ 2, "desc" ]],
         "scrollY": 250,
         "columnDefs": [ 
         {
             "sortable": false,
             "targets": 0, 
             "data" : 'packages',
             "render": function ( data, type, row ) {
                 return '<center><input type="checkbox" value="' + data + '" class="check"></center>';
             }
          },
          {
             "targets": 1, 
             "data" : 'packages',
             "render": function ( data, type, row ) {
                 return display_packages(data);
             }
          },
          {
             "targets": 2,
             "data" : 'status_time',
             "render": function ( data, type, row ) {
                 return convertToLocaleString(data);
             }
          },
          {
             "targets": 3,
             "data" : 'created_by'
          },
          ],
    });  
    
    function display_packages(packages) {
        if (packages) {
            return packages.replace(/,/g,"<br/>");
        } else {
            return '&nbsp;';
        }       
    }
   
});

function display_install_history_dialog(hostname_list) {
    initialize_install_history_dialog();

    $('#install-history-dialog').modal({show:true, backdrop:'static'})
    if (hostname_list.length == 1) {
        var hostname = hostname_list[0];
        
        $('<option>', {value: hostname, text: hostname, selected: true}).appendTo($('#install_history_dialog_host')); 
        refresh_install_history(hostname)
        
    } else {
        for (i = 0; i < hostname_list.length; i++) {
          $('<option>', {value: hostname_list[i], text: hostname_list[i]}).appendTo($('#install_history_dialog_host')); 
        }
    }
}

function initialize_install_history_dialog() {
    $('#install_history_dialog_host').empty();
    $('<option>', {value: '', text: ''}).appendTo($('#install_history_dialog_host')); 
    install_history_table.api().clear().draw();
}

function refresh_install_history(hostname) {
    install_history_table.api().ajax.url("/api/get_install_history/hosts/" + hostname).load();
}
    
    
    
