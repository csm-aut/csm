
function generate_plugin_detail_template(plugin_uid, plugin_name, plugin_to_user_input){

    var $plugin_detail_modal = $('#plugin-details-modal');
    $plugin_detail_modal.empty();
    var html = "";
    console.log(plugin_to_user_input[plugin_uid]);
    if (plugin_name == "Script Executor") {
        html += create_html_for_script_executor_plugin(plugin_to_user_input[plugin_uid])
    } else if (plugin_name == "Custom Configuration") {
        html += create_html_for_custom_configuration_plugin(plugin_to_user_input[plugin_uid])
    }

    html += '<div class="btn pull-right">' +
            '<button id="save-plugin-data" type="button" class="btn btn-primary">Save</button>' +
            '</div>';
    return html;

    //return create_html_for_plugin_data_input(plugin_to_user_input[plugin_uid]);

}


function generate_input_field(label_name, label_width, field_value, field_width, allow_host_variables) {
    var field_id = label_name.split(' ').join('_');
    var html = '<div class="form-group">' +
               '<label class="' + label_width + ' control-label" id="label_' + field_id + '">' + label_name + '</label>' +
               '<div class="' + field_width + '">';
    if (allow_host_variables) {
        html += '<input class="form-control allow-host-variables" id="field_' + field_id + '" type="text" value="' + field_value + '">';
    } else {
        html += '<input class="form-control" id="field_' + field_id + '" type="text" value="' + field_value + '">';

    }

    html += '</div></div>';
    return html;
}

function generate_textarea_field(label_name, label_width, num_rows, num_cols, field_width, content) {
    var field_id = label_name.split(' ').join('_');
    var html = '<div class="form-group">' +
               '<label class="' + label_width + ' control-label" id="label_' + field_id + '">' + label_name + '</label>' +
               '<div class="' + field_width + '">' +
               '<textarea style="border: 1px solid #ccc;border-radius: 4px;" id="field_' + field_id + '" rows="' + num_rows + '" cols="' + num_cols + '">' + content + '</textarea>' +
               '</div>' +
               '</div>';
    return html;
}

function generate_radio_button_field(label_name, label_width, field_width, options, selected_value) {
    var field_id = label_name.split(' ').join('_');
    var html = '<div class="form-group">' +
               '<label class="' + label_width + ' control-label" id="label_' + field_id + '">' + label_name + '</label>' +
               '<div class="' + field_width + '" style="margin-top: 6px;">';
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


function create_html_for_plugin_data_input(selected_plugin_data) {
    var html = create_html_for_plugin_data_fields(selected_plugin_data);
    html += '<div class="btn pull-right">' +
            '<button id="save-plugin-data" type="button" class="btn btn-primary">Save</button>' +
            '</div>';
    return html;
}


function create_html_for_script_executor_plugin(selected_plugin_data) {
    var attribute_name="full_command",label_width="col-sm-2", field_width="col-sm-10";

    var value = get_value(selected_plugin_data, attribute_name, "");
    return generate_input_field(convert_attribute_name_to_field_label(attribute_name), label_width, value, field_width, true)
}

function create_html_for_custom_configuration_plugin(selected_plugin_data) {
    var attribute_name="configlet", value = "", label_width="col-sm-2", field_width="col-sm-10";

    var html = "";
    if (selected_plugin_data) {
        value = selected_plugin_data[attribute_name]
    }
    html += generate_textarea_field(convert_attribute_name_to_field_label(attribute_name), label_width, 20, 90, field_width, value);

    attribute_name="plane";
    value = get_value(selected_plugin_data, attribute_name, "sdr");
    var options=["admin", "sdr"];
    html += generate_radio_button_field(convert_attribute_name_to_field_label(attribute_name), label_width, field_width, options, value);

    attribute_name="description";
    value = get_value(selected_plugin_data, attribute_name, "");
    html += generate_input_field(convert_attribute_name_to_field_label(attribute_name), label_width, value, field_width, false);
    return html;
}

function get_value(selected_plugin_data, attribute_name, default_value) {
    if (selected_plugin_data) {
        return selected_plugin_data[attribute_name]
    }
    return default_value
}

/*
function create_html_for_plugin_data_fields(required_data_fields, selected_plugin_data){

    var label_width="col-sm-2", field_width="col-sm-10", enable_environment_vars = true;
    var html = "";
    var j;
    for(j=0;j<required_data_fields.length;j++){
        var field_label = convert_attribute_name_to_field_label(required_data_fields[j]);
        var field_value = get_input_value_for_field(field_label, selected_plugin_data);

        html += generate_input_field(field_label, label_width, field_value, field_width, enable_environment_vars);

    }
    return html;
}
*/
function get_input_value_for_field(label, selected_plugin_data) {
    if (selected_plugin_data) {
        var key = label.toLowerCase().replace(" ", "_");
        if (selected_plugin_data[key]) {
            return selected_plugin_data[key];
        }
    }
    return "";
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