# FFox fork dev

Local fork of Firefox for iPhone and iPad with desktop browsing and built-in ad blocking enabled by default.
See [fork behavior, setup, and validation](docs/iphone-fork.md).

Public source: [michft/zen-fork](https://github.com/michft/zen-fork).
See [CI, signed releases, and installation limits](docs/github-releases.md).

## Upstream Firefox for iOS and Focus iOS

Download [Firefox iOS](https://apps.apple.com/app/firefox-web-browser/id989804926) and [Focus iOS](https://itunes.apple.com/app/id1055677337) on the App Store.

<table>
  <tr>
    <th style="border: none;"><strong>Firefox iOS</strong></th>
    <td style="border: none;"><img src="https://img.shields.io/badge/Xcode-26.5-blue?logo=Xcode&logoColor=white" alt="Firefox-iOS"></td>
    <td style="border: none;"><img src="https://img.shields.io/badge/Swift-6.2-red?logo=Swift&logoColor=white" alt="Firefox-iOS"></td>
    <td style="border: none;"><img src="https://img.shields.io/badge/iOS-15.0+-green?logo=apple&logoColor=white" alt="Firefox-iOS"></td>
  </tr>
  <tr>
    <th style="border: none;"><strong>Focus iOS</strong></th>
    <td style="border: none;"><img src="https://img.shields.io/badge/Xcode-26.5-blue?logo=Xcode&logoColor=white" alt="Focus-iOS"></td>
    <td style="border: none;"><img src="https://img.shields.io/badge/Swift-6.2-red?logo=Swift&logoColor=white" alt="Focus-iOS"></td>
    <td style="border: none;"><img src="https://img.shields.io/badge/iOS-15.0+-green?logo=apple&logoColor=white" alt="Focus-iOS"></td>
  </tr>
</table>

## Building the code

This is a monolithic-repository, containing both the Firefox and Focus iOS projects.

As this is an iOS project, it is required to have Xcode on your system, and you should check that `xcode-select -p` points to `/Applications/Xcode.app/Contents/Developer` (or however you've named your `Xcode.app`).

### Automatic Installation (Recommended)
Steps: [Automated Project Setup with FXIOS](https://github.com/mozilla-mobile/firefox-ios/wiki/Automated-Project-Setup-with-FXIOS)

### Manual Installation

1. Clone the repo locally
1. For their related build instructions, please follow the respective project readmes:

- [Firefox for iOS](./firefox-ios/README.md)
- [Focus iOS](./focus-ios/README.md)

## Getting involved

Report fork bugs and propose changes in [michft/zen-fork](https://github.com/michft/zen-fork).
See [CONTRIBUTING.md](CONTRIBUTING.md) for general code contribution guidance and
[GitHub releases](docs/github-releases.md) for this fork's build/release process.

## License

    This Source Code Form is subject to the terms of the Mozilla Public
    License, v. 2.0. If a copy of the MPL was not distributed with this
    file, You can obtain one at https://mozilla.org/MPL/2.0/
