cmake_minimum_required(VERSION 2.8)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)
endif(NOT CMAKE_BUILD_TYPE)

set(Compiler_Flags_CPP "-std=gnu++1y -Wconversion-null ${Compiler_Flags_Common}")
set(Compiler_Flags_C " ${Compiler_Flags_Common}")

set(Compiler_Flags_Common_Debug "-O0 -g -fms-extensions -frtti -Wno-unused-value -Wno-comment -Wint-to-pointer-cast -fpermissive")
set(Compiler_Flags_Common_Release "-O3 -DNDEBUG -fms-extensions -frtti -Wno-unused-value -Wno-comment -Wint-to-pointer-cast -fpermissive")

set(CMAKE_C_FLAGS_DEBUG "${Compiler_Flags_C} ${Compile_Options_Debug}")
set(CMAKE_C_FLAGS_RELEASE "${Compiler_Flags_C} ${Compile_Options_Release}")


include_directories("/usr/include" "../inc" "../../public/inc")
add_definitions(-DCURL_VERBOSE -DNO_SSL_VERIFYPEER -D_GNU_SOURCE -DCURL_STATICLIB)

link_directories("${CMAKE_CURRENT_SOURCE_DIR}/../../public/lib/Linux/x86_64/Release")

ADD_EXECUTABLE(TTSSDKsample ../src/TTSClientSDKSample.c ../src/TTSClientSDK.c )
TARGET_LINK_LIBRARIES(TTSSDKsample silk curl)
