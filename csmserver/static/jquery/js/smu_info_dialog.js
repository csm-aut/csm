var current_history_pos = 0;
var smu_id_list = [];
var saved_smu_id = '';

function init_history(smu_id) {
    saved_smu_id = '';
    current_history_pos = 0;
    smu_id_list = [];
    smu_id_list.push(smu_id);
}

function add_to_history(smu_id) {
    if (saved_smu_id != smu_id) {
        saved_smu_id = smu_id;

        // Remove everything after the current location to the end
        for (var i = smu_id_list.length - 1; i > current_history_pos; i--) {
            smu_id_list.splice(i, 1);
        }

        smu_id_list.push(smu_id);
        current_history_pos++;
    }
}

function move_back(table, title) {
    if (--current_history_pos < 0) {
        current_history_pos = 0;
        return;
    }
    refresh(table, title, current_history_pos);
}

function move_forward(table, title) {
    if (++current_history_pos > smu_id_list.length - 1) {
        current_history_pos = smu_id_list.length - 1;
        return;
    }
    refresh(table, title, current_history_pos);
}

function refresh(table, title, pos) {
    if (pos >= 0 && pos < smu_id_list.length) {
        smu_id = smu_id_list[pos];
        display_smu_details(table, title, smu_id);
        saved_smu_id = smu_id;
    }
}

function setModalsAndBackdropsOrder() {
    var modalZIndex = 1040;
    $('.modal.in').each(function(index) {
        var $modal = $(this);
        modalZIndex++;
        $modal.css('zIndex', modalZIndex);
        $modal.next('.modal-backdrop.in').addClass('hidden').css('zIndex', modalZIndex - 1);
    });
    $('.modal.in:visible:last').focus().next('.modal-backdrop.in').removeClass('hidden');
}

/*
Allow the capability to stack model dialogs.
*/
$(document)
    .on('show.bs.modal', '.modal', function(event) {
        $(this).appendTo($('body'));
    })
    .on('shown.bs.modal', '.modal.in', function(event) {
        setModalsAndBackdropsOrder();
    })
    .on('hidden.bs.modal', '.modal', function(event) {
        setModalsAndBackdropsOrder();
    });

function display_smu_details(table, title, smu_id) {
    $.ajax({
        url: "/api/get_smu_details/smu_id/" + smu_id,
        dataType: 'json',
        success: function(data) {
            $.each(data, function(index, element) {
                if (element.length == 0) {
                    title.text('Unable to locate SMU ID: ' + smu_id)
                    table.html('');
                } else {
                    var html = '';
                    html += create_html_table_row('SMU ID', element[0].id);
                    html += create_html_table_row('SMU Name', element[0].name);
                    html += create_html_table_row('Posted Date', element[0].posted_date);
                    html += create_html_table_row('Type', element[0].type);
                    html += create_html_table_row('Impact', element[0].impact);
                    html += create_html_table_row('Functional Areas', element[0].functional_areas);
                    html += create_html_table_row('DDTS', element[0].ddts);
                    html += create_html_table_row('Description', element[0].description);
                    html += create_html_table_row('Status', element[0].status);
                    html += create_html_table_row('Compressed Image Size', element[0].compressed_image_size);
                    html += create_html_table_row('Uncompressed Image Size', element[0].uncompressed_image_size);
                    html += create_html_table_row('Package Bundles', element[0].package_bundles);
                    html += create_html_table_row('Constituent DDTS', element[0].composite_DDTS);
                    html += create_hyperlink_html_table_row('Pre-requisites', element[0].prerequisites_smu_ids, element[0].prerequisites);
                    html += create_hyperlink_html_table_row('Supersedes', element[0].supersedes_smu_ids, element[0].supersedes);
                    html += create_hyperlink_html_table_row('Superseded By', element[0].superseded_by_smu_ids, element[0].superseded_by);

                    title.text('SMU Name: ' + element[0].name);
                    table.html(html);
                }
            });
        }
    });
}

function display_ddts_details(table, title, ddts_id, ddts_spinner) {
    $.ajax({
        url: "/api/get_ddts_details/ddts_id/" + ddts_id,
        dataType: 'json',
        success: function(data) {
            var html = '';
            $.each(data, function(index, element) {
                html += create_html_table_row_with_commas('DDTS ID', element['bug_id']);
                html += create_html_table_row_with_commas('Headline', element['headline']);
                html += create_html_table_row_with_commas('Description', element['description']);
                html += create_html_table_row_with_commas('Last Modified', element['last_modified_date']);
                html += create_html_table_row_with_commas('Status', element['status']);
                html += create_html_table_row_with_commas('Severity', element['severity']);
                html += create_html_table_row_with_commas('Product', element['product']);
                html += create_html_table_row_with_commas('Known Affected Releases', element['known_affected_releases']);
                html += create_html_table_row_with_commas('Known Fixed Releases', element['known_fixed_releases']);
                html += create_html_table_row_with_commas('Support Cases', element['support_case_count']);
                html += create_html_table_row_with_commas('Error Description', element['ErrorDescription']);
                html += create_html_table_row_with_commas('Suggested Action', element['SuggestedAction']);
                html += create_html_table_row_with_commas('Error', element['ErrorMsg']);

                ddts_spinner.hide();
                title.text('DDTS ID: ' + ddts_id);
                table.html(html);
            });
        }
    });
}

function create_hyperlink_html_table_row(field, smu_id_list, smu_name_list) {
    var html_code = '';
    if (smu_id_list != null && smu_id_list.length > 0) {
        var smu_id_array = smu_id_list.split(',');
        var smu_name_array = smu_name_list.split(',');

        for (var i = 0; i < smu_id_array.length; i++) {
            var hyperlink = '<a class="show-smu-hyperlink-details" smu_id="' + smu_id_array[i] + '" href="javascript://">' + smu_name_array[i] + '</a>';
            if (i == 0) {
                html_code = '<tr><td>' + field + '</td><td>' + hyperlink + '</td></tr>';
            } else {
                html_code += '<tr><td>&nbsp;</td><td>' + hyperlink + '</td></tr>';
            }
        }
    } else {
        html_code = '<tr><td>' + field + '</td><td> None </td></tr>';
    }
    return html_code;
}