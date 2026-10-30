# Paid-team device signing

On 6 October 2026, FFox fork dev was rebuilt, installed over the existing app,
and launched successfully on both `deadbeef7` (iPhone) and `deadbeef6` (iPad).
Team `PP97C35JA7` and bundle ID `net.mich431.ffoxfork.dev` were retained.

The paid-team provisioning profile covers both device UDIDs and uses Apple's
wildcard application identifier `PP97C35JA7.*`. The signed app's entitlement
remains `PP97C35JA7.net.mich431.ffoxfork.dev`. The deployment validator now accepts
matching terminal `.*` profiles while rejecting unrelated teams, prefixes, and
invalid wildcard patterns. Existing signature, bundle ID, expiry, and device
checks still apply.

| Signing limit | Expiry (Australia/Sydney) |
| --- | --- |
| Embedded provisioning profile | 6 October 2027, 09:05:36 |
| Actual app signing certificate | 15 September 2027, 19:52:45 |

Rebuild/re-sign before the earlier expiry: **15 September 2027**. This gives
more than eleven months from this deployment. A future rebuild's actual profile
and signing certificate must be checked again; deployment output reports profile
expiry, which may be later than certificate expiry.

## Rebuild and checks

Use the existing [terminal deployment guide](command-line-deploy.md).

```sh
./scripts/deploy-device.py both
python3 -m unittest scripts/test_deploy_device.py scripts/test_prepare_personal_device.py
```

The initial build required the documented `--skip-macro-validation` workaround
after reviewing the pinned `ModifiedCopyMacros` source. Xcode then reused the old
seven-day profile. That app-specific cached profile was moved to a temporary
backup before requesting fresh provisioning. The paid build succeeded, but the
old validator rejected its wildcard profile before installation. After verifying
the signature, signed entitlements, certificate, profile, and both device UDIDs,
the same universal paid-signed app was manually installed and launched on both
devices. The validator fix passed all nine focused deployment/preparation tests.

## Security deployment on 20 October 2026

The current patched FFox 157.1 (build 1), bundle `net.mich431.ffoxfork.dev`, was
built and signed for device families 1 and 2, then installed successfully on
`deadbeef7` and `deadbeef6`. Initial launch requests were rejected with `Locked`;
both app installations were confirmed. The follow-up iPhone update and process
launch succeeded. The iPad repeat installation encountered a remote connection
error and bounded retry timed out; its earlier patched installation was confirmed,
while launch/UI verification remains deferred. Lois-iPad is excluded from routine
updates unless specifically requested.

The embedded profile covers all three registered devices and expires
18 October 2027, 15:58:46 Sydney. The selected installed signing certificate still
expires earlier, **15 September 2027, 19:52:45 Sydney**. No private signing material
was exported or uploaded. The source pin and build output show Swift Crypto 4.5.1;
the built app contains the safe translation binding and regenerated JS assets.

Focused translation XCTest passed all 10 tests on iOS 27 Simulator. JavaScript
security/rule checks passed 7 tests. These checks establish neither physical UI
acceptance nor complete coverage of embedded Rust binaries.

## Security deployment on 26 October 2026

The weekly build (FFox 157.1 build 1, device families 1 and 2, Xcode 27.1 and
iPhoneOS 27.1 SDK) was installed on `deadbeef6`; its launch request was refused
with `Locked`, so launch verification is deferred. `deadbeef7` stayed
`unavailable` to CoreDevice for 30 minutes, so its update is **incomplete**; rerun
`./scripts/deploy-device.py deadbeef7 --skip-macro-validation` once it is
connected and reachable. Xcode 27.1 again required macro approval; the checkout
was confirmed at the reviewed `ModifiedCopyMacros` revision `d020bf8c6432`
before using the documented workaround. Signing certificate and profile expiry
are unchanged from 20 October.

## Security deployment on 31 October 2026

The on-demand security build (FFox 157.1 build 1, Xcode 27.1, iPhoneOS 27.1 SDK)
links App Services with SQLite 3.54.1 in place of 3.50.2 (see
[security maintenance](security-maintenance.md)). The built app's
`RustMozillaAppServices` contains only the 3.54.1 source ID; Glean keeps its own
3.50.2 copy. It was installed on `deadbeef7` and `deadbeef6`; both launch requests
were refused with `Locked`, so launch verification is deferred. Codesign
verification passed; signing expiry is unchanged.

## Scheduled maintenance

T3 Code tasks post into the original rebuild thread:

- Rebuild reminder: **15 August 2027, 10:00 Sydney**, one calendar month before
  certificate expiry. Stored as an interval task with instructions to disable
  itself after its first reminder. This reminder does not rebuild automatically.
- CVE check: **Mondays, 09:00 Sydney**, first run **12 October 2026**. Checks actual
  pinned/installed JS and Swift libraries, vendored code, Mozilla/Glean binaries,
  Firefox iOS advisories, and OS-provided WebKit advisories. Since 20 October,
  each run must patch still-valid actionable findings, run focused checks, build,
  sign and install on deadbeef7 and deadbeef6, then attempt launch. Lois-iPad is
  included only when specifically requested for that run. An explicit `Locked`
  launch refusal is recorded as deferred verification after a completed update;
  it does not stop the other default device. Builds and
  deployments also run when no new applicable CVE is found. A report alone never
  completes the task. Unavailable hardware/signing prerequisites leave that
  deployment incomplete and require concrete follow-up; other targets continue.
  Keep the existing team/bundle ID and use pinned local native dependencies.
  Open or update the michft PR with validation and per-device evidence; do not
  merge automatically. Private signing exports and unapproved public cache
  uploads remain outside this automation.

- Weekly CVE review: **Mondays, 08:00 Sydney**, report-only. Covers Firefox, Zen
  Browser and every downloaded input, shipped or build-only, at any severity; its
  applicable findings feed the 09:00 patch/build/deploy run.
- Daily CVE check: **07:00 Sydney**. Looks for CVSS above 8.0 in shipped code. An
  applicable unfixed finding immediately starts the weekly patch/build/deploy
  procedure for that item; build-only tools and OS-provided WebKit never trigger it.

Reschedule the reminder when a later deployment changes the earliest signing
expiry. The scheduled CVE check is not evidence that a security audit has already
run or that opaque binary dependencies have complete coverage.
