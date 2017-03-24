var optimized_list;

function optimize_software(src_control, target_control, spinner) {
    if (spinner) { spinner.show() };

    $.ajax({
        url: "/cco/api/optimize_software",
        dataType: 'json',
        data: { smu_list: src_control.val() },
        success: function(data) {
            var lines = '';
            $.each(data, function(index, element) {
                optimized_list = element;

                for (i = 0; i < element.length; i++) {
                    var smu_entry = element[i].smu_entry;
                    var is = element[i].is;
                            
                    if (is == 'Pre-requisite') {
                        is = 'A Missing ' + is;
                    }

                    var description = (element[i].description.length > 0) ? ' - ' + element[i].description : ''
                    lines += smu_entry + ' (' + is + ')' + description + '<br>';
                }
            });

            if (lines) {
                display_optimized_dialog(lines, target_control);
            }
            
            if (spinner) { spinner.hide(); }
        },
        error: function(XMLHttpRequest, textStatus, errorThrown) {
            if (spinner) { spinner.hide(); }
        }
    });
}

function display_optimized_dialog(lines, target_control) {

    bootbox.dialog({
        message: lines,
        title: "Click 'Accept' to include all missing pre-requisites and remove all superseded packages, if any.<br>" +
            "Click 'Accept (Remove Unrecognized)' to remove entries marked as Unrecognized, if any. <br>" +
            "Entries classified as SMU/SP/Package will be included automatically.",
        buttons: {       
            success: {
                label: "Accept",
                className: "btn-success",
                callback: function() {
                    accept_optimized_list(false, target_control);
                }
            },
            primary: {
                label: "Accept (Remove Unrecognized)",
                className: "btn-primary",
                callback: function() {
                    accept_optimized_list(true, target_control);
                }
            },
            main: {
                label: "Cancel",
                className: "btn-default",
            }
        }
    });

}

function accept_optimized_list(exclude_unrecognized, target_control) {
    var result_list = [];

    for (i = 0; i < optimized_list.length; i++) {
        var entry = optimized_list[i].smu_entry;
        var is = optimized_list[i].is;

        if (is.indexOf('Pre-requisite') >= 0) {
            result_list.push(entry);
        } else if (is.indexOf('Superseded') >= 0 ||
            (exclude_unrecognized && is.indexOf('Unrecognized') >= 0)) {
            continue;
        } else {
            result_list.push(entry);
        }
    }

    target_control.val(convert_list_to_lines(result_list));
}