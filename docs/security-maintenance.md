# Dependency security maintenance

Reviewed 19 October 2026 against the 12 October baseline. Version matches,
reachable code, and demonstrated exploitation are different findings. This change
updates reviewed dependencies and backports parser fixes; it is not a complete SBOM
or a guarantee that the app has no vulnerabilities.

## Applied fixes

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

- Build-only `sprintf-js` 1.0.3 / 1.1.3 still matches Moderate
  [CVE-2026-97058 / GHSA-hp3w-g68c-fv3c](https://github.com/advisories/GHSA-hp3w-g68c-fv3c).
  It requires attacker-controlled format strings; inspected agtree error formats
  are static. Audit metadata suggests 1.1.4, but the npm registry returns 404 for
  that release and OSV reports no published fix. No nonexistent-version override
  or semantically different formatter was substituted.
- Glean 69.0.0's license inventory includes `idna` 0.3.0
  ([CVE-2024-12224](https://rustsec.org/advisories/RUSTSEC-2024-0421.html), recommend
  idna ≥1.0.3 / url ≥2.5.4), `anyhow` 1.0.95
  ([RUSTSEC-2026-0190](https://rustsec.org/advisories/RUSTSEC-2026-0190.html), fixed
  1.0.103), and unmaintained `bincode` 1.3.3. The inventory aggregates build,
  test, and platform dependencies; linkage and input reachability are unverified.
- Mozilla Application Services 158.0.20260911050252 contains Rust/NSS/NSPR/SQLite
  components without a binary-specific version/feature SBOM. These binaries were
  retained. Changing Swift package metadata cannot patch their embedded code.
- Nested Glean locks and GCDWebServer pins differ across projects. Vendored code,
  Sentry CLI 1.73.0 transitives, and separately vendored BoringSSL remain partly
  unverified. Fuzi's system libxml2 and WKWebView/WebKit depend on device OS updates.
- Native CI requires a regenerated, reviewed michft dependency snapshot matching
  the new Swift pins. Publishing the private local cache contents as a public
  release asset remains a separate action; an old snapshot must not be accepted.

Previously installed apps require a patched rebuild and installation to receive
these changes. This PR does not establish the version currently installed on a
device or close the opaque-binary coverage gaps.
