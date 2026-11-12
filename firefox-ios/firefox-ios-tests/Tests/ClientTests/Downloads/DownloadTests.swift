// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/

import WebKit
import XCTest
@testable import Client

@MainActor
final class DownloadTests: XCTestCase {
    var download: Download!

    override func setUp() async throws {
        try await super.setUp()
        download = Download(originWindow: .XCTestDefaultUUID)
    }

    override func tearDown() async throws {
        download = nil
        try await super.tearDown()
    }

    func testDelegateMemoryLeak() {
        let mockDownloadDelegate = MockDownloadDelegate()
        download.delegate = mockDownloadDelegate
        trackForMemoryLeaks(download, file: #filePath, line: #line)
        download = nil
    }

    func testCancelDoesNotLeak() {
        let mockDownloadDelegate = MockDownloadDelegate()
        download.delegate = mockDownloadDelegate

        // Simulate canceling the download
        download.cancel()

        // Check for memory leaks
        trackForMemoryLeaks(download, file: #filePath, line: #line)

        download = nil
    }

    func testPauseDoesNotLeak() {
        let mockDownloadDelegate = MockDownloadDelegate()
        download.delegate = mockDownloadDelegate

        // Simulate pausing the download
        download.pause()

        // Check for memory leaks
        trackForMemoryLeaks(download, file: #filePath, line: #line)

        download = nil
    }

    func testResumeDoesNotLeak() {
        let mockDownloadDelegate = MockDownloadDelegate()
        download.delegate = mockDownloadDelegate

        // Simulate resuming the download
        download.resume()

        // Check for memory leaks
        trackForMemoryLeaks(download, file: #filePath, line: #line)

        download = nil
    }

    // MARK: - Download path containment

    func testUniqueDownloadPath_plainFilename_isInsideDownloadsDirectory() throws {
        let url = try download.uniqueDownloadPathForFilename("file.pdf")

        XCTAssertEqual(url.lastPathComponent, "file.pdf")
        XCTAssertEqual(url.deletingLastPathComponent().lastPathComponent, "Downloads")
    }

    func testUniqueDownloadPath_traversalFilename_throws() {
        // The filename is normally sanitized at assignment; this guards the write site itself.
        XCTAssertThrowsError(try download.uniqueDownloadPathForFilename("../../escaped.plist")) { error in
            guard case DownloadPathError.unsafeFilename(let name) = error else {
                return XCTFail("Expected DownloadPathError.unsafeFilename, got \(error)")
            }
            XCTAssertEqual(name, "../../escaped.plist")
        }
    }

    func testUniqueDownloadPath_dotDotFilename_throws() {
        XCTAssertThrowsError(try download.uniqueDownloadPathForFilename(".."))
    }

    // MARK: - Filename sanitization

    func testBlobDownload_traversalFilename_isSanitized() {
        let subject = BlobDownload(originWindow: .XCTestDefaultUUID,
                                   filename: "../../escaped.plist",
                                   mimeType: "application/pdf",
                                   size: 0,
                                   data: Data())

        XCTAssertEqual(subject.filename, "escaped.plist")
    }

    func testBlobDownload_strippedCharactersFormingTraversal_isSanitized() {
        // stripUnicode removes the zero-width spaces, which would otherwise form "../../" after stripping.
        // Sanitization must therefore run after stripping, not before.
        let subject = BlobDownload(originWindow: .XCTestDefaultUUID,
                                   filename: ".\u{200B}./.\u{200B}./escaped.pdf",
                                   mimeType: "application/pdf",
                                   size: 0,
                                   data: Data())

        XCTAssertEqual(subject.filename, "escaped.pdf")
    }

    func testHTTPDownload_traversalSuggestedFilename_isSanitized() throws {
        // Foundation normally flattens separators in suggestedFilename; the mock bypasses that
        // so the download's own sanitization is what is under test here.
        let url = try XCTUnwrap(URL(string: "https://example.com/file.pdf"))
        let response = MockURLResponse(filename: "../../escaped.plist", url: url)
        let subject = try XCTUnwrap(HTTPDownload(originWindow: .XCTestDefaultUUID,
                                                 cookieStore: WKWebsiteDataStore.default().httpCookieStore,
                                                 preflightResponse: response,
                                                 request: URLRequest(url: url)))
        defer { subject.cancel() }

        XCTAssertEqual(subject.filename, "escaped.plist")
    }
}

// MARK: - DownloadDelegate Methods
class MockDownloadDelegate: DownloadDelegate {
    // Called when the download is complete
    func download(_ download: Download, didCompleteWithError error: Error?) { }

    // Called when a certain amount of bytes have been downloaded
    func download(_ download: Download, didDownloadBytes bytesDownloaded: Int64) { }

    // Called when the download finishes and provides the location of the downloaded file
    func download(_ download: Download, didFinishDownloadingTo location: URL) { }
}
