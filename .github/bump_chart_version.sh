#!/bin/bash
set -euo pipefail

readonly CHART_DIR="${1}"
readonly CHART_YAML_PATH="${CHART_DIR}/Chart.yaml"

echo "Bumping patch version in '${CHART_YAML_PATH}'"

readonly CURRENT_VERSION="$(grep '^version:' "${CHART_YAML_PATH}" | awk '{print $2}')"
readonly MAJOR="$(echo "${CURRENT_VERSION}" | cut -d. -f1)"
readonly MINOR="$(echo "${CURRENT_VERSION}" | cut -d. -f2)"
readonly PATCH="$(echo "${CURRENT_VERSION}" | cut -d. -f3)"
readonly NEW_PATCH="$(expr "${PATCH}" + 1)"

echo "Bumping version '${MAJOR}.${MINOR}.${PATCH}' to '${MAJOR}.${MINOR}.${NEW_PATCH}'"

sed -i "s/^version:.*/version: ${MAJOR}\.${MINOR}\.${NEW_PATCH}/g" "${CHART_YAML_PATH}"
