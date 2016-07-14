/* 
 * The following js files must be included by the caller.
 *
 * <script src="/static/bootbox-4.2.0/js/bootbox.js"></script>
 * <script src="/static/duallistbox/dist/dual-list-box.js"></script>
 */

function auto_select_software(hostname, selector, target_release, match_internal_name) {     
    if (target_release.length == 0) {
        bootbox.alert('Target software release has not been specified.');
        return;
    }   
    
    var target_package_list = [];

    $.ajax({
        url: "/api/get_software_package_upgrade_list/hosts/" + hostname + "/release/" + target_release,
        dataType: 'json',
        data: { match_internal_name: match_internal_name} ,
        success: function(data) {
            $.each(data, function(index, element) {
                for (i = 0; i < element[0].packages.length; i++) {
                    target_package_list.push(element[0].packages[i]);
                }

        
                if (target_package_list.length > 0) {
                    selector.select_partial_match(target_package_list, element[0].is_regex);
                } else {
                    bootbox.alert("<img src='/static/error.png'> &nbsp;Unable to locate software packages that match the version.");
                }
            });
        
            var missing_package_list = [];
            var selected_package_list = selector.get_selected_items();
          
            for (i = 0; i < target_package_list.length; i++) {
                var target_package = target_package_list[i];
                var found = false;
                for (j = 0; j < selected_package_list.length; j++) {
                    var selected_package = selected_package_list[j];
                    if (selected_package.indexOf(target_package) > -1 || selected_package.match(".*" + target_package + ".*")) {
                        found = true;
                        break;
                    }
                }  
            
                if (!found) {
                    missing_package_list.push(target_package);
                }           
            }
          
            // print error list if any
            if (missing_package_list.length > 0) {
                var package_list = '';
                for (i = 0; i < missing_package_list.length; i++) {
                    package_list += missing_package_list[i] + '<br>';
                }
                bootbox.alert("<img src='/static/error.png'> &nbsp;Unable to locate software packages that match the following names<br><br>" + package_list);
            }
        }
    });
    
}