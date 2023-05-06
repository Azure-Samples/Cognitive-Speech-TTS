<?php
// Check that code was called from WordPress with
// uninstallation constant declared
if ( !defined( 'WP_UNINSTALL_PLUGIN' ) ) {
    exit;
   }
   // Check if options exist and delete them if present
   if ( false != get_option( 'msttsplayer_options' ) ) {
    delete_option( 'msttsplayer_options' );
   }