# Changelog

## Unreleased

- Add App Store Connect exports and michft-only TestFlight upload CI.
- Replace identified private UIKit/WebKit API access with public APIs.
- Use continuous 20pt corners for tab previews instead of querying private hardware geometry.
- Add michft-only public CI and universal unsigned iPhone/iPad build artifacts.
- Add paid-team manual signing and `ffox-vMAJOR.MINOR.PATCH` GitHub Releases.
- Restore pinned build dependencies from michft assets without upstream build downloads.
- Remove inherited Mozilla workflow automation and review ownership.
- Add isolated optimized Release configuration while retaining Debug device deployment.
- Use Node 24 for CI build tools and pinned JavaScript actions.

The initial fork release version is tracked in `VERSION`; no app release has been
published by this change. Upstream Firefox version history remains separate.
