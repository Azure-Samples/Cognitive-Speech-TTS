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

import Foundation

class TTSAuthentication {
    
    static let accessTokenUri = "https://api.cognitive.microsoft.com/sts/v1.0/issueToken"
    
    private let apiKey: String
    private var accessToken: String?
    
    //Access token expires every 10 minutes. Renew it every 9 minutes only.
    private static let refreshTokenDuration: Double = 9 * 60
    
    init(apiKey: String) {
        self.apiKey = apiKey
        self.refreshToken()
    }
    
    func getAccessToken(_ callback: @escaping (String) -> ()) {
        if let token = self.accessToken {
            callback(token)
        } else {
            self.refreshToken({ (token: String) in
                callback(token)
            })
        }
    }
    
    private func refreshToken(_ callback: ((String) -> ())? = nil) {
        TTSHttpRequest.submit(withUrl: TTSAuthentication.accessTokenUri, andHeaders: ["Ocp-Apim-Subscription-Key": apiKey]) { [weak self] (c: TTSHttpRequest.Callback) in
            defer {
                // renew the token every specified minutes
                DispatchQueue.global().asyncAfter(deadline: .now() + TTSAuthentication.refreshTokenDuration) {
                    self?.refreshToken()
                }
            }
            guard let data = c.data, let accessToken = String(data: data, encoding: String.Encoding.utf8) else {
                return
            }
            self?.accessToken = accessToken
            callback?(accessToken)
        }
    }

}
