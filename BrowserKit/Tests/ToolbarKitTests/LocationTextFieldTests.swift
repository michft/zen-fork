// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/

import UIKit
import XCTest
@testable import ToolbarKit

@MainActor
final class LocationTextFieldTests: XCTestCase {
    private final class ClearDelegate: LocationTextFieldDelegate {
        var clearCount = 0

        func locationTextFieldShouldClear() -> Bool {
            clearCount += 1
            return true
        }

        func locationTextFieldDidEnterText(_ text: String) {}
        func locationTextFieldShouldReturn(_ textField: LocationTextField) -> Bool { return true }
        func locationTextFieldDidBeginEditing(_ textField: UITextField) {}
        func locationTextFieldDidEndEditing() {}
        func locationTextFieldNeedsSearchReset() {}
        func locationTextFieldDidDisplayEditingAccessoryButton(_ button: UIButton, contextualHintType: String) {}
    }

    private var textField: LocationTextField!
    private var window: UIWindow!

    override func setUp() async throws {
        try await super.setUp()
        window = UIWindow(frame: CGRect(x: 0, y: 0, width: 375, height: 44))
        textField = LocationTextField(frame: window.bounds)
        window.addSubview(textField)
        window.makeKeyAndVisible()
    }

    override func tearDown() async throws {
        textField.resignFirstResponder()
        window.isHidden = true
        textField = nil
        window = nil
        try await super.tearDown()
    }

    private func makeTextFieldEditing() {
        textField.becomeFirstResponder()
    }

    func testClearButton_retainsNativeControlAndAccessibilityBehavior() throws {
        let delegate = ClearDelegate()
        textField.autocompleteDelegate = delegate
        textField.frame = window.bounds
        makeTextFieldEditing()
        textField.text = "example.com"
        textField.setNeedsLayout()
        textField.layoutIfNeeded()

        let button = try XCTUnwrap(textField.clearButton)
        let nativeTextField = UITextField(frame: window.bounds)
        nativeTextField.clearButtonMode = .always
        nativeTextField.text = "example.com"
        window.addSubview(nativeTextField)
        nativeTextField.layoutIfNeeded()
        let nativeButton = try XCTUnwrap(nativeTextField.subviews.compactMap { $0 as? UIButton }.first)

        XCTAssertEqual(button.frame, textField.clearButtonRect(forBounds: textField.bounds))
        XCTAssertEqual(button.accessibilityLabel, nativeButton.accessibilityLabel)
        XCTAssertEqual(button.accessibilityTraits, nativeButton.accessibilityTraits)
        XCTAssertEqual(button.allControlEvents, nativeButton.allControlEvents)
        XCTAssertTrue(button.allTargets.contains { ($0.base as? UITextField) === textField })

        XCTAssertTrue(textField.textFieldShouldClear(textField))

        XCTAssertEqual(textField.text, "")
        XCTAssertEqual(delegate.clearCount, 1)
        XCTAssertNil(textField.markedTextRange)
    }

    func testClearButton_excludesEditingAccessory() throws {
        textField.frame = window.bounds
        makeTextFieldEditing()
        textField.editingAccessoryAction = ToolbarElement(
            iconName: "accessory",
            isEnabled: true,
            a11yLabel: "Accessory",
            a11yHint: nil,
            a11yId: "accessory",
            hasLongPressAction: false,
            onSelected: nil
        )
        textField.setNeedsLayout()
        textField.layoutIfNeeded()

        let accessory = try XCTUnwrap(textField.rightView)
        XCTAssertEqual(accessory.accessibilityIdentifier, "accessory")
        XCTAssertFalse(textField.clearButton === accessory)
        XCTAssertEqual(textField.clearButtonMode, .never)
    }
}
