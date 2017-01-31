/**
 * This file requires a corresponding templates/shared/select_region_hosts.html.
 * The following js files must be included by the caller.
 *
 * <script src="/static/duallistbox/dist/dual-list-box.js"></script>
 */

var host_selector;

$(function() {

    var platform_ui = $('#platform');
    var software_ui = $("#software").select2();
    var region_ui = $("#region").select2();
    var role_ui = $("#role").select2();

    host_selector = $('#host-selector').DualListBox();

    populate_host_platforms(platform_ui);

    platform_ui.on('change', function(e) {
        if ($(this).val().length > 0) {
            initialize_select2(software_ui);
            initialize_select2(region_ui);
            initialize_select2(role_ui);
            populate_host_software_versions(platform_ui, software_ui);
        }
    });

    software_ui.on('change', function(e) {
        if ($(this).val() != null) {
            initialize_select2(region_ui);
            initialize_select2(role_ui);
            populate_host_regions(platform_ui, software_ui, region_ui);
        }
    });

    region_ui.on('change', function(e) {
        if ($(this).val() != null) {
            initialize_select2(role_ui);
            populate_host_roles(platform_ui, software_ui, region_ui, role_ui);
        }
    });

    function initialize_select2(select2_ui) {
        if (select2_ui.val() != null) {
            select2_ui.select2('val', '');
        }
    }

    $('#retrieve-hosts-by-platform').on('click', function(e) {
        // Avoid form submission
        e.preventDefault();

        var platform = $('#platform option:selected').val();
        if (platform.length == 0) {
            bootbox.alert('Platform has not been specified.');
            return;
        }
        populate_host_duallist(platform, $('#software').val(), $('#region').val(), $('#role').val())
    });

    function populate_host_duallist(platform, software_versions, region_ids, roles) {
        $.ajax({
            url: "/api/get_hosts/platform/" + platform +
                 "/software_versions/" + (software_versions == null ? 'ALL' : software_versions) +
                 "/region_ids/" + ((region_ids == null || region_ids == -1) ? 'ALL' : region_ids) +
                 "/roles/" + (roles == null ? 'ALL' : roles),
            dataType: 'json',
            success: function(data) {
                var available_hosts = []
                $.each(data, function(index, element) {
                    for (i = 0; i < element.length; i++) {
                        available_hosts.push({
                            'id': element[i].hostname,
                            'name': element[i].hostname
                        });
                    }
                });
                host_selector.initialize(available_hosts);
            }
        });
    }

});