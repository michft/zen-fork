// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/

import XCTest
import WebKit

@testable import Client

@MainActor
final class UserScriptManagerTests: XCTestCase {
    func testYouTubeAdBlockerScriptIsDocumentStartAllFramesWhenEnabled() {
        let webView = WKWebView()
        UserScriptManager.shared.injectUserScriptsIntoWebView(
            webView,
            nightMode: false,
            noImageMode: false,
            backgroundAudio: false,
            adBlockEnabled: true
        )
        let script = webView.configuration.userContentController.userScripts.first {
            $0.source.contains("FFOX_ADBLOCK_SAFELIST")
        }
        XCTAssertNotNil(script)
        XCTAssertEqual(script?.injectionTime, .atDocumentStart)
        XCTAssertEqual(script?.forMainFrameOnly, false)
    }

    func testYouTubeAdBlockerScriptIsOmittedWhenDisabled() {
        let webView = WKWebView()
        UserScriptManager.shared.injectUserScriptsIntoWebView(
            webView,
            nightMode: false,
            noImageMode: false,
            backgroundAudio: false,
            adBlockEnabled: false
        )
        XCTAssertFalse(webView.configuration.userContentController.userScripts.contains {
            $0.source.contains("FFOX_ADBLOCK_SAFELIST")
        })
    }

    func testYouTubeAdBlockerSafelistIsJSONEscaped() {
        let webView = WKWebView()
        UserScriptManager.shared.injectUserScriptsIntoWebView(
            webView,
            nightMode: false,
            noImageMode: false,
            backgroundAudio: false,
            adBlockEnabled: true,
            safelistedDomains: ["example.com", "quoted\"domain"]
        )
        let script = webView.configuration.userContentController.userScripts.first {
            $0.source.contains("FFOX_ADBLOCK_SAFELIST")
        }
        XCTAssertNotNil(script)
        XCTAssertTrue(script?.source.contains("quoted\\\"domain") == true)
        XCTAssertTrue(script?.source.contains("ancestorOrigins") == true)
    }
}
