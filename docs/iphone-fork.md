# FFox fork dev for iPhone and iPad

This is a local source fork of [Firefox iOS](https://github.com/mozilla-mobile/firefox-ios),
based on upstream commit `0ce12e0c`. It uses the existing native Swift application and
WebKit engine. It does not port desktop Gecko or Firefox desktop extensions to iOS.

The Client target is universal (`TARGETED_DEVICE_FAMILY = 1,2`), supporting iOS
and iPadOS. iPad uses desktop identity and rendering by default too; its existing
mobile-site override remains available. Both device families use the same blockers.

## Fork defaults

- Request desktop identity and desktop page rendering on iPhone, including normal,
  private, restored, and newly opened tabs. Keep the existing mobile-site override
  for sites that need it.
- Keep web links inside the browser by default, with the existing external-app setting
  available as an override.
- Enable the existing EasyList ad blocker when the user has not chosen a setting.
  Respect an explicit off setting. Keep tracking protection as a separate feature.
- Include the upstream `ad-block.json` in app resources and compile it during startup.
  Main-frame web navigation waits for content rules to be attached. Existing Remote
  Settings updates can refresh the list; first-use protection uses bundled data.

Desktop mode affects the browser's requests and rendering. It cannot make a website
provide a desktop version. Literal mobile URLs, responsive layouts, touch detection,
and server redirects can still produce mobile content. This fork adds no general
rewrite of `m.` hosts or arbitrary link paths: their desktop equivalents are not
predictable, and rewriting can break links or change their destination.

Ad blocking is list-based, not a promise that every ad disappears. Upstream's list
contains exceptions, including search and other sites. First-party and video ads can
remain. The existing site safelist and global blocker switch are retained.

## YouTube page filtering

The original device build included Mozilla's static EasyList-based blocker, not
uBlock Origin. Desktop identity does not add desktop Firefox's extension APIs.
Compiling its rules successfully did not establish YouTube video-ad blocking.

The fork now also bundles 25 YouTube page rules from AdGuard Filters revision
`11f2af14f6c0ce87b209264540c3818ff7a214a0`, compiled with AdGuard Scriptlets 2.5.1
and AGTree 4.2.1. These execute in the page world at document start, before YouTube
scripts, on the matching YouTube domains. They filter initial player properties,
fetch/XHR player responses, Shorts metadata, and newer player paths. They do not
install the uBlock extension or implement every desktop blocking capability.

The existing Ad Blocker toggle also controls this layer. Changing it or the site
safelist rebuilds scripts before reloading the tab. Safelisted page/frame ancestors
are excluded. Existing tabs need reloading after installing the updated app.

Source rules and GPL-3.0 notices live in
`firefox-ios/Client/Frontend/UserContent/AdBlocking/`. The generated JavaScript also
contains the license. `pnpm run build` regenerates the asset offline from the pinned
source. To update, review the upstream YouTube section, update the selected rules
and revision, regenerate, then rerun the checks below and real YouTube playback.
This layer does not download and execute remote JavaScript. Filter improvements
currently require rebuilding the app.

The adapter supports only the checked-in YouTube JavaScript/scriptlet rules, with
domain scope and the existing `/tv` path rule. Firefox-only and obsolete Safari
compatibility variants were excluded. Unsupported rule types fail generation.
Network and HTML response-rewrite filters are not implemented by this adapter.
Live YouTube changes can still cause ads or playback problems; disabling the blocker
and reloading remains available. Ads inside the separate YouTube app are unaffected.

### YouTube validation

```bash
node --test scripts/test-youtube-blocking.mjs
xcrun swiftc -O -module-cache-path /tmp/ffox-swift-module-cache \
  -framework Cocoa -framework WebKit scripts/check-youtube-blocking.swift \
  -o /tmp/ffox-youtube-check
/tmp/ffox-youtube-check
/tmp/ffox-youtube-check --disabled
/tmp/ffox-youtube-check --unrelated
```

All three WebKit cases and the three generator checks passed on 2026-09-21.
The WebKit fixture checks initial player properties, a fetched player response,
and a non-player response that also contains ad fields. It verifies preservation
of video data, retention of ad fields when disabled/on an unrelated host, and
absence of script initialization warnings. It does not contact YouTube or prove
that every live ad delivery variant is handled. XHR interception and the live
video player require further end-to-end coverage.

The signed updated app built, installed, and remained running on `deadbeef7`.
The bundled asset matches the generated source. Native injection XCTest cases
were added but have not been run. Real YouTube replay confirmation is pending.

## Setup and installation status

The development app is named **FFox fork dev**. Device build preparation uses an
isolated generated project; the upstream project's signing settings remain intact.

Use the Xcode version specified in the root README. The application project is
`firefox-ios/Client.xcodeproj`, scheme `Fennec`. Native code remains Swift because
this is an existing Firefox iOS fork. Device installation requires configuring your
own development team, provisioning, and suitable bundle/app-group identifiers for
the application and its extensions; the upstream signing configuration is retained.

The [upstream setup guide](../firefox-ios/README.md) describes dependency setup.
This checkout was prepared using `pnpm install --lockfile=false`, `pnpm run build`,
Mozilla's Nimbus bootstrap, and `sh scripts/install-swiftlint.sh`. Swift packages
were resolved through Xcode's system Git provider, without GitHub credentials.

### Personal Team device build

Generate an app-only Debug project using your Apple development team and unique
bundle identifier:

```bash
python3 scripts/prepare-personal-device.py --team YOURTEAMID --bundle-id net.example.ffoxfork.dev
env GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/usr/bin/false xcodebuild \
  -project .build/personal-device/Client.xcodeproj -scheme Fennec -configuration Debug \
  -destination 'id=YOUR_DEVICE_UDID' -derivedDataPath .build/DeviceDerivedData \
  -clonedSourcePackagesDirPath .build/SourcePackages -scmProvider system \
  -packageAuthorizationProvider netrc -skipPackageUpdates \
  -allowProvisioningUpdates -allowProvisioningDeviceRegistration \
  DEVELOPMENT_TEAM=YOURTEAMID CODE_SIGN_STYLE=Automatic build
```

Enable the pinned `ModifiedCopyMacros` package in Xcode before building. The local
CLI build used `-skipMacroValidation` after reviewing that package's macro source.
Apple signing credentials are separate from GitHub access. Public package fetches
do not require GitHub sign-in.

The generated project excludes app extensions and uses minimal keychain entitlements.
Widgets, credential-provider extensions, push capabilities, and default-browser
registration are unavailable in this Personal Team build. Its Info.plist marker
selects app-local Documents storage for tab state and Nimbus data. Normal builds
retain app-group storage. Personal Team provisioning expires and requires rebuilding.

After a successful build, install and launch using the same bundle identifier:

```bash
xcrun devicectl device install app --device YOUR_DEVICE_UDID \
  .build/DeviceDerivedData/Build/Products/Debug-iphoneos/Client.app
xcrun devicectl device process launch --device YOUR_DEVICE_UDID net.example.ffoxfork.dev
```

On 2026-09-21, Xcode 27.0 built and signed this configuration with team `PP97C35JA7`
and bundle identifier `net.mich431.ffoxfork.dev`. It was installed and launched on
`deadbeef7` (iPhone 17 Pro, iOS 26.7). The device reports the exact display name
`FFox fork dev`. Provisioning expires 2026-09-28 at 06:51:39 UTC; rebuild before then.
No remote publication has been performed.

A universal physical-device build (`-destination 'generic/platform=iOS'`) also
succeeded on 2026-09-21. Its app metadata declares both iPhone and iPad, and includes
the current YouTube filtering asset. A device-specific build subsequently succeeded
for `deadbeef6` (iPad Air 13-inch M3, iPadOS 26.7,
UDID `00008122-000928CC2E11001C`). Installation and launch succeeded after enabling
Developer Mode, restarting, and trusting the developer account under Settings >
General > VPN & Device Management. The app remained running at first-run onboarding;
live iPad browsing and long-play YouTube blocking have not yet been verified.

The iPad provisioning profile includes its UDID and expires 2026-09-28 at
07:28:37 UTC. Local signature verification passed, and the installed app reports
`FFox fork dev`, bundle `net.mich431.ffoxfork.dev`, version 157.1 (1).
The bundled YouTube script matches the generated asset. Other switches in the
iPad's Developer settings can remain at their defaults.

## Validation

Checks include Swift syntax parsing, focused SwiftLint, Xcode project plist validation,
bundled rule JSON/resource-registration checks, and a signed physical-device build.

Passed `xcrun swiftc -frontend -parse` and `swiftlint lint --strict --quiet --no-cache`
for all 16 changed Swift files, and `plutil -lint firefox-ios/Client.xcodeproj/project.pbxproj`.
JSON and project checks confirmed 63,730 bundled rules and resource membership in
both `Client` and `ClientTests`. Initial lint warnings were fixed before the strict check.

`python3 -m unittest scripts/test_prepare_personal_device.py` passes, checking
extension removal (including Sticker), display name, signing settings, isolated
project paths, and preservation of the source project. Device startup logged
`Compiled 9 of 9 lists checked. 0 errors.`, including `ad-block`, and the app remained
running after startup. The initial Personal Team preferences crash was fixed by
using a separate local preferences suite instead of the app's bare bundle identifier.

Xcode 27's Debug build logs duplicate Objective-C classes from package frameworks
and `Client.debug.dylib` at startup. Launch succeeded after the preferences fix;
those linker warnings remain unresolved. Browsing smoke checks below remain pending.

Regression tests cover desktop defaults and manual overrides, ad-blocking defaults,
settings/reporting consistency, private-tab blocking, and compilation of bundled
rules with no network fetch. XCTest has not yet been run; the device smoke check
does not establish that these regression tests pass.

For fuller functional validation, run the focused test targets and verify:

1. A fresh install requests desktop identity and renders desktop content.
2. Same-tab links, redirects, `target="_blank"`, new/private tabs, and restored tabs
   retain desktop behavior; switching one site to mobile still works.
3. HTTP(S) links stay in the browser by default; an explicit external-app override works.
4. A fresh profile with Remote Settings unavailable attaches bundled ad rules before
   its first web page loads. A known blocked test request fails, an ordinary request succeeds.
5. Blocker off, site exceptions, rule updates, and restart preserve their expected state.

Upstream notices and the existing [EasyList attribution](../firefox-ios/Client/Assets/About/LicenseFiles/EasyList.txt)
remain in place. See [Mozilla's blocker description](https://blog.mozilla.org/en/firefox/ad-blocker-on-ios/)
for the upstream filter's coverage.
