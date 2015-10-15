
var validated_list;

function validate_software(src_control, target_control, spinner) {
    if (spinner) { spinner.show() };

    $.ajax({
        url: "/api/validate_software",
        dataType: 'json',
        data: { smu_list: src_control.val() },
        success: function(data) {
            var lines = '';
            $.each(data, function(index, element) {
                validated_list = element;

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
                display_validated_dialog(lines, target_control);
            }
            
            if (spinner) { spinner.hide(); }
        },
        error: function(XMLHttpRequest, textStatus, errorThrown) {
            if (spinner) { spinner.hide(); }
        }
    });
}

function display_validated_dialog(lines, target_control) {

    bootbox.dialog({
        message: lines,
        title: "Click 'Accept' to include all missing pre-requisites, minus any supersedes if any.<br>" +
            "Click 'Accept excludes Unrecognized' to exclude entries marked as unrecognized if any.<br>" +
            "Entries classified as SMU/SP/Package will be included automatically.",
        buttons: {       
            success: {
                label: "Accept",
                className: "btn-success",
                callback: function() {
                    accept_validated_list(false, target_control);
                }
            },
            primary: {
                label: "Accept Excludes Unrecognized",
                className: "btn-primary",
                callback: function() {
                    accept_validated_list(true, target_control);
                }
            },
            main: {
                label: "Cancel",
                className: "btn-default",
            }
        }
    });

}

function accept_validated_list(exclude_unrecognized, target_control) {
    var result_list = [];

    for (i = 0; i < validated_list.length; i++) {
        var entry = validated_list[i].smu_entry;
        var is = validated_list[i].is;

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