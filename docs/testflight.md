# Internal TestFlight updates

`testflight.yml` builds one universal iPhone/iPad Release app from `main`, verifies
its App Store Connect signing, validates the IPA with Apple's `altool`, then uploads
it to App Store Connect. Dispatching this workflow authorizes that upload. It does
not create GitHub tags/releases, upload public build artifacts, or submit an app
for App Store review. Apple processing and tester distribution follow the upload.
See Apple's [build upload guide](https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds/).

This is separate from the longer registered-device signing described in
[paid device signing](paid-device-signing.md). Each TestFlight build expires after
90 days, regardless of the development profile's longer expiration date. Upload
and distribute a replacement before expiry; a new build can keep the same
committed `VERSION` while increasing its build number. See Apple's
[TestFlight overview](https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview/).

## Apple setup

1. Use the paid Apple Developer team `PP97C35JA7`, or override `IOS_TEAM_ID` for the
   team that owns this app. Accept current Apple agreements in App Store Connect.
2. Register the explicit bundle ID `net.mich431.ffoxfork.dev` and create its iOS
   app record in App Store Connect. Keep the bundle ID identical to the installed
   fork and record its numeric Apple app ID as `ASC_APP_ID`. Changing the bundle ID
   creates a separate app and storage sandbox.
3. Create an Apple Distribution certificate and an App Store Connect distribution
   provisioning profile for that explicit bundle ID. Export exactly one matching
   identity, including its private key, as a password-protected P12. Development,
   ad hoc, wildcard, and enterprise profiles are unsuitable for this workflow.
4. In App Store Connect, create a dedicated **team** API key with the Developer
   role needed for uploads. Record the key ID and issuer UUID; download its `.p8`
   key privately. This workflow uses team-key authentication, not an individual
   API key or Apple account password. Review the key's account-wide access before
   storing it. See [App Store Connect API setup](https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-api).
5. Complete beta test information and export compliance for the app in App Store
   Connect. The workflow does not answer those account questions automatically.

The app retains this fork's app-only project, minimal entitlements, and app-local
data storage. Signing for TestFlight does not restore Mozilla app groups,
extensions, or shared-container access. Back up local data before replacing an
existing development install; uninstalling can remove its local data.

## Private GitHub environment

The `ios-testflight` environment in **michft/zen-fork** is prepared with deployment
restricted to `main`, without credentials. Add required reviewers if desired. Keep these
credentials in environment secrets, not repository files, PRs, release assets,
comments, or workflow inputs.

| Environment secret | Value |
| --- | --- |
| `TESTFLIGHT_CERTIFICATE_P12_BASE64` | Base64 of the Apple Distribution P12 including private key |
| `TESTFLIGHT_CERTIFICATE_PASSWORD` | P12 password |
| `TESTFLIGHT_PROVISION_PROFILE_BASE64` | Base64 of matching explicit App Store Connect profile |
| `ASC_PRIVATE_KEY_P8_BASE64` | Base64 of the downloaded team API private key `.p8` |
| `ASC_KEY_ID` | Ten-character App Store Connect key ID |
| `ASC_ISSUER_ID` | App Store Connect team issuer UUID |

| Environment variable | Value |
| --- | --- |
| `ASC_APP_ID` | Required numeric Apple ID of this App Store Connect app |
| `IOS_TEAM_ID` | Optional; defaults to `PP97C35JA7` |
| `IOS_BUNDLE_ID` | Optional; defaults to `net.mich431.ffoxfork.dev` |

The workflow has a read-only GitHub token and no PR trigger. Signing files and API
keys stay in the runner's temporary directory. Cleanup restores the original
keychain search list, removes installed profiles and temporary keychain, and
deletes private exports and credentials even when a step fails. It publishes no
IPA, archive, profile, keychain, or API key to GitHub artifacts.

The release helper also generates a matching dSYM ZIP privately. This workflow
does not retain or upload that ZIP; cleanup deletes it with the IPA. Export requests
symbol uploading, but actual symbol delivery and crash symbolication must be
verified after the first real App Store Connect upload.

## Upload and device updates

Merge the release CI PR and this TestFlight PR first. Publish the reviewed michft
dependency snapshot required by [GitHub CI](github-releases.md); the workflow
fails if it is unavailable rather than downloading from upstream. Native builds
use the standard `xcode-27` preview runner, a 90-minute timeout, Node 24, pinned JavaScript
dependencies, and the same offline Swift/Nimbus dependency snapshot.

Dispatch **michft TestFlight** from `main`, with the version committed in `VERSION`:

```sh
gh workflow run testflight.yml --ref main -f version=0.1.0 --repo michft/zen-fork
```

The Apple build number is `GITHUB_RUN_NUMBER.GITHUB_RUN_ATTEMPT`, for example
`12.1` then `12.2` for a retry. Runs are serialized. Dispatch a new run, or retry
only the latest run, so an older build number does not follow a newer upload.
The workflow fails above run number 9999 or attempt 99 to preserve Apple's
conservative component limits. Do not rename/recreate the workflow and reset its
counter for an already-uploaded version. See Apple's
[bundle version reference](https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/CoreFoundationKeys.html#//apple_ref/doc/uid/TP40009249-SW9).

After Apple finishes processing, create an internal TestFlight group, enable
automatic distribution, and invite the App Store Connect users testing this app.
Install TestFlight on both iPhone and iPad, accept invitations, and enable
automatic updates in TestFlight. Apple documents internal group configuration in
[Add internal testers](https://developer.apple.com/help/app-store-connect/test-a-beta-version/add-internal-testers).

Check the processed build and install it on both device families before treating
the update as verified. A successful upload alone does not prove processing,
distribution, or installation succeeded. Keep a replacement build available
before the current build's 90-day deadline. External testing and its review are
separate; this workflow does not configure external groups or public invite links.
