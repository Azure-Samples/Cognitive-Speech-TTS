<?php
/*
Plugin Name: Microsoft TTS Player
Plugin URI: https://aka.ms/tts-player
Description: Enable your website to support Text To Speech with player.
Version: 1.03
Author: Microsoft
Author URI: https://aka.ms/tts-player
License: GPLv2
*/

global $wp;

register_activation_hook(__FILE__, 'ttsplayer_set_default_options');

add_filter( 'the_content', 'insert_ttsplayer_ahead_and_warp_content_source' );

add_action( 'admin_menu', 'ttsplayer_settings_menu' );

add_action( 'wp_head', 'ttsplayer_script_output' );

add_action( 'admin_init', 'ttsplayer_admin_init' );

function get_ttsplayer_regions() {
    $regions = array(
        "local",
        "develop",
        "centraluseuap",

        "australiaeast",
        "brazilsouth",
        "canadacentral",
        "centralindia",
        "centralus",
        "chinaeast2",
        "eastasia",
        "eastus",
        "eastus2",
        "francecentral",
        "germanywestcentral",
        "japaneast",
        "japanwest",
        "jioindiawest",
        "koreacentral",
        "northcentralus",
        "northeurope",
        "norwayeast",
        "qatarcentral",
        "southafricanorth",
        "southeastasia",
        "southcentralus",
        "swedencentral",
        "switzerlandnorth",
        "switzerlandwest",
        "uaenorth",
        "uksouth",
        "westcentralus",
        "westeurope",
        "westus",
        "westus2",
        "westus3"
    );
    
    return $regions;
}

function query_cog_voice_list_short_names($region) {
    $url = get_cog_voice_list_api_uri($region);
    $request = wp_remote_get($url);
    if( is_wp_error( $request ) ) {
        return; // Bail early
    }
    
    $http_code = wp_remote_retrieve_response_code($request);
    if ($http_code != 200)
    {
        return;
    }

    $body = wp_remote_retrieve_body($request);
    $voices = json_decode($body);
    $voiceShortNames = array();
    foreach ($voices as $voice) {
        if ($voice->Status == 'GA' && $voice->VoiceType == 'Neural') {
            array_push($voiceShortNames,  $voice->ShortName);
        }
    }

    return $voiceShortNames;
}

function get_cog_voice_list_api_uri($region) {
    return 'https://' .
        get_cog_voice_list_api_host($region) .
         '/synthesize/list/cognitive-service/voices';
}

function get_cog_voice_list_api_host($region) {
    if (!isset($region)) {
        $region = '';
    }

    if ($region == 'local' || $region == 'develop') {
        // https://dev.tts.speech-test.microsoft.com/synthesize/list/cognitive-service/voices
        return 'dev.tts.speech-test.microsoft.com';
    } else if ($region == 'centraluseuap') {
        // https://centraluseuap.tts-frontend.speech.microsoft.com/synthesize/list/cognitive-service/voices
        return 'centraluseuap.tts-frontend.speech.microsoft.com';
    }

    // https://jioindiawest.tts-frontend.speech.microsoft.com/synthesize/list/cognitive-service/voices
    return $region . '.tts-frontend.speech.microsoft.com';
}

function get_ttsplayer_api_hostname($region){
    if (!isset($region)) {
        $region = '';
    }

    if ($region == 'local') {
        return 'localhost:44311';
    } elseif ($region == 'develop') {
        return 'develop.customvoice.api.speech-test.microsoft.com';
    } else if ($region == 'centraluseuap') {
        return 'centraluseuap.customvoice.api.speech.microsoft.com';
    }

    return $region . '.customvoice.api.speech.microsoft.com';
}

function ttsplayer_admin_init() {
    // Register a setting group with a validation
    // function so that post data handling is done
    // automatically for us
    register_setting(
        'ttsplayer_settings',
        'msttsplayer_options',
        'ttsplayer_validate_options');

    // Add a new settings section within the group
    add_settings_section(
        'ttsplayer_main_section',
        'Microsoft TTS Player Settings',
        'ttsplayer_main_setting_section_callback',
        'ttsplayer_settings_section');

    // Add each field with its name and function to
    // use for our new settings, put in new section
    add_settings_field(
        'ttsplayer_region',
        'TTS Player Region',
        'ttsplayer_display_select_list', 
        'ttsplayer_settings_section',
        'ttsplayer_main_section',
        array(
            'name' => 'ttsplayer_region',
            'choices' => get_ttsplayer_regions()));

    $options = ttsplayer_get_options();
    add_settings_field(
        'ttsplayer_voice_name',
        'TTS Voice Name',
        'ttsplayer_display_select_list',
        'ttsplayer_settings_section',
        'ttsplayer_main_section',
        array(
            'name' => 'ttsplayer_voice_name',
            'choices' => [
                '',
                ...query_cog_voice_list_short_names($options["ttsplayer_region"])]));

    add_settings_field(
        'ttsplayer_id',
        'TTS Player ID',
        'ttsplayer_display_text_field', 
        'ttsplayer_settings_section',
        'ttsplayer_main_section',
        array( 'name' => 'ttsplayer_id' ) );
}

function util_is_null_or_empty_string($value){
    return ($value === null || trim($value) === '');
}

function has_configured_ttsplayer($options){
    return isset($options) && !util_is_null_or_empty_string($options['ttsplayer_id']);
}

function ttsplayer_script_output() {
    $options = ttsplayer_get_options();
    if (!has_configured_ttsplayer($options)) {
        return;
    }
?>
    <script src="<?php echo esc_html(plugins_url('tts-player/tts-player.js', __FILE__)); ?>" type="text/javascript"></script>
    <link rel="stylesheet" type="text/css" href="<?php echo esc_html(plugins_url('tts-player/tts-player.css', __FILE__)); ?>" />
    <script>
    let ttsPlayerConfig = {
        playerId: "<?php echo esc_html($options['ttsplayer_id']); ?>",
        environment: "<?php echo esc_html(get_ttsplayer_api_hostname($options['ttsplayer_region'])); ?>",
        playerParentDivId: "MicrosoftTTSPlayerControlContainer",
        playerLibPath: "<?php echo esc_html(plugins_url('tts-player', __FILE__)); ?>"
    }

    window.onload = function (e) {
        ttsPlayer(
            {
                ttsPlayerConfig: ttsPlayerConfig,
                sourceLocation: "<?php echo esc_html(getSourceLocation()); ?>",
                voice: "<?php echo esc_html($options['ttsplayer_voice_name']); ?>",
                isFlat: true,
                xPaths: ["//div[contains(@class, 'MSTTSPlayerContentSource')]"],
                isLogging: true
            });
    }
    </script>
<?php 
}

function ttsplayer_settings_menu() {
    add_options_page(
        'Microsoft TTS Player Configuration',
        'Microsoft TTS Player',
        'manage_options',
        'ttsplayer_config', // This is the admin config page url.
        'ttsplayer_config_page');
}

function ttsplayer_config_page() { ?>
    <div id="ttsplayer-general" class="wrap">
        <h2>Microsoft TTS Player - Settings API</h2>
        <form name="ttsplayer_options_form_settings_api" method="post" action="options.php">
            <?php settings_fields('ttsplayer_settings'); ?>
            <?php do_settings_sections('ttsplayer_settings_section'); ?>
            <input type="submit" value="Submit" class="button-primary" />
        </form>
    </div>
   <?php
}

function ttsplayer_display_text_field($data = array()) {
    extract($data);
    $options = ttsplayer_get_options();
    ?>
    <input type="text" 
    size="36"
    name="msttsplayer_options[<?php echo
    esc_html($name); ?>]"
    value="<?php echo
    esc_html( $options[$name] ); ?>"/>
    <br />
   <?php
}

function ttsplayer_display_select_list($data = array()) {
    extract($data);
    $options = ttsplayer_get_options();
    ?>
    <select 
    name="msttsplayer_options[<?php 
    echo esc_html($name); ?>]">
    <?php foreach( $choices as $item ) { ?>
    <option value="<?php echo esc_html( $item ); ?>"
    <?php selected( $options[$name] == $item ); ?>>
    <?php echo esc_html( $item ); ?></option>;
    <?php } ?>
    </select>
   <?php
}

function ttsplayer_validate_options($input) {
    foreach (array('ttsplayer_id', 'ttsplayer_voice_name', 'ttsplayer_region') as $option_name) {
        if (isset($input[$option_name])) {
            $input[$option_name] = sanitize_text_field($input[$option_name]);
        }
    }

    return $input;
}

function ttsplayer_get_options() {
    $options = get_option('msttsplayer_options', array());

    $new_options['ttsplayer_region'] = 'eastus';
    $new_options['ttsplayer_id'] = '';
    $new_options['ttsplayer_voice_name'] ='en-US-JennyNeural';

    $merged_options = wp_parse_args($options, $new_options);
    $compare_options = array_diff_key($new_options, $options);

    if (empty($options) || !empty($compare_options)) {
        update_option('msttsplayer_options', $merged_options);
    }

    return $merged_options;
}

function ttsplayer_main_setting_section_callback() { ?>
    <p>This is the TTS player main configuration section.</p>
   <?php
}
   
function ttsplayer_set_default_options() {
    ttsplayer_get_options();
}

function insert_ttsplayer_ahead_and_warp_content_source ( $the_content ) {
    $options = get_option('msttsplayer_options', array());
    if (!has_configured_ttsplayer($options)) {
        return $the_content;
    }

    $new_content = '';
    $new_content .= '<div id="MicrosoftTTSPlayerControlContainer"></div>';
    $new_content .= '<div class="MSTTSPlayerContentSource">';
    $new_content .= $the_content;
    $new_content .= '</div>';
    return $new_content;
}

// cache_mode: OnlyCache, TryHitCache
// divClassNames split by comma.
function build_ttsplayer_url($cache_mode) {
    $options = ttsplayer_get_options();

    $apiHostName = get_ttsplayer_api_hostname($options['ttsplayer_region']);
    
    return "https://" .
        $apiHostName .
        "/api/texttospeech/v3.0-beta1/TTSWebPagePlayerSynthesis/synthesis-content?playerId=" .
        $options['ttsplayer_id'] .
        "&voice=" .
        $options['ttsplayer_voice_name'] .
        "&divClassNames=MSTTSPlayerContentSource&cacheMode=" .
        $cache_mode .
        "&sourceLocation=" .
        getSourceLocation();
}

function getSourceLocation() {
    $pageUrl = get_permalink();
    $siteUrl = site_url();
    $sourceLocation = "";
    if (substr($pageUrl, 0, strlen($siteUrl)) == $siteUrl) {
        $sourceLocation = substr($pageUrl, strlen($siteUrl) + 1);
    }

    return $sourceLocation;
}
