#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
readonly VERSION="${TUESDAY_VERSION:-1.0.0}"
readonly ARCH="all"
readonly DIST_DIR="${SCRIPT_DIR}/dist"
readonly STAGING="${SCRIPT_DIR}/build/tuesday-desktop_${VERSION}_${ARCH}"
readonly PACKAGE="${DIST_DIR}/tuesday-desktop_${VERSION}_${ARCH}.deb"
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1786982400}"

command -v dpkg-deb >/dev/null 2>&1 || {
    echo "dpkg-deb is required (package: dpkg-dev)" >&2
    exit 127
}

rm -rf -- "${STAGING}"
install -d "${STAGING}/DEBIAN" \
    "${STAGING}/usr/bin" \
    "${STAGING}/usr/share/applications" \
    "${STAGING}/usr/share/icons/hicolor/scalable/apps" \
    "${STAGING}/usr/share/doc/tuesday-desktop"

sed -e "s/@VERSION@/${VERSION}/g" "${SCRIPT_DIR}/src/tuesday-desktop" \
    > "${STAGING}/usr/bin/tuesday-desktop"
chmod 0755 "${STAGING}/usr/bin/tuesday-desktop"
install -m 0644 "${SCRIPT_DIR}/assets/ai.tuesday.Tuesday.desktop" \
    "${STAGING}/usr/share/applications/ai.tuesday.Tuesday.desktop"
install -m 0644 "${PROJECT_ROOT}/services/api/app/static/icons/tuesday.svg" \
    "${STAGING}/usr/share/icons/hicolor/scalable/apps/ai.tuesday.Tuesday.svg"
install -m 0644 "${SCRIPT_DIR}/README.md" "${STAGING}/usr/share/doc/tuesday-desktop/README.md"

sed -e "s/@VERSION@/${VERSION}/g" "${SCRIPT_DIR}/debian/control.in" > "${STAGING}/DEBIAN/control"
find "${STAGING}" -type d -exec chmod 0755 {} +
find "${STAGING}" -exec touch --date="@${SOURCE_DATE_EPOCH}" {} +
mkdir -p "${DIST_DIR}"
dpkg-deb --root-owner-group --build "${STAGING}" "${PACKAGE}"
(
    cd "${DIST_DIR}"
    sha256sum "$(basename "${PACKAGE}")" > "$(basename "${PACKAGE}").sha256"
)
echo "Built ${PACKAGE}"
