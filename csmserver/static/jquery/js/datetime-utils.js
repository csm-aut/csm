
function getToday()
{
    var today = new Date();    
    return formatMMDDYYYY(today.getFullYear(), today.getMonth(), today.getDate()) + ' ' + formatAMPM(today.getHours(), today.getMinutes());   
}

function compareDateString(datetime1, datetime2)
{
    var date1 = new Date(datetime1);
    var date2 = new Date(datetime2);
    
    return (date1 - date2);
}

/**
 * Given a locale date string (06/12/2014 8:37:48 PM), 
 * return the UTC date string in the same format.
 **/
function convertToUTCString(dateString) 
{
    if (dateString == null) return dateString;
    
    var localeDate = new Date(dateString);
    return formatMMDDYYYY(localeDate.getUTCFullYear(), localeDate.getUTCMonth(), localeDate.getUTCDate()) + ' ' + formatAMPM(localeDate.getUTCHours(), localeDate.getUTCMinutes());
}

/**
 * Given a UTC date string, return either a pretty UTC string or
 * convert the date string to locale date string
 **/
function getDateStringfromUTCString(dateString, use_utc_timezone)
{
    if (use_utc_timezone) {
        return getPrettyUTCString(dateString);
    } else {
        return convertToLocaleString(dateString);
    }
}

/**
 * Given a UTC date string, return a prettier display.
 **/
function getPrettyUTCString(dateString)
{
    if (dateString == null) return dateString;

    var utcDate = '';
    // If the date suffix is not GMT, indicate it is a GMT (a.k.a UTC) time.
    if (dateString.indexOf('GMT') == -1) {
        utcDate = new Date(dateString + ' UTC');
    } else {
        utcDate = new Date(dateString);
    }
    return formatMMDDYYYY(utcDate.getUTCFullYear(), utcDate.getUTCMonth(), utcDate.getUTCDate()) + ' ' + formatAMPM(utcDate.getUTCHours(), utcDate.getUTCMinutes()) + ' UTC';
}


/**
 * Given a date string in UTC format (06/12/2014 8:37:48 PM) or (06/12/2014 8:37:48 PM GMT), 
 * return the Locale date string in the same format.
 **/
function convertToLocaleString(dateString) 
{
    if (dateString == null) return dateString;
    
    var utcDate = '';
    // If the date suffix is not GMT, indicate it is a GMT (a.k.a UTC) time.
    if (dateString.indexOf('GMT') == -1) {
        utcDate = new Date(dateString + ' UTC');    
    } else {
        utcDate = new Date(dateString); 
    } 
    return formatMMDDYYYY(utcDate.getFullYear(), utcDate.getMonth(), utcDate.getDate()) + ' ' + formatAMPM(utcDate.getHours(), utcDate.getMinutes());   
}

function formatMMDDYYYY(year, month, date) 
{
    var yyyy = year.toString();                                   
    var mm = (month + 1).toString(); // getMonth() is zero-based         
    var dd  = date.toString();             
    return (mm[1] ? mm : "0" + mm[0]) + '/' + (dd[1] ? dd : "0" + dd[0])  + '/' + yyyy;
}

function formatAMPM(hours, minutes) 
{
    var ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12; // the hour '0' should be '12'
    hours = hours < 10 ? '0'+ hours : hours;
    minutes = minutes < 10 ? '0'+ minutes : minutes;
    var strTime = hours + ':' + minutes + ' ' + ampm;
    return strTime;
}

