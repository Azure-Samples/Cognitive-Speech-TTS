#!/bin/bash
if [ ! -d "TTSClientSDK_x64" ]; then
	mkdir TTSClientSDK_x64
fi

cd TTSClientSDK_x64
cmake -DCPU_PLATFORM="x64" ../../../

