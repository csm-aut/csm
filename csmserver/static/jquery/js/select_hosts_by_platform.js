/**
 * This file requires a corresponding templates/shared/select_region_hosts.html.
 * The following js files must be included by the caller.
 *
 * <script src="/static/duallistbox/dist/dual-list-box.js"></script>
 */

var host_selector;

$(function() {

    $("#software").select2();
    $("#region").select2();
    $("#role").select2();

    host_selector = $('#host-selector').DualListBox();
    populate_host_platforms();

    function populate_host_platforms() {
        $('#platform').find('option').remove();
        $('#platform').append('<option value=""></option>');
        $.ajax({
            url: "/api/get_distinct_host_platforms",
            dataType: 'json',
            success: function(data) {
                $.each(data, function(index, element) {
                    for (i = 0; i < element.length; i++) {
                        var platform = element[i].platform;
                        $('#platform').append('<option value="' + platform + '">' + platform + '</option>');;
                    }
                });
            }
        });
    }

    function populate_host_software_versions(platform) {
        $('#software').find('option').remove();
        $('#software').append('<option value="ALL">ALL</option>');
        $.ajax({
            url: "/api/get_distinct_host_software_versions/platform/" + platform,
            dataType: 'json',
            success: function(data) {
                $.each(data, function(index, element) {
                    for (i = 0; i < element.length; i++) {
                        var software_version = element[i].software_version;
                        $('#software').append('<option value="' + software_version + '">' + software_version + '</option>');;
                    }
                });
            }
        });
    }

    function populate_host_regions(platform, software_versions) {
        $('#region').find('option').remove();
        $('#region').append('<option value="ALL">ALL</option>');
        $.ajax({
            url: "/api/get_distinct_host_regions/platform/" + platform +
                 "/software_versions/" + (software_versions == null ? 'ALL' : software_versions),
            dataType: 'json',
            success: function(data) {
                $.each(data, function(index, element) {
                    for (i = 0; i < element.length; i++) {
                        $('#region').append('<option value="' + element[i].region_id + '">' + element[i].region_name + '</option>');;
                    }
                });
            }
        });
    }

    function populate_host_roles(platform, software_versions, region_ids) {
        $('#role').find('option').remove();
        $('#role').append('<option value="ALL">ALL</option>');
        $.ajax({
            url: "/api/get_distinct_host_roles/platform/" + platform +
                 "/software_versions/" + (software_versions == null ? 'ALL' : software_versions) +
                 "/region_ids/" +  ((region_ids == null || region_ids == -1) ? 'ALL' : region_ids),
            dataType: 'json',
            success: function(data) {
                $.each(data, function(index, element) {
                    for (i = 0; i < element.length; i++) {
                        $('#role').append('<option value="' + element[i].role + '">' + element[i].role + '</option>');;
                    }
                });
            }
        });
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

    $('#region').on('change', function(e) {
        var platform = $('#platform option:selected').val();
        var software_versions = $('#software').val();
        var region_ids = $('#region').val();

        if (region_ids != null) {
            if ($('#role').val() != null) {
                $('#role').select2('val','');
            }
            populate_host_roles(platform, software_versions, region_ids);
        }
    });

    $('#software').on('change', function(e) {
        var platform = $('#platform option:selected').val();
        var software_versions = $('#software').val();

        if (software_versions != null) {
            if ($('#region').val() != null) {
                $('#region').select2('val','');
            }
            if ($('#role').val() != null) {
                $('#role').select2('val','');
            }
            populate_host_regions(platform, software_versions);
        }
    });

    $('#platform').on('change', function(e) {
        var platform = $('#platform option:selected').val();

        if (platform.length > 0) {
            // Remove the selections from Select2
            if ($('#software').val() != null) {
                $('#software').select2('val','');
            }
            if ($('#region').val() != null) {
                $('#region').select2('val','');
            }
            if ($('#role').val() != null) {
                $('#role').select2('val','');
            }
            populate_host_software_versions(platform);
        }
    });

});