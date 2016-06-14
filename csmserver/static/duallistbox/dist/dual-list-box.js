/**
 * Modified to support CSM Server
 * Modified by: Alex Tang
 *
 * jQuery DualListBox plugin with Bootstrap styling v1.0
 * http://www.geodan.nl
 *
 * Copyright (c) 2014 Geodan B.V.
 * Created by: Alex van den Hoogen
 *
 * Usage:
 *   Create a <select> and apply this script to that select via jQuery like so:
 *   $('select').DualListBox(); - the DualListBox will than be created for you.
 *
 *   Options and parameters can be provided through html5 data-* attributes or
 *   via a provided JavaScript object. Optionally already selected items can
 *   also be provided and this script can download the JSON to fill the
 *   DualListBox when a valid URI is provided.
 *
 *   See the default parameters (below) for a complete list of options.
 */

(function($) {
    "use strict";
   
    /** Initializes the DualListBox code as jQuery plugin. */
    $.fn.DualListBox = function(paramOptions, selected) {
        return this.each(function () {
                 
            var defaults = { 
                element:    $(this).context,    // Select element which creates this dual list box.
                uri:        'local.json',       // JSON file that can be opened for the data.
                value:      'id',               // Value that is assigned to the value field in the option.
                text:       'name',             // Text that is assigned to the option field.
                title:      'Example',          // Title of the dual list box.
                json:       true,               // Whether to retrieve the data through JSON.
                timeout:    500,                // Timeout for when a filter search is started.
                horizontal: false,              // Whether to layout the dual list box as horizontal or vertical.
                textLength: 45,                 // Maximum text length that is displayed in the select.
                moveAllBtn: true,               // Whether the append all button is available.
                maxAllBtn:  3000,                // Maximum size of list in which the all button works without warning. See below.
                selectClass:'form-control',
                warning:    'Are you sure you want to move these many items? Doing so can cause your browser to become unresponsive.'
            };

            var htmlOptions = {
                element:    $(this).context,
                uri:        $(this).data('source'),
                value:      $(this).data('value'),
                text:       $(this).data('text'),
                title:      $(this).data('title'),
                json:       $(this).data('json'),
                timeout:    $(this).data('timeout'),
                horizontal: $(this).data('horizontal'),
                textLength: $(this).data('textLength'),
                moveAllBtn: $(this).data('moveAllBtn'),
                maxAllBtn:  $(this).data('maxAllBtn')
            };

            var plugin_options = $.extend({}, defaults, htmlOptions, paramOptions);

            $.each(plugin_options, function(i, item) {
                if (item === undefined || item === null) { throw 'DualListBox: ' + i + ' is undefined.'; }
            });

            plugin_options['parent'] = 'dual-list-box-' + plugin_options.title;
            plugin_options['parentElement'] = '#' + plugin_options.parent;
            selected = $.extend([{}], selected);

            if (plugin_options.json) {
                addElementsViaJSON(plugin_options, selected);
            } else {
                construct(plugin_options);
            }

            $(this).data('options', plugin_options);
            $(this).data('init_observers', []);
        }) 
    };

    $.fn.add_init_observer = function(observer) {
        var observers = $(this).data('init_observers');
        observers.push(observer);
    };

    $.fn.notify_init_observers = function(all_options) {
        var observers = $(this).data('init_observers');
        for (var i = 0; i < observers.length; i++) {
            observers[i](all_options)
        }
    };
    
    $.fn.get_selected_items = function() {                  
        var options = $(this).data('options');
        var selected_options = [];
        
        $(options.parentElement + ' .selected').find('option').each(function() {
          selected_options.push($(this).val());
        });
              
        return selected_options;
    };
    $.fn.get_unselected_items = function() {
        var options = $(this).data('options');

        var selected_options = [];

        $(options.parentElement + ' .unselected').find('option').each(function() {
          selected_options.push($(this).val());
        });

        return selected_options;
    };

    /** Retrieves all the option elements through a JSON request. */
    function addElementsViaJSON(options, selected) {
        var multipleTextFields = false;

        if (options.text.indexOf(':') > -1) {
            var textToUse = options.text.split(':');

            if (textToUse.length > 1) {
                multipleTextFields = true;
            }
        }

        $.getJSON(options.uri, function(json) {
            $.each(json, function(key, item) {
                var text = '';

                if (multipleTextFields) {
                    textToUse.forEach(function (entry) { text += item[entry] + ' '; });
                } else {
                    text = item[options.text];
                }

                $('<option>', {
                    value: item[options.value],
                    text: text,
                    selected: (selected.some(function (e) { return e[options.value] === item[options.value] }) === true)
                }).appendTo(options.element);
            });

            construct(options);
        });
    }
    
    function filtering(select, textBox) {
        var options = $(select).data('options');
        var search = $.trim($(textBox).val());
        var regex = new RegExp(search,'gi');
        
        $(select).empty();                  
        for (var key in options) {
            if (options[key].text.match(regex) != null)  {
                $('<option>', {
                    value: options[key].value,
                    text:  options[key].text,
                    selected: false
                }).appendTo($(select));                          
                
            }
        }    
    }
    
    function handle_move(src, dst, filter_selected) {
      var src_options = $(src).data('options');
      var dst_options = $(dst).data('options');
      
      var criteria = filter_selected ? ':selected' : '';
      src.find('option' + criteria).each(function(index) {
          dst_options[$(this).val()] = {value: $(this).val(), text: $(this).text()};
          delete src_options[$(this).val()];
      });
      
      $(src).data('options', src_options);
      $(dst).data('options', dst_options);        
    }
    
    /** Adds the event listeners to the buttons and filters. */
    function addListeners(options) {
        var unselected = $(options.parentElement + ' .unselected');
        var selected = $(options.parentElement + ' .selected');

        $(options.parentElement).find('button').bind('click', function() {
            switch ($(this).data('type')) {
                case 'str': /* Selected to the right. */
                    handle_move(unselected, selected, true);            
                    $(this).prop('disabled', true);
                    break;
                case 'atr': /* All to the right. */
                    if (unselected.find('option').length >= options.maxAllBtn && confirm(options.warning) ||
                        unselected.find('option').length < options.maxAllBtn) {
                        handle_move(unselected, selected, false); 
                    }
                    break;
                case 'stl': /* Selected to the left. */
                    handle_move(selected, unselected, true);
                    $(this).prop('disabled', true);
                    break;
                case 'atl': /* All to the left. */
                    if (selected.find('option').length >= options.maxAllBtn && confirm(options.warning) ||
                        selected.find('option').length < options.maxAllBtn) {
                        handle_move(selected, unselected, false);
                    }
                    break;
                default: break;
            }
        
            filtering(unselected, $.trim($(options.parentElement + ' .filter-unselected').val()) );
            filtering(selected, $.trim($(options.parentElement + ' .filter-selected').val()) );
      
            handleMovement(options);
        });

        $(options.parentElement).closest('form').submit(function() {
            selected.find('option').prop('selected', true);
        });

        $(options.parentElement).find('input[type="text"]').keypress(function(e) {
            if (e.which === 13) {
                event.preventDefault();
            }
        });
    }

    /** Constructs the jQuery plugin after the elements have been retrieved. */
    function construct(options) {
        createDualListBox(options);
        parseStubListBox(options);
        addListeners(options);
    }

    /** Counts the elements per list box/select and shows it. */
    function countElements(parentElement) {
        var countUnselected = 0, countSelected = 0;

        $(parentElement + ' .unselected').find('option').each(function() { if ($(this).isVisible()) { countUnselected++; } });
        $(parentElement + ' .selected').find('option').each(function() { if ($(this).isVisible()) { countSelected++ } });

        $(parentElement + ' .unselected-count').text(countUnselected);
        $(parentElement + ' .selected-count').text(countSelected);

        toggleButtons(parentElement); 
    }

    /** Creates a new dual list box with the right buttons and filter. */
    function createDualListBox(options) {
        $(options.element).parent().attr('id', options.parent);

        $(options.parentElement).addClass('row').append(
                (options.horizontal == false ? '   <div class="col-md-5">' : '   <div class="col-md-6">') +
                '       <h4><span class="unselected-title"></span> <small>- showing <span class="unselected-count"></span></small></h4>' +
                '       <input class="filter form-control filter-unselected" type="text" placeholder="Filter" style="margin-bottom: 5px;">' +
                (options.horizontal == false ? '' : createHorizontalButtons(1, options.moveAllBtn)) +
                '       <select class="unselected ' + options.selectClass + '" style="height: 180px; width: 100%;" multiple></select>' +
                '   </div>' +
                (options.horizontal == false ? createVerticalButtons(options.moveAllBtn) : '') +
                (options.horizontal == false ? '   <div class="col-md-5">' : '   <div class="col-md-6">') +
                '       <h4><span class="selected-title"></span> <small>- showing <span class="selected-count"></span></small></h4>' +
                '       <input class="filter form-control filter-selected" type="text" placeholder="Filter" style="margin-bottom: 5px;">' +
                (options.horizontal == false ? '' : createHorizontalButtons(2, options.moveAllBtn)) +
                '       <select class="selected ' + options.selectClass + '" style="height: 180px; width: 100%;" multiple></select>' +
                '   </div>');

        $(options.parentElement + ' .selected').prop('name', $(options.element).prop('name'));
        $(options.parentElement + ' .unselected-title').text('Available ' + options.title);
        $(options.parentElement + ' .selected-title').text('Selected ' + options.title);
    }

    /** Creates the buttons when the dual list box is set in horizontal mode. */
    function createHorizontalButtons(number, copyAllBtn) {
        if (number == 1) {
            return (copyAllBtn ? '       <button type="button" class="btn btn-default atr" data-type="atr" style="margin-bottom: 5px;"><span class="glyphicon glyphicon-list"></span> <span class="glyphicon glyphicon-chevron-right"></span></button>': '') +
                '       <button type="button" class="btn btn-default ' + (copyAllBtn ? 'pull-right col-md-6' : 'col-md-12') + ' str" data-type="str" style="margin-bottom: 5px;" disabled><span class="glyphicon glyphicon-chevron-right"></span></button>';
        } else {
            return '       <button type="button" class="btn btn-default ' + (copyAllBtn ? 'col-md-6' : 'col-md-12') + ' stl" data-type="stl" style="margin-bottom: 5px;" disabled><span class="glyphicon glyphicon-chevron-left"></span></button>' +
                (copyAllBtn ? '       <button type="button" class="btn btn-default col-md-6 pull-right atl" data-type="atl" style="margin-bottom: 5px;"><span class="glyphicon glyphicon-chevron-left"></span> <span class="glyphicon glyphicon-list"></span></button>' : '');
        }
    }

    /** Creates the buttons when the dual list box is set in vertical mode. */
    function createVerticalButtons(copyAllBtn) {
        return '   <div class="col-md-2 center-block" style="margin-top: ' + (copyAllBtn ? '80px' : '130px') +'">' +
            (copyAllBtn ? '       <button type="button" class="btn btn-default col-md-8 col-md-offset-2 atr" data-type="atr" style="margin-bottom: 10px;"><span class="glyphicon glyphicon-list"></span> <span class="glyphicon glyphicon-chevron-right"></span></button>' : '') +
            '       <button type="button" class="btn btn-default col-md-8 col-md-offset-2 str" data-type="str" style="margin-bottom: 20px;" disabled><span class="glyphicon glyphicon-chevron-right"></span></button>' +
            '       <button type="button" class="btn btn-default col-md-8 col-md-offset-2 stl" data-type="stl" style="margin-bottom: 10px;" disabled><span class="glyphicon glyphicon-chevron-left"></span></button>' +
            (copyAllBtn ? '       <button type="button" class="btn btn-default col-md-8 col-md-offset-2 atl" data-type="atl" style="margin-bottom: 10px;"><span class="glyphicon glyphicon-chevron-left"></span> <span class="glyphicon glyphicon-list"></span></button>' : '') +
            '   </div>';
    }

    /** Specifically handles the movement when one or more elements are moved. */
    function handleMovement(options) {
        $(options.parentElement + ' .unselected').find('option:selected').prop('selected', false);
        $(options.parentElement + ' .selected').find('option:selected').prop('selected', false);

        //$(options.parentElement + ' .filter').val('');
        //$(options.parentElement + ' select').find('option').each(function() { $(this).show(); });

        countElements(options.parentElement);
    }

    /** Parses the stub select / list box that is first created. */
    function parseStubListBox(options) {
        var textIsTooLong = false;

        $(options.element).find('option').text(function (i, text) {
            $(this).data('title', text);

            if (text.length > options.textLength) {
                textIsTooLong = true;
                return text.substr(0, options.textLength) + '...';
            }
        }).each(function () {
            if (textIsTooLong) {
                $(this).prop('title', $(this).data('title'));
            }

            if ($(this).is(':selected')) {
                $(this).appendTo(options.parentElement + ' .selected');
            } else {
                $(this).appendTo(options.parentElement + ' .unselected');
            }
        });

        $(options.element).remove();
        handleMovement(options);
    }

    /** Toggles the buttons based on the length of the selects. */
    function toggleButtons(parentElement) {
        $(parentElement + ' .unselected').change(function() {
            $(parentElement + ' .str').prop('disabled', false);
        });

        $(parentElement + ' .selected').change(function() {
            $(parentElement + ' .stl').prop('disabled', false);
        });

        if ($(parentElement + ' .unselected').has('option').length == 0) {
            $(parentElement + ' .atr').prop('disabled', true);
            $(parentElement + ' .str').prop('disabled', true);
        } else {
            $(parentElement + ' .atr').prop('disabled', false);
        }

        if ($(parentElement + ' .selected').has('option').length == 0) {
            $(parentElement + ' .atl').prop('disabled', true);
            $(parentElement + ' .stl').prop('disabled', true);
        } else {
            $(parentElement + ' .atl').prop('disabled', false);
        }
    }

    /**
     * Filters through the select boxes and hides when an element doesn't match.
     *
     * Original source: http://www.lessanvaezi.com/filter-select-list-options/
     */
    /*
    $.fn.filterByText = function(textBox, timeout, parentElement) {
        return this.each(function() {
            var select = this;
            var options = [];

            $(select).find('option').each(function() {
                options.push({value: $(this).val(), text: $(this).text()});
            });

            $(select).data('options', options);

            $(textBox).bind('change keyup', function() {
                delay(function() {
                    var options = $(select).data('options');
                    var search = $.trim($(textBox).val());
                    var regex = new RegExp(search,'gi');

                    $.each(options, function(i) {
                        if(options[i].text.match(regex) === null) {
                            $(select).find($('option[value="' + options[i].value + '"]')).hide();
                        } else {
                            $(select).find($('option[value="' + options[i].value + '"]')).show();
                        }
                    });

                    countElements(parentElement);
                }, timeout);
            });
        });
    };
    */
    
    
    $.fn.select_partial_match = function(data_list, is_regex) {
      if (data_list.length == 0) {
        return;
      }

      var plugin_options = $(this).data('options');           
      var unselected = $(plugin_options.parentElement + ' .unselected');
      
      // remove all selected highlights
      unselected.find('option').each(function() {
          var found = false;

          if (is_regex == 0) {
              for (i = 0; i < data_list.length; i++) {
                  if ($(this).text().indexOf(data_list[i]) > -1) {
                      found = true;
                      break;
                  }
              }
          } else {
              for (i = 0; i < data_list.length; i++) {
                  if ($(this).text().match(".*" + data_list[i] + ".*")) {
                      found = true;
                      break;
                  }
              }
          }
        $(this).prop("selected", found);
      });
      
      $( ".str" ).click();
    }

    $.fn.select_regex_match = function(data_list) {
      if (data_list.length == 0) {
        return;
      }

      var plugin_options = $(this).data('options');
      var unselected = $(plugin_options.parentElement + ' .unselected');

      // remove all selected highlights
      unselected.find('option').each(function() {
        var found = false;

        for (i = 0; i < data_list.length; i++) {
          if ($(this).text().match(data_list[i])) {
            found = true;
            break;
          }
        }
        $(this).prop("selected", found);
      });

      $( ".str" ).click();
    }
    
    $.fn.set_title = function(title) {
      var plugin_options = $(this).data('options');               
      $(plugin_options.parentElement + ' .unselected-title').text('Available ' + title);
      $(plugin_options.parentElement + ' .selected-title').text('Selected ' + title);
    }
    
    /* array of dictionary data with value and text */
    $.fn.initialize = function(unselected_data, selected_data) {
        var plugin_options = $(this).data('options');           
        var unselected = $(plugin_options.parentElement + ' .unselected');
        var selected = $(plugin_options.parentElement + ' .selected');
        
        $(plugin_options.parentElement + ' .filter').val('');
        
        init(plugin_options, unselected.empty(), '.filter-unselected', unselected_data);
        init(plugin_options, selected.empty(), '.filter-selected', selected_data);

        countElements(plugin_options.parentElement);

        $(this).notify_init_observers(unselected_data);
    }
     
    function init(plugin_options, select, id, data) {
        var textbox = $(plugin_options.parentElement + ' ' + id);
            var cached_options = [];
         
        if (data != null) {
            $.each(data, function(i, item){
                $('<option>', {
                    value: item[plugin_options.value],
                    text:  item[plugin_options.text],
                    selected: false
                }).appendTo(select);
                
                cached_options[item[plugin_options.value]] = { value: item[plugin_options.value], text: item[plugin_options.text] };
            });
        }   
        
        $(select).data('options', cached_options);    
        
        $(textbox).bind('keyup', function() {
            delay(function() {

                var options = $(select).data('options');
                var search = $.trim($(textbox).val());
              
                filtering($(select), search);
                countElements(plugin_options.parentElement);
               
            }, plugin_options.timeout);
        });
    };
    
    function filtering(select, search) {
        var regex = new RegExp(search,'gi');
        var options = $(select).data('options');
        
        select.empty();       
        for (var key in options) {
          if(options[key].text.match(regex) != null) {
              $('<option>', {
                  value: options[key].value,
                  text:  options[key].text
              }).appendTo($(select));   
          }
        }
     
        $(select).scrollTop(0).sortOptions();
    }

    /** Checks whether or not an element is visible. The default jQuery implementation doesn't work. */
    $.fn.isVisible = function() {
        return !($(this).css('visibility') == 'hidden' || $(this).css('display') == 'none');
    };

    /** Sorts options in a select / list box. */
    $.fn.sortOptions = function() {
        return this.each(function() {
            $(this).append($(this).find('option').remove().sort(function(a, b) {
                var at = $(a).text(), bt = $(b).text();
                return (at > bt) ? 1 : ((at < bt) ? -1 : 0);
            }));
        });
    };

    /** Simple delay function that can wrap around an existing function and provides a callback. */
    var delay = (function() {
        var timer = 0;
        return function (callback, ms) {
            clearTimeout(timer);
            timer = setTimeout(callback, ms);
        };
    })();

})(jQuery);

