# Changelog

## Unreleased

- Override build-only fast-uri to 3.1.9 and record the 26 October weekly security review.
- Rebuild App Services' bundled SQLite as 3.54.1 to fix FTS5 heap overflows (CVE-2026-11822, CVE-2026-119373, CVE-2026-119374).
- Continue updates across locked-device launch refusals; keep Lois-iPad an explicit target.
- Bind translation language arguments safely, backport formatter precision limits, and require weekly patch/build/device deployment.
- Update reviewed JavaScript and Swift security dependencies; apply guarded cmark backports during dependency preparation.
- Add michft-only public CI and universal unsigned iPhone/iPad build artifacts.
- Add paid-team manual signing and `ffox-vMAJOR.MINOR.PATCH` GitHub Releases.
- Restore pinned build dependencies from michft assets without upstream build downloads.
- Remove inherited Mozilla workflow automation and review ownership.
- Add isolated optimized Release configuration while retaining Debug device deployment.
- Use Node 24 for CI build tools and pinned JavaScript actions.

The initial fork release version is tracked in `VERSION`; no app release has been
published by this change. Upstream Firefox version history remains separate.
