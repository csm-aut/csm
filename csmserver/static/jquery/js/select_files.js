/**
 * This file requires that a selector elements be present with id="file-selector"
 * and id="sp-file-selector". Originally intended only for create tar file wizard (create_tar_file.html)
 *
 * The following js files must be included by the caller.
 *
 * <script src="/static/duallistbox/dist/dual-list-box.js"></script>
 */

var file_selector;
var sp_file_selector;

$(function() {
    file_selector = $('#file-selector').DualListBox();
    sp_file_selector = $('#sp-file-selector').DualListBox();

    function populate_tar_file_duallist() {

        $.ajax({
            url: "/tools/api/get_full_software_tar_files_from_csm_repository/",
            dataType: 'json',
            success: function(data) {
                available_files = []
                $.each(data, function(index, element) {
                    for (i = 0; i < element.length; i++) {
                        available_files.push({
                            'id': element[i]['image_name'],
                            'name': element[i]['image_name']
                        });
                    }
                });
                file_selector.initialize(available_files);
            }
        });
    }

    function populate_sp_file_duallist() {
        $.ajax({
            url: "/tools/api/get_sp_files_from_csm_repository/",
            dataType: 'json',
            success: function(data) {
                available_files = []
                $.each(data, function(index, element) {
                    for (i = 0; i < element.length; i++) {
                        available_files.push({
                            'id': element[i]['image_name'],
                            'name': element[i]['image_name']
                        });
                    }
                });
                sp_file_selector.initialize(available_files);
            }
        });
    }
    populate_tar_file_duallist();
    populate_sp_file_duallist();
});