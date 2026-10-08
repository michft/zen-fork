# Glossary

- **FFox fork dev**: This fork's existing application name and behavior.
- **Fork version**: Numeric `MAJOR.MINOR.PATCH` in `VERSION`, used for public artifacts
  and `ffox-v` release tags. Separate from upstream Firefox version history.
- **Universal app**: One archive/IPA supporting iPhone (iOS) and iPad (iPadOS).
- **Unsigned build**: ZIP containing an app requiring signing before device installation.
- **Development IPA**: Signed `debugging` export requiring registered devices and Developer Mode.
- **Ad hoc IPA**: Signed `release-testing` export requiring registered devices and
  matching distribution certificate/profile.
- **Dependency snapshot**: Immutable, checked CI cache hosted by michft, containing
  public dependency sources, binary artifacts, and build tools; no signing credentials.
- **Signing expiry**: Earlier of actual signing certificate and provisioning profile expiry.
