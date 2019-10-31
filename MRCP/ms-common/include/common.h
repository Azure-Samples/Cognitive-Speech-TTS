#pragma once

namespace Microsoft
{
namespace speechlib
{
struct Common
{
    static constexpr const char* SPEECH_SECTION = "speech_configs";
    static constexpr const char* SPEECH_SDK_REGION = "speech_sdk_region";
    static constexpr const char* SPEECH_SDK_KEY = "speech_sdk_key";
    static constexpr const char* MAX_SYNTHESIZER = "max_synthesizer";
    static constexpr const char* SR_USE_LOCAL_CONTAINER =
    "sr_use_local_container";
    static constexpr const char* TTS_USE_LOCAL_CONTAINER =
    "tts_use_local_container";
    static constexpr const char* SR_LOCAL_ENDPOINT = "sr_local_endpoint";
    static constexpr const char* SR_LOCAL_KEY = "sr_local_key";
    static constexpr const char* TTS_LOCAL_ENDPOINT = "tts_local_endpoint";
    static constexpr const char* TTS_LOCAL_KEY = "tts_local_key";
    static constexpr const char* TTS_LOCALE = "tts_locale";
    static constexpr const char* TTS_VOICE_NAME = "tts_voice_name";
    static constexpr const char* TTS_SAMPLE_RATE = "tts_sample_rate";
    static constexpr const char* TTS_EXTRA_ENABLE_PROPERTY =
    "tts_extra_enable_property";
};

} // namespace speechlib
} // namespace Microsoft
