// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/

import UIKit
import XCTest
import Shared

@testable import Client

@MainActor
final class UIAlertControllerExtensionTests: XCTestCase {
    func testAlertActionRetainsAccessibilityIdentifierBeforePresentation() {
        let alert = AlertController(title: nil, message: nil, preferredStyle: .alert)
        let action = UIAlertAction(title: "Confirm", style: .default)

        alert.addAction(action, accessibilityIdentifier: "confirm-action")

        XCTAssertTrue(alert.actions.first === action)
        XCTAssertEqual(action.accessibilityIdentifier, "confirm-action")
    }

    func testAddShortcutAlertEnablesSaveButtonForValidURL() throws {
        let alert = UIAlertController.addShortcutAlert { _ in }

        let saveAction = try XCTUnwrap(alert.actions.last)
        let textField = try XCTUnwrap(alert.textFields?.first)

        XCTAssertFalse(saveAction.isEnabled)

        textField.text = "facebook.com"
        textField.sendActions(for: .editingChanged)

        XCTAssertTrue(saveAction.isEnabled)
    }

    func testAddShortcutAlertDisablesSaveButtonForInvalidURL() throws {
        let alert = UIAlertController.addShortcutAlert { _ in }

        let saveAction = try XCTUnwrap(alert.actions.last)
        let textField = try XCTUnwrap(alert.textFields?.first)

        textField.text = "facebook.com"
        textField.sendActions(for: .editingChanged)

        XCTAssertTrue(saveAction.isEnabled)

        textField.text = "foo bar"
        textField.sendActions(for: .editingChanged)

        XCTAssertFalse(saveAction.isEnabled)
    }
}
