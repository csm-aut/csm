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

    var required_image_regex = "asr9k.*\.tar.*\\d\\.\\d\\.\\d.*";

    selector.select_partial_match([required_image_regex]);
    var selected_package_list = selector.get_selected_items();

    var found = false;
    for (i = 0; i < selected_package_list.length; i++) {
        if (selected_package_list[i].match(required_image_regex)) {
            found = true;
            break;
        }

    }

    if (found == false) {
        bootbox.alert("No ASR9K-64 tar file found. Please make sure that the filename of your ASR9K-64 tar file matches the wildcard expression 'asr9k*.tar*' and contains the suffix three digit ASR9K-64 software version number such as '6.1.1'.")
    }

}
