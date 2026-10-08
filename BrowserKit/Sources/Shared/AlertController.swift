// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/

import UIKit

// Subclassed to support accessibility identifiers
public final class AlertController: UIAlertController {
    public func addAction(_ action: UIAlertAction, accessibilityIdentifier: String) {
        action.accessibilityIdentifier = accessibilityIdentifier
        super.addAction(action)
    }
}
