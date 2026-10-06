// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/

@testable import Client

import Common
import Shared
import XCTest
import WebKit

class TabWebViewTests: XCTestCaseRootViewController, UIGestureRecognizerDelegate {
    private var configuration = WKWebViewConfiguration()
    private var navigationDelegate: MockNavigationDelegate!
    private var tabWebViewDelegate: MockTabWebViewDelegate!
    private let sleepTime: UInt64 = 1 * NSEC_PER_SEC
    let windowUUID: WindowUUID = .XCTestDefaultUUID

    override func setUp() async throws {
        try await super.setUp()
        navigationDelegate = MockNavigationDelegate()
        tabWebViewDelegate = MockTabWebViewDelegate()
        DependencyHelperMock().bootstrapDependencies()
    }

    override func tearDown() async throws {
        navigationDelegate = nil
        tabWebViewDelegate = nil
        DependencyHelperMock().reset()
        try await super.tearDown()
    }

    func testBasicTabWebView_doesntLeak() async throws {
        _ = try await createSubject()
    }

    func testSavedCardsClosure_doesntLeak() async throws {
        let subject = try await createSubject()
        subject.accessoryView.savedCardsClosure = {}
    }

    func testAddPullRefresh() async throws {
        let subject = try await createSubject()
        subject.addPullRefresh {}

        XCTAssertNotNil(subject.scrollView.subviews.first(where: { $0 is PullRefreshView }))
    }

    func testRemovePullRefresh() async throws {
        let subject = try await createSubject()

        subject.addPullRefresh {}
        subject.removePullRefresh()

        XCTAssertNil(subject.subviews.first(where: { $0 is PullRefreshView }))
    }

    func testTabWebView_doesntLeak() {
        let tab = Tab(profile: MockProfile(), windowUUID: windowUUID)
        tab.createWebview(configuration: configuration)

        trackForMemoryLeaks(tab)
    }

    func testTabWebView_usesDesktopDefaults() throws {
        let tab = Tab(profile: MockProfile(), windowUUID: windowUUID)
        tab.createWebview(configuration: configuration)

        let webView = try XCTUnwrap(tab.webView)
        XCTAssertEqual(webView.customUserAgent, UserAgent.desktopUserAgent())
        XCTAssertEqual(webView.configuration.defaultWebpagePreferences?.preferredContentMode, .desktop)
    }

    func testTabWebView_respectsMobileSiteException() throws {
        let url = URL(string: "https://desktop-default-test.example.org")!
        let mobileChangedUA = UIDeviceDetails.userInterfaceIdiom != .phone
        Tab.ChangeUserAgent.updateDomainList(forUrl: url, isChangedUA: mobileChangedUA, isPrivate: false)
        defer {
            Tab.ChangeUserAgent.updateDomainList(forUrl: url, isChangedUA: !mobileChangedUA, isPrivate: false)
        }
        let tab = Tab(profile: MockProfile(), windowUUID: windowUUID)
        tab.url = url
        tab.createWebview(configuration: configuration)

        let webView = try XCTUnwrap(tab.webView)
        XCTAssertFalse(tab.usesDesktopSite)
        XCTAssertEqual(webView.customUserAgent, UserAgent.mobileUserAgent())
        XCTAssertEqual(webView.configuration.defaultWebpagePreferences?.preferredContentMode, .mobile)
    }

    func testTabWebView_load_doesntLeak() {
        let tab = Tab(profile: MockProfile(), windowUUID: windowUUID)
        tab.createWebview(configuration: configuration)
        tab.loadRequest(URLRequest(url: URL(string: "https://www.mozilla.com")!))

        trackForMemoryLeaks(tab)
    }

    func testTabWebView_withLegacySessionData_doesntLeak() {
        let tab = Tab(profile: MockProfile(), windowUUID: windowUUID)
        tab.url = URL(string: "http://yahoo.com/")!
        tab.createWebview(configuration: configuration)

        trackForMemoryLeaks(tab)
    }

    func testTabWebView_withSessionData_doesntLeak() {
        let tab = Tab(profile: MockProfile(), windowUUID: windowUUID)
        tab.createWebview(with: Data(), configuration: configuration)

        trackForMemoryLeaks(tab)
    }

    func testTabWebView_withURL_doesntLeak() {
        let tab = Tab(profile: MockProfile(), windowUUID: windowUUID)
        tab.url = URL(string: "https://www.mozilla.com")!
        tab.createWebview(configuration: configuration)

        trackForMemoryLeaks(tab)
    }

    func testHasOnlySecureContent_returnsTrue_ForLocalPDFFile() throws {
        let tab = Tab(profile: MockProfile(), windowUUID: windowUUID)
        tab.url = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("test.pdf")
        tab.createWebview(configuration: configuration)

        let tabWebView = try XCTUnwrap(tab.webView)

        XCTAssertTrue(tabWebView.hasOnlySecureContent)
    }

    // MARK: - Helper methods

    func createSubject(file: StaticString = #filePath,
                       line: UInt = #line) async throws -> TabWebView {
        let subject = TabWebView(frame: CGRect(origin: .zero, size: CGSize(width: 100, height: 100)),
                                 configuration: .init(),
                                 windowUUID: windowUUID,
                                 certStore: MockProfile().certStore)
        try await Task.sleep(nanoseconds: sleepTime)
        subject.configure(delegate: tabWebViewDelegate, navigationDelegate: navigationDelegate)
        trackForMemoryLeaks(subject)
        return subject
    }
}

// MARK: - MockTabWebViewDelegate
class MockTabWebViewDelegate: TabWebViewDelegate {
    func tabWebView(_ tabWebView: TabWebView,
                    didSelectFindInPageForSelection selection: String) {}

    func tabWebViewSearchWithFirefox(_ tabWebViewSearchWithFirefox: TabWebView,
                                     didSelectSearchWithFirefoxForSelection selection: String) {}

    func tabWebViewShouldShowAccessoryView(_ tabWebView: TabWebView) -> Bool {
        return true
    }
}

// MARK: - MockNavigationDelegate
class MockNavigationDelegate: NSObject, WKNavigationDelegate {}
