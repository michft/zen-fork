#!/bin/bash
set -euo pipefail

cd "${SOURCE_ROOT:?SOURCE_ROOT required}"
export MOZ_APPSERVICES_MODULE=MozillaAppServices
binary="build/nimbus/158.20260911050252/bin/nimbus-fml"
test -x "$binary" || { echo "Restore michft CI dependency snapshot before building." >&2; exit 1; }
case "${CONFIGURATION:-Debug}" in
    Debug|Fennec_Testing|Fennec_Enterprise) channel=developer ;;
    FirefoxBeta|FirefoxStaging) channel=beta ;;
    Firefox|Release) channel=release ;;
    *) echo "Unsupported Nimbus build configuration." >&2; exit 1 ;;
esac
mkdir -p Client/Generated build/nimbus/fml-cache
"$binary" validate --cache-dir build/nimbus/fml-cache nimbus.fml.yaml
for manifest in nimbus.fml.yaml nimbus-features/messaging/messaging.fml.yaml; do
    "$binary" generate --channel "$channel" --language swift \
        --cache-dir build/nimbus/fml-cache "$manifest" Client/Generated
done
