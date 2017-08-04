
function generate_plugin_detail_template(plugin_uid, plugin_name, plugin_to_user_input, plugin_to_required_data){

    var $plugin_detail_modal = $('#plugin-details-modal');
    $plugin_detail_modal.empty();
    console.log(plugin_to_user_input[plugin_uid]);

    var required_data_fields = plugin_to_required_data[plugin_name];

    return create_html_for_plugin_data_input(plugin_to_user_input[plugin_uid], required_data_fields);

}


function generate_input_field(label_name, label_width, field_value, field_width, enable_environment_vars) {
    var field_id = label_name.split(' ').join('_');
    var html = "";
    html += '<div class="form-group">' +
            '<label class="' + label_width + ' control-label" id="label_' + field_id + '">' + label_name + '</label>' +
            '<div class="' + field_width + '">' +
            '<input class="form-control" id="field_' + field_id + '" type="text" value="' + field_value + '">' +
            '</div>' +
            '</div>';
    return html;
}

function create_html_for_plugin_data_input(selected_plugin_data, required_data_fields) {
    var html = create_html_for_plugin_data_fields(required_data_fields, selected_plugin_data);
    html += '<div class="btn pull-right">' +
            '<button id="save-plugin-data" type="button" class="btn btn-primary">Save</button>' +
            '</div>';
    return html;
}


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