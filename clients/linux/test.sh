#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly TEMP_DIR="$(mktemp -d -t tuesday-linux-test.XXXXXX)"
trap 'rm -rf -- "${TEMP_DIR}"' EXIT
export XDG_CONFIG_HOME="${TEMP_DIR}/config"

"${SCRIPT_DIR}/src/tuesday-desktop" --configure https://tuesday.example
test "$(cat "${XDG_CONFIG_HOME}/tuesday/backend-url")" = "https://tuesday.example"
test "$(stat -c '%a' "${XDG_CONFIG_HOME}/tuesday/backend-url")" = "600"

if "${SCRIPT_DIR}/src/tuesday-desktop" --configure http://tuesday.example; then
    echo "HTTP URL was incorrectly accepted" >&2
    exit 1
fi
if "${SCRIPT_DIR}/src/tuesday-desktop" --configure https://user:pass@tuesday.example; then
    echo "URL credentials were incorrectly accepted" >&2
    exit 1
fi
if "${SCRIPT_DIR}/src/tuesday-desktop" --configure https://tuesday.example/path; then
    echo "URL path was incorrectly accepted" >&2
    exit 1
fi

"${SCRIPT_DIR}/build-deb.sh"
dpkg-deb --info "${SCRIPT_DIR}/dist/tuesday-desktop_1.0.0_all.deb" >/dev/null
(
    cd "${SCRIPT_DIR}/dist"
    sha256sum --check tuesday-desktop_1.0.0_all.deb.sha256
)
echo "Linux client tests passed"
