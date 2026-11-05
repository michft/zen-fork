# Dependency security maintenance

Reviewed 19–20 October 2026 against the 12 October baseline. Version matches,
reachable code, and demonstrated exploitation are different findings. This change
updates reviewed dependencies and backports parser fixes; it is not a complete SBOM
or a guarantee that the app has no vulnerabilities.

## Applied fixes

Translation Services also binds page-controlled language strings through
`callAsyncJavaScript(arguments:)`, retaining the isolated `.defaultClient` world.
This closes the source pattern in High
[CVE-2026-103418](https://www.mozilla.org/en-US/security/advisories/mfsa2026-105/);
the upstream 157.1 version label alone did not establish that the fork contained
the fix. The existing service test exercises a real WKWebView with quoted,
backslash-containing and injection-shaped language values.

| Component | Change | Evidence |
| --- | --- | --- |
| Swift Crypto | 3.15.1 → exact 4.5.1, commit `47d3869a7291f085c1fb9fb1e6d3b97a793f45c6`; retain Certificates 1.19.3 and ASN.1 1.7.0 | Critical [CVE-2026-43823 / GHSA-8q93-f6xh-4f6f](https://github.com/apple/swift-crypto/security/advisories/GHSA-8q93-f6xh-4f6f), affected 3.2.0–4.5.0. Certificate decoding uses X509 and the affected RSA implementation. |
| DOMPurify | 3.4.15 bundled / 3.4.14 stale npm lock → 3.4.17 | Low [GHSA-6688-9rhm-gjv2](https://github.com/advisories/GHSA-6688-9rhm-gjv2) and [GHSA-p98j-92pf-mc4p](https://github.com/advisories/GHSA-p98j-92pf-mc4p), fixed 3.4.16. Current string-sanitizing callers lack the `IN_PLACE` precondition. |
| DarkReader | 4.9.89 → 4.9.133 | Low [CVE-2025-68467 / GHSA-x369-mcw8-8rvj](https://github.com/darkreader/darkreader/security/advisories/GHSA-x369-mcw8-8rvj), extension fix 4.9.117. Ordinary npm integration is excluded; this browser integration uses `window.fetch`, with no identified privileged extension fetch path. |
| Build-time js-yaml | 3.14.1 → 3.15.2 through a scoped Scriptlets override | Clears [CVE-2026-84375](https://github.com/advisories/GHSA-2883-xcg3-v3hh), [CVE-2026-59869](https://github.com/advisories/GHSA-52cp-r559-cp3m), [GHSA-5p4m-2wfm-xmqj](https://github.com/advisories/GHSA-5p4m-2wfm-xmqj), [CVE-2026-53550](https://github.com/advisories/GHSA-h67p-54hq-rp68), and [CVE-2025-64718](https://github.com/advisories/GHSA-mh29-5h37-fv8m). Scriptlets 2.5.1 and agtree 4.2.1 remain pinned. |
| Down 0.11.0 / cmark 0.29.0 | Retain Down revision; apply reviewed cmark backports before compilation | [CVE-2023-22486](https://securitylab.github.com/advisories/GHSL-2022-128_cmark/) and [CVE-2023-24824](https://securitylab.github.com/advisories/GHSL-2023-031_cmark/). Patches cover link-openers, emphasis node reparenting, nested-list blank lines, and the required private inline append optimization. |

`pnpm-lock.yaml` is canonical. The stale npm lockfile was removed: its additional
brace-expansion and fast-uri findings were already fixed in the pnpm/installed
graph. Generated JavaScript remains ignored by Git and must be regenerated with
`pnpm run build`; builds must use the frozen pnpm lockfile.

## Weekly review 26 October 2026

| Finding | Component | Classification |
| --- | --- | --- |
| [GHSA-w74x-v6f9-j3xg](https://github.com/advisories/GHSA-w74x-v6f9-j3xg) (Medium 6.1), [GHSA-wjr9-j795-jxcr](https://github.com/advisories/GHSA-wjr9-j795-jxcr) (Medium 4.8), [GHSA-xhq7-xmqj-769h](https://github.com/advisories/GHSA-xhq7-xmqj-769h), [GHSA-333x-w4r6-6crp](https://github.com/advisories/GHSA-333x-w4r6-6crp) (Low 3.7) | Build-only `fast-uri` 3.1.8 via webpack schema-utils → ajv 8 | Fixed: pnpm override to 3.1.9. `scripts/test-fast-uri-security.mjs` resolves the webpack path and fails on 3.1.8. |
| [GHSA-cg2g-xh64-v4q7](https://github.com/advisories/GHSA-cg2g-xh64-v4q7) (Critical, CVSS 4.0 9.2), [GHSA-mrv2-3pqr-j5jr](https://github.com/advisories/GHSA-mrv2-3pqr-j5jr) (High 7.6) | Shipped DOMPurify | Fixed by the existing 3.4.17 pin; callers also lack the `SAFE_FOR_TEMPLATES`, DOM-return, `IN_PLACE` and hook preconditions. |
| CVE-2026-103417, [MFSA 2026-105](https://www.mozilla.org/en-US/security/advisories/mfsa2026-105/) (Moderate) | Firefox for iOS saved-login autofill | Fixed in inherited source: `CredentialAutofillCoordinator` rechecks the selected tab's origin before filling. |
| [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5) (High, CVSS 4.0 8.2) | Build-only `zod` 3.24.4 via agtree 4.2.1 | Unfixed; fix is zod 4.6.6 and agtree 4.3.0 still pins 3.24.4. Only parses this repository's YouTube rules at build time; not shipped. |
| [GHSA-hp3w-g68c-fv3c](https://github.com/advisories/GHSA-hp3w-g68c-fv3c) | Build-only `sprintf-js` | Advisory withdrawn because handling the exception is the application's responsibility; no upstream release. The local precision patch has since been removed: format strings are not attacker-controlled, and the worst case is a failed local build. |

Firefox 158/ESR advisories (MFSA 2026-106 to 2026-116) target Gecko, the desktop PDF
viewer, or Firefox's own OneCRL store; this iOS app uses WebKit and Apple trust
evaluation. Zen Browser's five 2026 advisories affect its desktop updater and UI.
`taskcluster/requirements.txt` certifi/urllib3 advisories apply only to unused
upstream CI tooling. iOS/iPadOS 27.0.1 remains the latest release for both devices.

## App Services SQLite, 31 October 2026

| Finding | Component | Classification |
| --- | --- | --- |
| [CVE-2026-11822 / GHSA-6qj8-gw6p-hc5p](https://github.com/advisories/GHSA-6qj8-gw6p-hc5p) (High, CVSS 4.0 8.5), [CVE-2026-119374 / GHSA-gr85-mf7f-6pq7](https://github.com/advisories/GHSA-gr85-mf7f-6pq7) (8.5), [CVE-2026-119373 / GHSA-mw7g-h5m4-mrxh](https://github.com/advisories/GHSA-mw7g-h5m4-mrxh) (8.5) | SQLite 3.50.2 with FTS5, statically linked into App Services 158.0.20260911050252; Suggest uses FTS5 (`amp_fts`, `fakespot_fts`) | Fixed in fork: SQLite rebuilt as 3.54.1. Exploitation needed a crafted database or `detail=none` table; the Suggest database is app-private. |
| [CVE-2026-119379 / GHSA-6w9f-4x4x-x559](https://github.com/advisories/GHSA-6w9f-4x4x-x559), [CVE-2026-119586 / GHSA-2h5x-4qp8-353h](https://github.com/advisories/GHSA-2h5x-4qp8-353h) (8.5) | SQLite session extension / command-line shell | Not applicable: neither is compiled into or shipped with the app; also fixed by 3.54.1. |
| Same FTS5 CVEs | Glean 69.0.0 dynamic framework, separate SQLite 3.50.2 | Unfixed, not reachable: Glean only creates its `telemetry` table and issues no FTS5 SQL. Needs a glean-swift release with SQLite ≥3.54.0. |

Application Services main still pins `libsqlite3-sys` 0.35.0 (SQLite 3.50.x), so no
upstream release fixes this. `scripts/prepare-appservices-sqlite.py` verifies the
pinned xcframework's per-slice SHA-256, the tracked sqlite.org 3.54.1 amalgamation's
published SHA3-256, and the exact App Services SQLite archive member. It compiles
the amalgamation with libsqlite3-sys 0.35.0's bundled flags plus `unlock_notify`
for each architecture, requires identical compile options (except 3.54's new
`MAX_SCHEMA` default) and a superset of exported symbols, replaces only that
member, and verifies every other archive member is retained. Rebuilding 3.50.2
with the same flags reproduced the shipped object's compile options and exports.
Unknown libraries fail closed; already-patched libraries are accepted.

Device and CI preparation run it with the cmark backports. Run it directly after
resolving or restoring packages for other builds:

```sh
python3 scripts/prepare-appservices-sqlite.py
python3 -m unittest scripts/test_prepare_appservices_sqlite.py
APPSERVICES_SQLITE_INTEGRATION=1 python3 -m unittest scripts/test_prepare_appservices_sqlite.py
```

The integration tests rebuild copies of the real libraries and run SQLite's own
FTS5 negative-rowid regression plus App Services-style `amp_fts` operations under
AddressSanitizer. The same regression overflows the heap on 3.50.2 and returns 56
rows cleanly on 3.54.1. A full App Services source rebuild was not used: its NSS
build step was not permitted in this environment. Retire this replacement when
an App Services release bundles SQLite ≥3.54.0.

## Weekly review 2 November 2026

OSV was queried for every pinned npm, Swift and App Services crate version, not only
advisories changed since the previous run.

| Finding | Component | Classification |
| --- | --- | --- |
| [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249) (CVE-2026-118764, Moderate, CVSS 4.0 6.9) | Build-only `minimatch` 5.1.9 via `glob` 8.1.0, used only by `webpack.config.js` | Fixed: `glob` removed. The config lists each user-script directory with `fs.readdirSync` using glob 8's `en` locale ordering; entry lists and generated bundles are byte-identical. `scripts/test-webpack-entries.mjs` checks ordering, entries and the absent packages. Patterns were repository-controlled, so it was not exploitable. |
| [RUSTSEC-2026-0258](https://rustsec.org/advisories/RUSTSEC-2026-0258.html) (empty DATA frames) | Shipped `h2` 0.3.26 via hyper 0.14.27 / viaduct-hyper | Not applicable: `Viaduct.initialize` selects the hyper backend, but hyper-tls 0.5.0 negotiates no ALPN and viaduct-hyper never forces HTTP/2, so connections stay HTTP/1.1. Fixed only in h2 0.4.16. |
| [CVE-2026-44983 / GHSA-97wc-2hqc-cjgr](https://github.com/advisories/GHSA-97wc-2hqc-cjgr) (High, no fix) | Shipped `smallbitvec` 2.5.1 via dogear 0.5.0 | Not applicable: dogear sizes vectors by bookmark count (`from_elem(entries.len())`); the overflow needs a length near `usize::MAX`. |
| [RUSTSEC-2026-0386](https://rustsec.org/advisories/RUSTSEC-2026-0386.html), [GHSA-rr8g-9fpq-6wmg](https://github.com/advisories/GHSA-rr8g-9fpq-6wmg) (Low) | Shipped `tokio` 1.29.1 | Not applicable: hyper, h2, hyper-tls and viaduct-hyper use neither `AsyncFd` nor broadcast channels. |
| [GHSA-cq8v-f236-94qc](https://github.com/advisories/GHSA-cq8v-f236-94qc) (Low) | Shipped `rand` 0.8.5 | Not applicable: rand's `log` feature is disabled in the iOS graph. |
| [CVE-2024-43806 / GHSA-c827-hfw6-qwvm](https://github.com/advisories/GHSA-c827-hfw6-qwvm) (Moderate) | Shipped `rustix` 0.36.7 | Not applicable: only the `linux_raw` backend is affected; the iOS binary contains the libc backend. |
| [RUSTSEC-2026-0190](https://rustsec.org/advisories/RUSTSEC-2026-0190.html) (Informational) | Shipped `anyhow` 1.0.58 in App Services | Unverified: App Services sources never call `downcast_mut`; other compiled crates were not audited. |

Other matched App Services crates (openssl, zip, zstd, unsafe-libyaml, yaml-rust,
oneshot, cxx, memmap2, instant, number_prefix, basic-toml) are outside the
`megazord_ios` aarch64-apple-ios runtime graph. `zod` 3.24.4 remains unfixed and
build-only (agtree 4.3.0 still pins it). No new Mozilla, Zen or RustSec items; both
default devices run iOS/iPadOS 27.2 (24B119), covering the 27.2 WebKit fixes.

## cmark backports

`scripts/prepare-down-security.py` checks the exact Down Git revision and SHA-256
of each affected source file, stages the two tracked patches, verifies output
hashes, then replaces the three files. Already-patched sources are accepted;
unknown or partially patched sources fail closed. Patches retain upstream
commit links and existing dependency licensing.

CI cache restoration and `prepare-personal-device.py` apply this preparation
before compiling dependencies. A direct original-project or BrowserKit package
build must run it explicitly after restoring/resolving the pinned cache:

```sh
python3 scripts/prepare-down-security.py
python3 -m unittest scripts/test_prepare_down_security.py
DOWN_CMARK_INTEGRATION=1 python3 -m unittest scripts/test_prepare_down_security.py
```

The helper's unit tests run without a native cache. The opt-in integration command
requires Down sources and a C compiler; it compiles the real parser, compares
ordinary Markdown output before/after, and checks bounded regression inputs.
The final backports preserve 11 ordinary Markdown outputs, including Down's own
examples and binding snapshot. Three 20,000-repetition regression cases complete
in under 0.03 seconds each locally; the unpatched blockquote/emphasis case exceeds
the three-second bound. AddressSanitizer and UndefinedBehaviorSanitizer report no
diagnostics on these cases. Apple's two malformed RSA public-key regression tests
also pass with Swift Crypto 4.5.1. These are bounded checks, not exhaustive fuzzing.
Re-review patches and hashes when updating Down; do not bypass a hash failure.

## Remaining findings and coverage gaps

- Glean 69.0.0's source graph contains `idna` 0.3.0 through
  rkv 0.20.0 → url 2.3.1
  ([CVE-2024-12224](https://rustsec.org/advisories/RUSTSEC-2024-0421.html), Moderate;
  recommend idna ≥1.0.3 / url ≥2.5.4). The inspected
  [rkv helper](https://github.com/mozilla/rkv/blob/v0.20.0/src/helpers.rs)
  converts canonical filesystem paths through URL only inside a Windows branch;
  that branch is inactive on iOS and performs no network-origin privilege check.
  The CVE trigger is absent from this inspected iOS path. This is a scoped
  reachability conclusion, not a whole-binary safety claim.
- The cached iOS-arm64 Glean binary independently embeds `anyhow-1.0.95` source
  paths and anyhow symbols. Informational
  [RUSTSEC-2026-0190](https://rustsec.org/advisories/RUSTSEC-2026-0190.html) is fixed
  in 1.0.103 and requires context plus mutable downcasting. The inspected
  [UniFFI 0.31 converter](https://github.com/mozilla/uniffi-rs/blob/v0.31.0/uniffi_core/src/ffi_converter_impls.rs)
  uses owned `downcast`, not `downcast_mut`; the vulnerable trigger across the
  complete binary remains unverified. The binary was not patched. A reproducible
  rebuild requires matching Glean 69 Rust source/Cargo.lock, fixed anyhow source,
  iOS Rust targets and complete offline crate/parser inputs, absent locally.
  Unmaintained bincode and other opaque transitive versions remain coverage gaps.
- Mozilla Application Services 158.0.20260911050252 contains Rust/NSS/NSPR
  components without a binary-specific version/feature SBOM; only its SQLite object
  is replaced (see above). Its source `Cargo.lock` pins `zip` 2.3.0, matching
  [CVE-2026-115905](https://github.com/advisories/GHSA-m665-v7pm-7grj) and related
  advisories, but `zip` is not in the `megazord_ios` runtime graph.
- Nested Glean locks and GCDWebServer pins differ across projects. Vendored code,
  Sentry CLI 1.73.0 transitives, and separately vendored BoringSSL remain partly
  unverified. Fuzi's system libxml2 and WKWebView/WebKit depend on device OS updates.
- Native CI requires a regenerated, reviewed michft dependency snapshot matching
  the new Swift pins. Publishing the private local cache contents as a public
  release asset remains a separate action; an old snapshot must not be accepted.

Deployment evidence must identify the patched build and each device install/launch
result; source fixes alone do not establish that installed apps received them. This PR does not establish the version currently installed on a
device or close the opaque-binary coverage gaps.
