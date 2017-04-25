cmake_minimum_required(VERSION 2.8)

PROJECT(TTSClientSDK.normalTest)

MESSAGE(STATUS "Project: TTSClientSDK.normalTest")
MESSAGE(STATUS "Project Directory: ${PROJECT_SOURCE_DIR}")

IF (CMAKE_SYSTEM_NAME MATCHES "Linux")
    MESSAGE(STATUS "current platform: Linux ")
ELSEIF (CMAKE_SYSTEM_NAME MATCHES "Windows")
    MESSAGE(STATUS "current platform: Windows")
ELSE ()  
    MESSAGE(STATUS "other platform: ${CMAKE_SYSTEM_NAME}") 
ENDIF (CMAKE_SYSTEM_NAME MATCHES "Linux") 


IF(NOT CMAKE_BUILD_TYPE)
    SET(CMAKE_BUILD_TYPE Debug)
ENDIF(NOT CMAKE_BUILD_TYPE)


SET(Compiler_Flags_CPP "-std=gnu++1y -Wconversion-null ${Compiler_Flags_Common}")
SET(Compiler_Flags_C " ${Compiler_Flags_Common}")

SET(Compiler_Flags_Common_Debug "-O0 -g -fms-extensions -frtti -Wno-unused-value -Wno-comment -Wint-to-pointer-cast -fpermissive")
SET(Compiler_Flags_Common_Release "-O3 -DNDEBUG -fms-extensions -frtti -Wno-unused-value -Wno-comment -Wint-to-pointer-cast -fpermissive")

SET(CMAKE_C_FLAGS_DEBUG "${Compiler_Flags_C} ${Compile_Options_Debug}")
SET(CMAKE_C_FLAGS_RELEASE "${Compiler_Flags_C} ${Compile_Options_Release}")


IF(NOT CPU_PLATFORM)
    IF (CMAKE_SYSTEM_NAME MATCHES "Linux")
        SET(CPU_PLATFORM "x64")
    ELSE ()  
        SET(CPU_PLATFORM "x86")
    ENDIF (CMAKE_SYSTEM_NAME MATCHES "Linux") 
ENDIF(NOT CPU_PLATFORM)


IF(CPU_PLATFORM MATCHES x86)
    MESSAGE(STATUS "CPU platform: ${CPU_PLATFORM}")
    IF(CMAKE_SYSTEM_NAME MATCHES "Linux")
        SET(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -m32")  
        SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -m32")  
    ENDIF(CMAKE_SYSTEM_NAME MATCHES "Linux")
    SET(CPU_PLATFORM "x86")
ELSE(CPU_PLATFORM MATCHES x64)
    MESSAGE(STATUS "CUP platform: ${CPU_PLATFORM}")
    SET(CPU_PLATFORM "x64")
ENDIF(CPU_PLATFORM MATCHES x86)  

set(Project_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../..)

IF (CMAKE_SYSTEM_NAME MATCHES "Linux")
    include_directories("${Project_DIR}/include" "${Project_DIR}/3rdparty/silk/include" "${Project_DIR}/3rdparty/curl/include")
    add_definitions(-DCURL_VERBOSE -DNO_SSL_VERIFYPEER -D_GNU_SOURCE -DCURL_STATICLIB)
    link_directories("${CMAKE_CURRENT_SOURCE_DIR}/../../public/lib/Linux/x86_64/Release")
    link_directories("${Project_DIR}/3rdparty/silk/lib/Linux/x86_64/Release")
ELSEIF (CMAKE_SYSTEM_NAME MATCHES "Windows")
    include_directories("${Project_DIR}/include" "${Project_DIR}/3rdparty/silk/include" "${Project_DIR}/3rdparty/curl/include")
    add_definitions(-DCURL_VERBOSE -DNO_SSL_VERIFYPEER -D_CRT_SECURE_NO_WARNINGS -DCURL_STATICLIB)
    IF(CPU_PLATFORM MATCHES x86)
        link_directories("${Project_DIR}/3rdparty/curl/lib/Windows/Win32/Release" "${Project_DIR}/3rdparty/openssl/lib/Windows/Win32/Release" "${Project_DIR}/3rdparty/silk/lib/Windows/Win32/Release")
    ELSE(CPU_PLATFORM MATCHES x64)
        link_directories("${Project_DIR}/3rdparty/curl/lib/Windows/Win32/Release" "${Project_DIR}/3rdparty/openssl/lib/Windows/x64/Release" "${Project_DIR}/3rdparty/silk/lib/Windows/x64/Release")
    ENDIF(CPU_PLATFORM MATCHES x86)  
ELSE ()  
    MESSAGE(STATUS "other platform: ${CMAKE_SYSTEM_NAME}") 
ENDIF (CMAKE_SYSTEM_NAME MATCHES "Linux") 

set(TTSClientSDK_src ${Project_DIR}/source/TTSClientSDK.c)
set(TTSClientSDK_src ${TTSClientSDK_src} ${CMAKE_CURRENT_SOURCE_DIR}/TTSClientSDK.normalTest.c)

ADD_EXECUTABLE(TTSSDK_normalTest ${TTSClientSDK_src})

IF (CMAKE_SYSTEM_NAME MATCHES "Linux")
    TARGET_LINK_LIBRARIES(TTSSDKsample silk curl)
ELSEIF (CMAKE_SYSTEM_NAME MATCHES "Windows")
    TARGET_LINK_LIBRARIES(TTSSDK_normalTest silk.lib libcurl.lib ws2_32.lib wldap32.lib libcrypto.lib libssl.lib)
ELSE ()
    MESSAGE(STATUS "other platform: ${CMAKE_SYSTEM_NAME}") 
ENDIF (CMAKE_SYSTEM_NAME MATCHES "Linux") 
