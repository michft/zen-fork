# Deploy FFox fork dev from Terminal

From this repo directory on the Mac:

```sh
./scripts/deploy-device.py           # deadbeef7 iPhone
./scripts/deploy-device.py deadbeef6 # iPad
./scripts/deploy-device.py both      # iPhone, then iPad
```

The script builds the current working copy, including uncommitted edits. It rebuilds
the bundled JavaScript and YouTube filters, regenerates the isolated Personal Team
project, builds and signs with Xcode, verifies the app signature and provisioning
profile, installs over the existing app, and launches it. It does not uninstall the
app, so its data is retained. Each device gets a destination-specific build; the
second build reuses Xcode's incremental build cache. A failure stops the command
with a nonzero exit code; any earlier successful device deployment remains installed.

"Update" means updating the installed app from local code. Source pulls, dependency
upgrades, and new ad-blocking rules are separate tasks. The command does not fetch
or merge upstream source. Missing pinned Swift packages may still be downloaded by
Xcode. See [fork setup and limitations](iphone-fork.md).

## Prerequisites

- Complete this checkout's existing [setup](iphone-fork.md#setup-and-installation-status):
  Xcode, Python 3, pnpm/Node, installed JS dependencies, Nimbus bootstrap, and SwiftLint.
  If JS dependencies are missing, run `pnpm install --lockfile=false` first.
- Select the full Xcode installation with `xcode-select`; accept its license and
  first-launch setup. Sign into the signing Apple account in Xcode Settings.
- Connect and unlock the chosen device, pair/trust the Mac, and enable Developer Mode.
  Check visibility with `xcrun devicectl list devices`.
- Approve the pinned `ModifiedCopyMacros` package in Xcode. If you have reviewed and
  trust its source, the existing CLI workaround is
  `./scripts/deploy-device.py deadbeef7 --skip-macro-validation`.
- Keep internet available for Apple signing and device verification.

Defaults match this fork: team `PP97C35JA7`, bundle `net.mich431.ffoxfork.dev`, and
the known UDIDs of deadbeef7/deadbeef6. Override signing explicitly when needed:

```sh
./scripts/deploy-device.py deadbeef7 --team YOURTEAMID --bundle-id net.example.ffoxfork.dev
./scripts/deploy-device.py both --dry-run
```

Changing the bundle ID creates a separate app; use the existing ID to keep its data.
Dry-run prints commands without invoking tools or creating files. Normal execution
uses `.build/personal-device`, `.build/DeviceDerivedData`, and `.build/SourcePackages`.
Only one script instance may run at a time; avoid manual Xcode builds using those
same paths while it runs. Run as your normal Mac user, without `sudo`.

Xcode may reuse a still-valid profile. The script allows provisioning updates as
needed and prints the actual embedded expiry; it does not guarantee a new seven-day
window on every run or remove Personal Team signing limits.

If installation succeeds but launch fails, the script reports that distinction.
Unlock the device and check Developer Mode. For an untrusted-developer popup, open
Settings > General > VPN & Device Management > Developer App > Trust/Verify, with
internet connected. Then open FFox fork dev. The script cannot accept device trust
prompts for you.

## Checks

```sh
python3 -m unittest scripts/test_deploy_device.py scripts/test_prepare_personal_device.py
```

Deployment tests mock Apple tools; they do not build or install on hardware.
