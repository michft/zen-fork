# michft GitHub builds and releases

Public repository: [michft/zen-fork](https://github.com/michft/zen-fork).
For Apple beta distribution and automatic device updates, see [TestFlight setup](testflight.md).
This repository is independent of Mozilla's GitHub fork network and CI services.
Its initial public commit is a source snapshot with existing licenses and attribution;
the original local JJ history remains available in the local checkout.

## CI scope and runner limits

Only `fork-ci.yml`, `release-ios.yml`, and `testflight.yml` run here. Inherited Mozilla workflow
automation is removed and disabled in GitHub. CODEOWNERS is `@michft`; issue and
PR templates address this fork. CI opens no upstream PRs, comments, review requests,
or tickets and invokes no Mozilla Taskcluster/Bitrise jobs.

Script tests use one Ubuntu runner. Native builds use one standard GitHub-hosted
`xcode-27` ARM runner with Xcode 27.0, a 90-minute timeout, and three-day unsigned
artifact retention. The runner label is GitHub's public-preview image, not a paid
larger runner or self-hosted machine. A universal archive supports iPhone and iPad;
there is no duplicate device matrix. Superseded PR builds cancel automatically.

JavaScript builds use Node 24 with pnpm 11.22.0. Checkout, Node setup, pnpm setup,
and artifact upload actions are pinned to releases using the Node 24 runtime.
Automatic package-manager caching is disabled; the dependency snapshot remains
the explicit native build cache.

See [GitHub's supported runner labels](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run)
and [Xcode 27 preview announcement](https://github.com/actions/runner-images/issues/14404).

## Dependencies without upstream build downloads

`ci/dependencies.json` pins a public asset in this repository's
`build-deps-2026-10-06` dependency release, including its SHA-256. It contains existing
public Swift package sources/binary caches, Nimbus generator, and SwiftLint. License
notices remain with their packages. It contains no application archive, provisioning
profile, P12, signing key, or keychain. The snapshot is approximately 1.3GB compressed.

CI downloads only the michft snapshot, checks its SHA-256, verifies manifest hashes
and checkout commits, then relocates cached paths. Swift package automatic resolution
and updates are disabled. Nimbus generation runs locally with the cached binary;
there is no Mozilla bootstrap/download step. JavaScript packages and Glean parser
dependencies use their ordinary npm/PyPI registries; GitHub Actions and Node tooling
come from GitHub. These steps do not use Mozilla-hosted resources.

The dependency asset must be published before native CI can pass. CI fails clearly
when it is absent or mismatched; it does not silently download from upstream.
Refresh the snapshot deliberately when changing any pinned Swift manifest/lock:

```sh
python3 scripts/package-ci-dependencies.py --output /tmp/ffox-ci-dependencies-YYYYMMDD.tar.gz
```

Audit the exact payload before public upload. Preserve licenses, publish under a
new `build-deps-YYYY-MM-DD` tag in michft/zen-fork, and update `ci/dependencies.json`
with the new name/hash. Cache archives stay outside tracked source. Restoration
requires Python 3.12+ and empty cache destinations.

## Unsigned PR builds

Pull requests, pushes to `main`, and manual CI runs execute focused script tests,
then build an isolated optimized Release configuration. The generated project
retains this fork's app-only capabilities, minimal entitlements, and app-local data
storage. Debug device deployment remains available through the existing script.
Generated Release projects omit the inherited modified-file SwiftLint build phase,
which scans the whole tree on clean checkouts. Debug linting remains unchanged.

The uploaded `universal-unsigned-*` artifact contains:

- `FFox-VERSION-unsigned-ios-ipados.zip`: app requiring signing before installation.
- `SHA256SUMS` and sanitized `build-info.json`.

PR jobs receive no Apple signing secrets and use a read-only GitHub token. Archives,
dependency caches, provisioning profiles, keychains, and signing files are not uploaded
as build artifacts.

## Signed release setup

The `ios-release` GitHub environment permits `main` and `ffox-v*` tags. Add these
environment secrets through GitHub Settings > Environments > ios-release:

| Secret | Value |
| --- | --- |
| `IOS_CERTIFICATE_P12_BASE64` | Base64 of one exported Apple signing identity, including its private key |
| `IOS_CERTIFICATE_PASSWORD` | Password protecting that P12 |
| `IOS_PROVISION_PROFILE_BASE64` | Base64 of matching development or ad hoc provisioning profile |

Keep files/passwords private. Upload files directly as GitHub environment secrets,
never in an issue, PR, release asset, or tracked source. Example for an existing P12:

```sh
base64 -i /private/path/signing.p12 | gh secret set IOS_CERTIFICATE_P12_BASE64 --env ios-release --repo michft/zen-fork
gh secret set IOS_CERTIFICATE_PASSWORD --env ios-release --repo michft/zen-fork
base64 -i /private/path/profile.mobileprovision | gh secret set IOS_PROVISION_PROFILE_BASE64 --env ios-release --repo michft/zen-fork
```

The workflow creates a temporary keychain, imports one identity, validates profile
team/bundle coverage/expiry/certificate, and signs the app target manually. It makes
no Apple account/provisioning update requests. Its cleanup restores keychain search
paths and removes signing files, installed profiles, and temporary keychain even on
failure. Signing secrets are not populated by this PR.

Optional repository/environment variables:

| Variable | Default |
| --- | --- |
| `IOS_TEAM_ID` | `PP97C35JA7` |
| `IOS_BUNDLE_ID` | `net.mich431.ffoxfork.dev` |
| `IOS_EXPORT_METHOD` | `debugging` |

`debugging` uses an Apple Development identity/profile, registered devices, and
Developer Mode. `release-testing` requires a matching Apple Distribution identity
and ad hoc profile. Both exports are limited to registered devices. A public GitHub
download does not make an IPA installable on every iPhone/iPad. App Store/TestFlight
submission is a separate distribution operation.

A signed IPA necessarily embeds its provisioning profile, including registered-device
UDIDs and public certificate/account metadata. Publishing the signed release publishes
that metadata. Choose profile devices deliberately. Never include the private key or
P12 in release assets. Actual certificate expiry may be earlier than profile expiry;
re-sign before the earlier date. The helper's metadata reports profile expiry.

## Tagging and publishing

Merge the release CI PR first. Update `VERSION` and `CHANGELOG.md` through a PR for
each fork release. `VERSION` is numeric `MAJOR.MINOR.PATCH`; it is separate from
upstream Firefox version history.

Run **michft iOS and iPadOS release** from `main`, supplying the committed version:

```sh
gh workflow run release-ios.yml --ref main -f version=0.1.0 --repo michft/zen-fork
```

The workflow verifies main ancestry, builds/signs/verifies the universal IPA, then
creates `ffox-vVERSION` at that exact commit and publishes the GitHub Release.
Failed builds do not create a new tag/release. Existing tags must point to the same
commit; they are never retargeted. Pushing an existing main-derived `ffox-vVERSION`
tag triggers the same workflow. Manual runs publish directly because tags made with
`GITHUB_TOKEN` do not trigger a second workflow.

Public app assets are `FFox-VERSION-ios-ipados.ipa`, `SHA256SUMS`, and sanitized
`build-info.json`. One IPA serves both iOS and iPadOS; validate real-device behavior
on both device families before calling a release production-ready.

## Local checks

```sh
python3 -m unittest scripts/test_prepare_ci_dependencies.py scripts/test_release_ios.py scripts/test_prepare_personal_device.py scripts/test_deploy_device.py
pnpm install --frozen-lockfile --lockfile-only
python3 scripts/release-ios.py --version 0.1.0 --build-number 1 --output .build/unsigned-release --unsigned
```

Run the archive command only after restoring the pinned tools/cache and copying
`scripts/nimbus-fml-offline.sh` to `firefox-ios/bin/nimbus-fml.sh`, as the workflows do.
