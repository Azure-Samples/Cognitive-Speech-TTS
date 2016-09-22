//
// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license.
//
// Microsoft Cognitive Services (formerly Project Oxford): https://www.microsoft.com/cognitive-services
//
// Microsoft Cognitive Services (formerly Project Oxford) GitHub:
// https://github.com/Microsoft/Cognitive-Speech-TTS
//
// Copyright (c) Microsoft Corporation
// All rights reserved.
//
// MIT License:
// Permission is hereby granted, free of charge, to any person obtaining
// a copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so, subject to
// the following conditions:
//
// The above copyright notice and this permission notice shall be
// included in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED ""AS IS"", WITHOUT WARRANTY OF ANY KIND,
// EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
// LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
// OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
// WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//

package com.microsoft.cognitiveservices.ttssample;

public class ByteArray {
    private byte[] data;
    private int length;

    public ByteArray(){
        length = 0;
        data = new byte[length];
    }

    public ByteArray(byte[] ba){
        data = ba;
        length = ba.length;
    }

    /*
    concatenate the array second after array data
     */
    public  void cat(byte[] second, int offset, int length){

        if(this.length + length > data.length) {
            int allocatedLength = Math.max(data.length, length);
            byte[] allocated = new byte[allocatedLength << 1];
            System.arraycopy(data, 0, allocated, 0, this.length);
            System.arraycopy(second, offset, allocated, this.length, length);
            data = allocated;
        }else {
            System.arraycopy(second, offset, data, this.length, length);
        }

        this.length += length;
    }

    public  void cat(byte[] second){
        cat(second, 0, second.length);
    }

    public byte[] getArray(){
        if(length == data.length){
            return data;
        }

        byte[] ba = new byte[length];
        System.arraycopy(data, 0, ba, 0, this.length);
        data = ba;
        return ba;
    }

    public int getLength(){
        return length;
    }
}
