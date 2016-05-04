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

    required_iso_regex = ["asr9k.*\.iso.*"];

    selector.select_regex_match(["asr9k.*\.iso.*"]);
    var selected_package_list = selector.get_selected_items();

    var found = false;
    for (i = selected_package_list.length; i >= 0; i--) {

        if (selected_package_list[i].match(required_iso_regex[0])) {
            found = true;
            break;
        }

    }

    if (found == false) {
        bootbox.alert("Please make sure that the filename of your ASR9K-X64 image matches the wildcard expression 'asr9k*.iso*'.")
    }

}
