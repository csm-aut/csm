/*
 * The following js files must be included by the caller.
 *
 * <script src="/static/bootbox-4.2.0/js/bootbox.js"></script>
 * <script src="/static/duallistbox/dist/dual-list-box.js"></script>
 */

function auto_select_software(hostname, selector, target_release, match_internal_name) {

    if ($('#server_dialog_server').val() == -1) {
        bootbox.alert("Please select server repository.");
        return false
    }

    if (selector.get_unselected_items().length <= 0) {
        bootbox.alert("There is no available package to select from.");
        return false
    }

    required_packages = ["asr9k-mini-x64.iso"];

    selector.select_exact_match(required_packages);
    var selected_package_list = selector.get_selected_items();


    for (i = selected_package_list.length; i >= 0; i--) {

        var index = $.inArray(selected_package_list[i], required_packages);
        console.log("index = " + index);
        if (index > -1) {
            console.log("removing...");
            required_packages.splice(index, 1);
        }
    }

    if (required_packages.length > 0) {
        bootbox.alert("Auto Select cannot locate " + required_packages.toString() + ". Please select the equivalent of the file yourself. Please also select FPD SMU if the release version of current image is below 6.0.0.")
    }

}
