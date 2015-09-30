/**
 * This file requires a corresponding templates/shared/select_region_hosts.html.
 * The following js files must be included by the caller.
 *
 * <script src="/static/duallistbox/dist/dual-list-box.js"></script>
 */

var host_selector;
var selected_software_profile_name;

$(function() {
   
    host_selector = $('#host-selector').DualListBox();

    function populate_host_duallist(region_id, selected_role, selected_software) {

        $.ajax({
            url: "/api/get_hosts/region/" + region_id + "/role/" + selected_role + "/software/" + selected_software,
            dataType: 'json',
            success: function(data) {

                var roles = []
                var platform_software = []
                var available_hosts = []
                $.each(data, function(index, element) {
                    for (i = 0; i < element.length; i++) {
                        available_hosts.push({
                            'id': element[i].hostname,
                            'name': element[i].hostname
                        });

                        // host_roles may contain comma delimited roles.
                        if (selected_role == 'Any') {
                            var host_roles = element[i].roles;
                            if (host_roles != null) {
                                host_roles = host_roles.split(',');
                                for (var j = 0; j < host_roles.length; j++) {
                                    if ($.inArray(host_roles[j].trim(), roles) == -1) {
                                        roles.push(host_roles[j].trim());
                                    }
                                }
                            }
                        }

                        if (selected_software == 'Any') {
                            if ($.inArray(element[i].platform_software, platform_software) == -1) {
                                platform_software.push(element[i].platform_software);
                            }
                        }
                    }
                });

                host_selector.initialize(available_hosts);

                // Populate the role selector with newly selected region.
                if (selected_role == 'Any') {
                    $('#role').find('option').remove();
                    $('#role').append('<option value="Any">Any</option>');

                    for (var i = 0; i < roles.length; i++) {
                        $('#role').append('<option value="' + roles[i] + '">' + roles[i] + '</option>');
                    }
                }

                // Populate the software selector with newly selected region.
                if (selected_software == 'Any') {
                    $('#software').find('option').remove();
                    $('#software').append('<option value="Any">Any</option>');

                    for (var i = 0; i < platform_software.length; i++) {
                        $('#software').append('<option value="' + platform_software[i] + '">' + platform_software[i] + '</option>');
                    }
                }
            }
        });
    }

    $('#role').on('change', function(e) {
        populate_host_duallist($('#region option:selected').val(), $('#role option:selected').val(), $('#software option:selected').val());
    });

    $('#software').on('change', function(e) {
        populate_host_duallist($('#region option:selected').val(), $('#role option:selected').val(), $('#software option:selected').val());
    });

    $('#region').on('change', function(e) {
        region_id = $('#region option:selected').val();

        if (region_id != -1) {
            populate_host_duallist(region_id, 'Any', 'Any');
        }
    });

});