/**
 * This file requires a corresponding templates/shared/select_region_hosts.html.
 * The following js files must be included by the caller.
 *
 * <script src="/static/duallistbox/dist/dual-list-box.js"></script>
 */

var host_selector;

$(function() {

    $("#role").select2(/* {
        placeholder: 'Select Desirable Roles'
    } */);

    $("#software").select2( /* {
        placeholder: 'Select Desirable Software Versions'
    } */);

    host_selector = $('#host-selector').DualListBox();

    function populate_host_duallist(region_id, selected_role, selected_software) {

        $.ajax({
            url: "/api/get_hosts/region/" + region_id +
                "/role/" + (selected_role == null ? 'ALL' : selected_role) +
                "/software/" + (selected_software == null ? 'ALL' : selected_software),
            dataType: 'json',
            success: function(data) {

                var roles = []
                var platform_software = []
                $.each(data, function(index, element) {
                    for (i = 0; i < element.length; i++) {
                        available_hosts.push({
                            'id': element[i].hostname,
                            'name': element[i].hostname
                        });

                        // host_roles may contain comma delimited roles.
                        if (selected_role == null) {
                            var host_roles = element[i].roles;
                            if (host_roles != null && host_roles.length > 0) {
                                host_roles = host_roles.split(',');
                                for (var j = 0; j < host_roles.length; j++) {
                                    if ($.inArray(host_roles[j].trim(), roles) == -1) {
                                        roles.push(host_roles[j].trim());
                                    }
                                }
                            }
                        }

                        if (selected_software == null) {
                            if ($.inArray(element[i].platform_software, platform_software) == -1) {
                                platform_software.push(element[i].platform_software);
                            }
                        }
                    }
                });
                host_selector.initialize(available_hosts);

                // Populate the role selector with newly selected region.
                if (selected_role == null) {
                    $('#role').find('option').remove();
                    $('#role').append('<option value="ALL">ALL</option>');
                    for (var i = 0; i < roles.length; i++) {
                        $('#role').append('<option value="' + roles[i] + '">' + roles[i] + '</option>');
                    }
                }

                // Populate the software selector with newly selected region.
                if (selected_software == null) {
                    $('#software').find('option').remove();
                    $('#software').append('<option value="ALL">ALL</option>');
                    for (var i = 0; i < platform_software.length; i++) {
                        $('#software').append('<option value="' + platform_software[i] + '">' + platform_software[i] + '</option>');
                    }
                }
            }
        });
    }

    $('#role').on('change', function(e) {
        $('#software').select2('val','');
        populate_host_duallist($('#region option:selected').val(), $('#role').val(), null);
    });

    $('#software').on('change', function(e) {
        populate_host_duallist($('#region option:selected').val(), $('#role').val(), $('#software').val());
    });

    $('#region').on('change', function(e) {
        region_id = $('#region option:selected').val();

        if (region_id != -1) {
            $('#role').select2('val','');
            $('#software').select2('val','');
            populate_host_duallist(region_id, null, null);
        }
    });

});