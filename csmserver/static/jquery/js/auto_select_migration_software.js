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

    required_packages_full = ["asr9k-full-x64.iso"];

    selector.select_exact_match(required_packages_full);
    var selected_package_list = selector.get_selected_items();


    for (i = selected_package_list.length; i >= 0; i--) {

        var index = $.inArray(selected_package_list[i], required_packages_full);
        if (index > -1) {
            required_packages_full.splice(index, 1);
        }
    }

    if (required_packages_full.length > 0) {

        required_packages_mini = ["asr9k-mini-x64.iso"];

        selector.select_exact_match(required_packages_mini);
        var selected_package_list = selector.get_selected_items();

        for (i = selected_package_list.length; i >= 0; i--) {

            var index = $.inArray(selected_package_list[i], required_packages_mini);
            if (index > -1) {
                required_packages_mini.splice(index, 1);
            }
        }
        if (required_packages_mini.length > 0) {

            bootbox.alert("Please make sure that the name of your ASR9K-X64 image is either '" + required_packages_full.toString() + "' or '" + required_packages_mini.toString() + "'. Auto Select cannot locate either of these.")

        }
    }

}
