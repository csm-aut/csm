
function generate_plugin_detail_template(plugin_data_specs, plugin_name, user_input, label_width, field_width){

    var $plugin_detail_modal = $('#plugin-details-modal');
    $plugin_detail_modal.empty();
    var html = "";

    html += create_html_for_plugin(plugin_name, plugin_data_specs, user_input, label_width, field_width);

    return html;


}


function generate_input_field(label_name, label_width, field_value, field_width, allow_host_variables) {
    var field_id = label_name.split(' ').join('_');
    var html = get_form_group_html(label_name, label_width, field_id, field_width, "");
    if (allow_host_variables) {
        html += '<input class="form-control allow-host-variables" id="field_' + field_id + '" type="text" value="' + field_value + '">';
    } else {
        html += '<input class="form-control" id="field_' + field_id + '" type="text" value="' + field_value + '">';

    }

    html += '</div></div>';
    return html;
}


function generate_textarea_field(label_name, label_width, num_rows, num_cols, content) {
    var field_width = "col-sm-6";
    var field_id = label_name.split(' ').join('_');
    var html = get_form_group_html(label_name, label_width, field_id, field_width, "") +
               '<textarea style="border: 1px solid #ccc;border-radius: 4px;" id="field_' + field_id + '" rows="' + num_rows + '" cols="' + num_cols + '">' + content + '</textarea>' +
               '</div>' +
               '</div>';
    return html;
}


function generate_radio_button_field(label_name, label_width, field_width, options, selected_value) {
    var field_id = label_name.split(' ').join('_');
    var html = get_form_group_html(label_name, label_width, field_id, field_width, "margin-top: 6px;");
    var i;
    for (i=0;i<options.length;i++) {
        if (options[i] == selected_value) {
            html += '<input type="radio" id="field_' + field_id + '" name="field_' + field_id + '" value="' + options[i] + '" style="margin-right: 10px" checked>' + options[i] + '&nbsp;&nbsp;&nbsp;&nbsp;';
        } else {
            html += '<input type="radio" id="field_' + field_id + '" name="field_' + field_id + '" value="' + options[i] + '" style="margin-right: 10px">' + options[i] + '&nbsp;&nbsp;&nbsp;&nbsp;';

        }
    }
    html += '</div></div>';
    return html;
}

function generate_checkbox_button_field(label_name, label_width, field_width, options, default_value) {
    var field_id = label_name.split(' ').join('_');
    var html = get_form_group_html(label_name, label_width, field_id, field_width, "margin-top: 6px;") +
               '<div class="btn-group" data-toggle="buttons" id="field_' + field_id + '">';
    if (default_value) {
        html += '<label class="btn btn-default">'+
                '<input type="radio" name="options" autocomplete="off" checked> Yes'+
                '</label>'+
                '<label class="btn btn-primary active">'+
                '<input type="radio" name="options" autocomplete="off"> No'+
                '</label>';
        //html += '<button type="button" class="btn btn-primary active" data-value="1">Yes</button>' +
          //      '<button type="button" class="btn btn-default" data-value="0">No</button>';
    } else {
        html += '<label class="btn btn-primary active">'+
                '<input type="radio" name="options" autocomplete="off" checked> Yes'+
                '</label>'+
                '<label class="btn btn-default">'+
                '<input type="radio" name="options" autocomplete="off"> No'+
                '</label>';
        //html += '<button type="button" class="btn btn-default" data-value="1">Yes</button>' +
          //      '<button type="button" class="btn btn-primary active" data-value="0">No</button>';
    }

    html += '</div></div>';

    return html;
}


function generate_toggle_button_field(label_name, label_width, field_width, options, default_value) {
    var field_id = label_name.split(' ').join('_');
    var html = get_form_group_html(label_name, label_width, field_id, field_width, "margin-top: 4px;");

    if (default_value) {
        html += '<label class="switch">' +
                '<input type="checkbox" id="field_' + field_id + '" checked>' +
                '<span class="slider round"></span>' +
                '</label>';
    } else {
        html += '<label class="switch">' +
                '<input type="checkbox" id="field_' + field_id + '">' +
                '<span class="slider round"></span>' +
                '</label>';
    }

    html += '</div></div>';

    return html;
}

function get_form_group_html(label_name, label_width, field_id, field_width, field_style) {
    return '<div class="form-group form-horizontal" style="display:block;margin-bottom:15px">' +
           '<label class="' + label_width + ' control-label" id="label_' + field_id + '">' + label_name + '</label>' +
           '<div class="' + field_width + '" style="' + field_style + '"> ';
}


function create_html_for_plugin(plugin_name, plugin_data_specs, selected_plugin_data, label_width, field_width) {
    if (!label_width) {
        label_width="col-sm-3";
    }
    if (!field_width) {
        field_width="col-sm-8";
    }
    var html = "";
    for (var i=0;i<plugin_data_specs.length;i++) {
        var data_specs = plugin_data_specs[i];
        var attribute_name = data_specs["attribute"];
        if (!attribute_name) {
            bootbox.alert("Error: Missing 'attribute' definition for plugin " + plugin_name);
            return '';
        }
        var default_value = "";
        if (data_specs["default_value"]) {
            default_value = data_specs["default_value"]
        }
        var value = get_value(selected_plugin_data, attribute_name, default_value);

        if (data_specs["ui_component"] == "toggle") {
            html += generate_toggle_button_field(convert_attribute_name_to_field_label(attribute_name), label_width, field_width, value);

        } else if (data_specs["ui_component"] == "textarea") {
            html += generate_textarea_field(convert_attribute_name_to_field_label(attribute_name), label_width, 20, 70, value);
        } else if (data_specs["ui_component"] == "text") {
            var allow_host_variables = false;
            if (data_specs["enable_env_var_input"] == true) {
                allow_host_variables = true;
            }
            html += generate_input_field(convert_attribute_name_to_field_label(attribute_name), label_width, value, field_width, allow_host_variables);
        } else if (data_specs["ui_component"] == "radio") {
            var options = data_specs["options"];
            if (!options || options.length < 1) {
                bootbox.alert("Error: Missing 'options' definition for attribute " + attribute_name + " in plugin " + plugin_name);
                return '';
            }
            html += generate_radio_button_field(convert_attribute_name_to_field_label(attribute_name), label_width, field_width, options, value);
        } else {
            bootbox.alert("Error: Unsupported ui_component " + data_specs["ui_component"] + " for attribute " + attribute_name + " in plugin " + plugin_name);
            return '';
        }


    }
    return html;
}


function get_value(selected_plugin_data, attribute_name, default_value) {
    if (selected_plugin_data) {
        return selected_plugin_data[attribute_name]
    }
    return default_value
}


function convert_attribute_name_to_field_label(attribute_name){
    var words = attribute_name.split("_");

    var field_label_words = [];

    for(var i = 0; i < words.length; i++) {
        field_label_words.push(words[i][0].toUpperCase() + words[i].substring(1, words[i].length));
    }

    return field_label_words.join(" ");

}


var host_variables = [

    {'label': "@host_ip"},
    {'label': "@host_port_number"},
    {'label': "@host_connection_type"},
    {'label': "@hostname"},
    {'label': "@host_chassis"},
    {'label': "@host_platform"},
    {'label': "@host_software_version"},
    {'label': "@host_region"},

];


function split( val ) {
  return val.split( / \s*/ );
}


function extractLast( term ) {
  return split( term ).pop();
}


function set_autocomplete_for_host_variables(selector) {

    selector
    // don't navigate away from the field on tab when selecting an item
        .bind("keydown", function (event) {
            if (event.keyCode === $.ui.keyCode.TAB &&
                $(this).autocomplete("instance").menu.active) {
                event.preventDefault();
            }
        })
        .autocomplete({
            minLength: 1,
            source: function (request, response) {
                // delegate back to autocomplete, but extract the last term
                var lastword = extractLast(request.term);
                // Regexp for filtering those labels that start with '@'
                var matcher = new RegExp("^" + $.ui.autocomplete.escapeRegex(lastword), "i");
                // Get all labels
                var labels = host_variables.map(function (item) {
                    return item.label;
                });
                var results = $.grep(labels, function (item) {
                    return matcher.test(item);
                });
                response($.ui.autocomplete.filter(
                    results, lastword));
            },
            focus: function () {
                // prevent value inserted on focus
                return false;
            },
            select: function (event, ui) {
                var terms = split(this.value);
                // remove the current input
                terms.pop();
                // add the selected item
                terms.push(ui.item.value);
                // add placeholder to get the comma-and-space at the end
                terms.push("");
                this.value = terms.join(" ");
                return false;
            }
        });
}