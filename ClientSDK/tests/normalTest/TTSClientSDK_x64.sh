#!/bin/bash
if [ ! -d "normalTest_x64" ]; then
	mkdir normalTest_x64
fi

cd normalTest_x64
cmake -DCPU_PLATFORM="x64" ../

