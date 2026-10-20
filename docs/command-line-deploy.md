# Deploy FFox fork dev from Terminal

From this repo directory on the Mac:

```sh
./scripts/deploy-device.py           # deadbeef7 iPhone
./scripts/deploy-device.py deadbeef6 # iPad
./scripts/deploy-device.py Lois-iPad # Lois's iPad (explicit target)
./scripts/deploy-device.py both      # deadbeef7, then deadbeef6; excludes Lois-iPad
```

The script builds the current working copy, including uncommitted edits. It rebuilds
the bundled JavaScript and YouTube filters, regenerates the isolated Personal Team
project, builds and signs with Xcode, verifies the app signature and provisioning
profile, installs over the existing app, and launches it. It does not uninstall the
app, so its data is retained. Each device gets a destination-specific build; the
second build reuses Xcode's incremental build cache. A failure stops the command
with a nonzero exit code; any earlier successful device deployment remains installed.
An explicit iOS `Locked` launch refusal after successful installation is deferred
verification: the update succeeded, and `both` continues to the other device.

"Update" means updating the installed app from local code. Source pulls, dependency
upgrades, and new ad-blocking rules are separate tasks. The command does not fetch
or merge upstream source. Xcode package updates and automatic resolution are disabled;
the build uses pinned versions from the resolved file and the prepared local package
cache. Restore that cache before deploying. See [fork setup and limitations](iphone-fork.md).

## Prerequisites

- Complete this checkout's existing [setup](iphone-fork.md#setup-and-installation-status):
  Xcode, Python 3, pnpm/Node, installed JS dependencies, Nimbus bootstrap, and SwiftLint.
  If JS dependencies are missing, run `pnpm install --frozen-lockfile` first.
  Prepare the pinned Swift package cache at `.build/SourcePackages` first.
- Select the full Xcode installation with `xcode-select`; accept its license and
  first-launch setup. Sign into the signing Apple account in Xcode Settings.
- Connect and unlock the chosen device, pair/trust the Mac, and enable Developer Mode.
  Check visibility with `xcrun devicectl list devices`.
- Approve the pinned `ModifiedCopyMacros` package in Xcode. If you have reviewed and
  trust its source, the existing CLI workaround is
  `./scripts/deploy-device.py deadbeef7 --skip-macro-validation`.
- Keep internet available for Apple signing and device verification.

Defaults match this fork: team `PP97C35JA7`, bundle `net.mich431.ffoxfork.dev`, and
the known UDIDs of deadbeef7/deadbeef6/Lois-iPad. `Lois-iPad` maps to
`00008132-000471C02620C01C`; `both` still selects only deadbeef7/deadbeef6. Lois is used only when specifically
requested; ordinary weekly runs ignore it.
Override signing explicitly when needed:

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

Locked devices can receive app updates when their trusted connection remains
available, as verified on both deadbeef devices. iOS can still require unlocking
for pairing, trust or restoring a connection. For new wired connections while
locked, Apple's optional **Settings > Privacy & Security > Wired Accessories >
Always Allow** setting permits accessories to connect while locked; it broadens
accessory access. See [Apple's accessory settings](https://support.apple.com/en-us/111806).
This setting does not make the foreground launch verified.

If installation succeeds but iOS reports `Locked` for launch, the script reports
installation success with launch deferred, then continues the next target. Open
FFox after unlocking for launch/UI verification. Other launch errors still fail.
For those errors, unlock the device and check Developer Mode. For an untrusted-developer popup, open
Settings > General > VPN & Device Management > Developer App > Trust/Verify, with
internet connected. Then open FFox fork dev. The script cannot accept device trust
prompts for you.

## Checks

```sh
python3 -m unittest scripts/test_deploy_device.py scripts/test_prepare_personal_device.py
```

Deployment tests mock Apple tools; they do not build or install on hardware.
