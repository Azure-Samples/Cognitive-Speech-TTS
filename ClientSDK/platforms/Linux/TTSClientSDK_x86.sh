#!/bin/bash
if [ ! -d "TTSClientSDK_x86" ]; then
	mkdir TTSClientSDK_x86
fi

cd TTSClientSDK_x86
cmake -DCPU_PLATFORM="x86" ../../../

