jQuery(document).ready(function(){
  jQuery('#events thead').click(function(){
    $(this).closest('li').toggleClass('closed').toggleClass('open') });

  jQuery('#level').val(jQuery('#prev_level').val());
  jQuery('#count').val(jQuery('#prev_count').val());
});

