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

## Scheduled maintenance

T3 Code tasks post into the original rebuild thread:

- Rebuild reminder: **15 August 2027, 10:00 Sydney**, one calendar month before
  certificate expiry. Stored as an interval task with instructions to disable
  itself after its first reminder. This reminder does not rebuild automatically.
- CVE check: **Mondays, 09:00 Sydney**, first run **12 October 2026**. Checks actual
  pinned/installed JS and Swift libraries, vendored code, Mozilla/Glean binaries,
  Firefox iOS advisories, and OS-provided WebKit advisories. Reports findings,
  fixes, and coverage gaps; performs no automatic upgrades or deployment.

Reschedule the reminder when a later deployment changes the earliest signing
expiry. The scheduled CVE check is not evidence that a security audit has already
run or that opaque binary dependencies have complete coverage.
