
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
        html += create_html_table_row('Pre-requisites', element[0].prerequisites);
        html += create_html_table_row('Supersedes', element[0].supersedes);
        html += create_html_table_row('Superseded By', element[0].superseded_by);
                      
        title.text('SMU Name: ' + element[0].name);
        table.html(html); 
     
      });
    }
  });
}
