# TTS player

The TTS player is used for your website to support text to speech synthesis easily.

- Cache is supported automatically, only the first synthesis request of the article is requesting TTS service, for later request, will use the cached audio automatically.
- Minimize integration develop effort, you don't need write server side code to enable TTS for your web site, and we provide javascript library for TTS player, you can enable the player with one function call.
- Improve user experience of your website.
- Enable accessibility of your website.

# TTS Player WordPress plugin
**This plugin is in private preview stage, please test it before going to production.**

**How to build WordPress plugin?**
1. Download folder **./tts-player** to local.
2. Download file **msttsplayer.php** and file **uninstall.php** from folder **./TTSPlayer/WordPress-Plugin** to local.
3. Zip the above files into a zip file with name **msttsplayer.zip**, below is the folder strucutre inside the zip file:
   > \- msttsplayer.php
   > \- uninstall.php
   > \- tts-player
   >> \- tts-player.css
   >> \- tts-player.js
   >> \- images\\*

**How to install WordPress plugin?**
If your website is build based on WordPress, here we provide a WordPress plugin to help you build your website to support TTS player with ZERO coding.
Below are the steps to install TTS player WordPress plugin:
1. In WordPress admin page, choose **Plugins** menu item, then click the **Upload Plugin** button, choose the downloaded WordPress plugin zip file **msttsplayer.zip**, click **Install Now** button.
2. Click the **Settings** menu item, there will be an new menu item with name **Microsoft TTS Player**, click it.
3. Choose the region and voice name for your player, and input the GUID format of player ID, click **Submit** to save the configuration.
4. Wait for several mins to let the configuration take effect, and open one web page to try the player.

**For developers who want to customize the WordPress plugin:**
1. For Develop environment, modify wwwroot\wp-config.php file, set WP_DEBUG variable to true as below:
        define( 'WP_DEBUG', true );
2. After tht WordPress plugin installed, the content of the zip will be installed under: wwwroot\wp-content\plugins\msttsplayer\.
3. Then modify the plugin source for development.