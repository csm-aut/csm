/*!
 * jQuery twitter bootstrap wizard plugin
 * Examples and documentation at: http://github.com/VinceG/twitter-bootstrap-wizard
 * version 1.0
 * Requires jQuery v1.3.2 or later
 * Supports Bootstrap 2.2.x, 2.3.x, 3.0
 * Dual licensed under the MIT and GPL licenses:
 * http://www.opensource.org/licenses/mit-license.php
 * http://www.gnu.org/licenses/gpl.html
 * Authors: Vadim Vincent Gabriel (http://vadimg.com), Jason Gill (www.gilluminate.com)
 */
;(function($) {
var bootstrapWizardCreate = function(element, options) {
	var element = $(element);
	var obj = this;
	
	// selector skips any 'li' elements that do not contain a child with a tab data-toggle
	var baseItemSelector = 'li:has([data-toggle="tab"])';

	// Merge options with defaults
	var $settings = $.extend({}, $.fn.bootstrapWizard.defaults, options);
	var $activeTab = null;
	var $navigation = null;
	
	this.rebindClick = function(selector, fn)
	{
		selector.unbind('click', fn).bind('click', fn);
	}

	this.fixNavigationButtons = function() {
		// Get the current active tab
		if(!$activeTab.length) {
			// Select first one
			$navigation.find('a:first').tab('show');
			$activeTab = $navigation.find(baseItemSelector + ':first');
		}

		// See if we're currently in the first/last then disable the previous and last buttons
		$($settings.previousSelector, element).toggleClass('disabled', (obj.firstIndex() >= obj.currentIndex()));
		$($settings.nextSelector, element).toggleClass('disabled', (obj.currentIndex() >= obj.navigationLength()));

		// We are unbinding and rebinding to ensure single firing and no double-click errors
		obj.rebindClick($($settings.nextSelector, element), obj.next);
		obj.rebindClick($($settings.previousSelector, element), obj.previous);
		obj.rebindClick($($settings.lastSelector, element), obj.last);
		obj.rebindClick($($settings.firstSelector, element), obj.first);

		if($settings.onTabShow && typeof $settings.onTabShow === 'function' && $settings.onTabShow($activeTab, $navigation, obj.currentIndex())===false){
			return false;
		}
	};

	this.next = function(e) {

		// If we clicked the last then dont activate this
		if(element.hasClass('last')) {
			return false;
		}

		if($settings.onNext && typeof $settings.onNext === 'function' && $settings.onNext($activeTab, $navigation, obj.nextIndex())===false){
			return false;
		}

		/*if ($('.nav-tabs .active').text() == "Pre-Migrate") {
			if (server_software_selector.get_selected_items().length < 3) {
				bootbox.alert("Please select at least the eXR iso image, grub.efi and grub.cfg before continuing. The FPD SMU is also needed if your release version is below 6.0.0.")
				return false
			}
			$.cookie('region-' + region_id + '-server', $('#hidden_server').val(), { path: '/' });
        	$.cookie('region-' + region_id + '-server-directory', $('#hidden_server_directory').val(), { path: '/' });

		}
*/

		/*if ($('.nav-tabs .active').text() == "Select Host") {

			if (host_selector.get_selected_items().length < 1) {
				bootbox.alert("Please select at least one host.")
				return false
			}

			if ($('#region option:selected').val() == -1) {
				bootbox.alert("Region has not been specified.");
            	return false;
			} else  {
              var server = $.cookie('region-' + $('#region option:selected').val() + '-server');
              var server_directory = $.cookie('region-' + $('#region option:selected').val() + '-server-directory');

              $('#hidden_server').val(server == null ? -1 : server);
              $('#hidden_server_directory').val(server_directory == null ? '' : server_directory);
          }

		}*/

		// Did we click the last button
		$index = obj.nextIndex();
		if($index > obj.navigationLength()) {
		} else {
			$navigation.find(baseItemSelector + ':eq('+$index+') a').tab('show');
		}
		if ($('#wizard-dialog .nav-tabs .active').text() == "PRE-MIGRATE") {
			get_server_list()

		}

	};

	this.previous = function(e) {

		// If we clicked the first then dont activate this
		if(element.hasClass('first')) {
			return false;
		}

		if($settings.onPrevious && typeof $settings.onPrevious === 'function' && $settings.onPrevious($activeTab, $navigation, obj.previousIndex())===false){
			return false;
		}

		$index = obj.previousIndex();
		if($index < 0) {
		} else {
			$navigation.find(baseItemSelector + ':eq('+$index+') a').tab('show');
		}

	};

	this.first = function(e) {
		if($settings.onFirst && typeof $settings.onFirst === 'function' && $settings.onFirst($activeTab, $navigation, obj.firstIndex())===false){
			return false;
		}

		// If the element is disabled then we won't do anything
		if(element.hasClass('disabled')) {
			return false;
		}
		$navigation.find(baseItemSelector + ':eq(0) a').tab('show');

	};
	this.last = function(e) {
		if($settings.onLast && typeof $settings.onLast === 'function' && $settings.onLast($activeTab, $navigation, obj.lastIndex())===false){
			return false;
		}

		// If the element is disabled then we won't do anything
		if(element.hasClass('disabled')) {
			return false;
		}
		$navigation.find(baseItemSelector + ':eq('+obj.navigationLength()+') a').tab('show');
	};
	this.currentIndex = function() {
		return $navigation.find(baseItemSelector).index($activeTab);
	};
	this.firstIndex = function() {
		return 0;
	};
	this.lastIndex = function() {
		return obj.navigationLength();
	};
	this.getIndex = function(e) {
		return $navigation.find(baseItemSelector).index(e);
	};
	this.nextIndex = function() {
		return $navigation.find(baseItemSelector).index($activeTab) + 1;
	};
	this.previousIndex = function() {
		return $navigation.find(baseItemSelector).index($activeTab) - 1;
	};
	this.navigationLength = function() {
		return $navigation.find(baseItemSelector).length - 1;
	};
	this.activeTab = function() {
		return $activeTab;
	};
	this.nextTab = function() {
		return $navigation.find(baseItemSelector + ':eq('+(obj.currentIndex()+1)+')').length ? $navigation.find(baseItemSelector + ':eq('+(obj.currentIndex()+1)+')') : null;
	};
	this.previousTab = function() {
		if(obj.currentIndex() <= 0) {
			return null;
		}
		return $navigation.find(baseItemSelector + ':eq('+parseInt(obj.currentIndex()-1)+')');
	};
	this.show = function(index) {
		if (isNaN(index)) {
			return element.find(baseItemSelector + ' a[href=#' + index + ']').tab('show');
		}
		else {
			return element.find(baseItemSelector + ':eq(' + index + ') a').tab('show');
		}
	};
	this.disable = function(index) {
		$navigation.find(baseItemSelector + ':eq('+index+')').addClass('disabled');
	};
	this.enable = function(index) {
		$navigation.find(baseItemSelector + ':eq('+index+')').removeClass('disabled');
	};
	this.hide = function(index) {
		$navigation.find(baseItemSelector + ':eq('+index+')').hide();
	};
	this.display = function(index) {
		$navigation.find(baseItemSelector + ':eq('+index+')').show();
	};
	this.remove = function(args) {
		var $index = args[0];
		var $removeTabPane = typeof args[1] != 'undefined' ? args[1] : false;
		var $item = $navigation.find(baseItemSelector + ':eq('+$index+')');

		// Remove menu item
		$item.remove();
	};
	
	var innerTabClick = function (e) {
		// Get the index of the clicked tab
		var clickedIndex = $navigation.find(baseItemSelector).index($(e.currentTarget).parent(baseItemSelector));
		if($settings.onTabClick && typeof $settings.onTabClick === 'function' && $settings.onTabClick($activeTab, $navigation, obj.currentIndex(), clickedIndex)===false){
			return false;
		}
	};
	
	var innerTabShown = function (e) {  // use shown instead of show to help prevent double firing
		$element = $(e.target).parent();
		var nextTab = $navigation.find(baseItemSelector).index($element);

		// If it's disabled then do not change
		if($element.hasClass('disabled')) {
			return false;
		}

		if($settings.onTabChange && typeof $settings.onTabChange === 'function' && $settings.onTabChange($activeTab, $navigation, obj.currentIndex(), nextTab)===false){
				return false;
		}

		$activeTab = $element; // activated tab
		obj.fixNavigationButtons();
	};
	
	this.resetWizard = function() {
		
		// remove the existing handlers
		$('a[data-toggle="tab"]', $navigation).off('click', innerTabClick);
		$('a[data-toggle="tab"]', $navigation).off('shown shown.bs.tab', innerTabShown);
		
		// reset elements based on current state of the DOM
		$navigation = element.find('ul:first', element);
		$activeTab = $navigation.find(baseItemSelector + '.active', element);
		
		// re-add handlers
		$('a[data-toggle="tab"]', $navigation).on('click', innerTabClick);
		$('a[data-toggle="tab"]', $navigation).on('shown shown.bs.tab', innerTabShown);
		
		obj.fixNavigationButtons();

		$settings.onInit($activeTab, $navigation, 0);
	};

	$navigation = element.find('ul:first', element);
	$activeTab = $navigation.find(baseItemSelector + '.active', element);

	if(!$navigation.hasClass($settings.tabClass)) {
		$navigation.addClass($settings.tabClass);
	}

	// Load onInit
	if($settings.onInit && typeof $settings.onInit === 'function'){
		$settings.onInit($activeTab, $navigation, 0);
	}

	// Load onShow
	if($settings.onShow && typeof $settings.onShow === 'function'){
		$settings.onShow($activeTab, $navigation, obj.nextIndex());
	}

	$('a[data-toggle="tab"]', $navigation).on('click', innerTabClick);

	// attach to both shown and shown.bs.tab to support Bootstrap versions 2.3.2 and 3.0.0
	$('a[data-toggle="tab"]', $navigation).on('shown shown.bs.tab', innerTabShown);
};
$.fn.bootstrapWizard = function(options) {
	//expose methods
	if (typeof options == 'string') {
		var args = Array.prototype.slice.call(arguments, 1)
		if(args.length === 1) {
			args.toString();
		}
		return this.data('bootstrapWizard')[options](args);
	}
	return this.each(function(index){
		var element = $(this);
		// Return early if this element already has a plugin instance
		if (element.data('bootstrapWizard')) return;
		// pass options to plugin constructor
		var wizard = new bootstrapWizardCreate(element, options);
		// Store plugin object in this element's data
		element.data('bootstrapWizard', wizard);
		// and then trigger initial change
		wizard.fixNavigationButtons();
	});
};

// expose options
$.fn.bootstrapWizard.defaults = {
	tabClass:         'nav nav-pills',
	nextSelector:     '.wizard li.next',
	previousSelector: '.wizard li.previous',
	firstSelector:    '.wizard li.first',
	lastSelector:     '.wizard li.last',
	onShow:           null,
	onInit:           null,
	onNext:           null,
	onPrevious:       null,
	onLast:           null,
	onFirst:          null,
	onTabChange:      null, 
	onTabClick:       null,
	onTabShow:        null
};

})(jQuery);


function get_server_list() {

	if ($('#region').val() == null || $('#region option:selected').val() == -1) {
		var region_id = $('#hidden_region').val();
	} else {
		var region_id = $('#region option:selected').val();
	}
	  // Now, gets the servers for the selected region
  $('#server_dialog_server').empty().append('<option value=-1></option>');

  $.ajax({
	url: "/api/get_nonlocal_servers/region/" + region_id,
	dataType: 'json',
	success: function(data) {
	  $.each(data, function(index, element) {
		for (i = 0; i < element.length; i++) {
		  var server_id = element[i].server_id;
		  var hostname = element[i].hostname;

		  $('#server_dialog_server').append('<option value="' + server_id + '">' + hostname + '</option>');
		}
		var server_id = $('#hidden_server').val();
		var server_directory = $('#hidden_server_directory').val();
		if (server_id != -1) {
			$('#server_dialog_server').val(server_id);
			//server_software_retrieve_file_list(server_id, $('#server_dialog_server_directory'), server_directory);

		}
	  });
	},
	error: function(xhr, status, errorThrown) {
	  bootbox.alert("Unable to retrieve server list. Error=" + errorThrown);
	}
  });
}
