#!/usr/bin/env bash
# Release a new Speasy version.
#
# Updates CITATION.cff (version + date-released), commits, creates an
# annotated git tag, and pushes both to origin. The build backend
# (uv-dynamic-versioning) resolves the package version from the tag, so
# no other file needs touching.
#
# Usage: scripts/release.sh 1.8.0
#
# Note: pass the version WITHOUT a leading `v`. The tag created will be
# `v1.8.0` to match historical practice.

set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <version>   (e.g. 1.8.0, no leading v)" >&2
    exit 1
fi

VERSION="$1"
TAG="v${VERSION}"
TODAY="$(date +%Y-%m-%d)"

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-].+)?$ ]]; then
    echo "ERROR: version '$VERSION' does not look like X.Y.Z" >&2
    exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "ERROR: tag $TAG already exists" >&2
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: working tree is dirty; commit or stash changes first" >&2
    exit 1
fi

# Update CITATION.cff in place.
sed -i.bak -E "s/^version: .*/version: ${VERSION}/" CITATION.cff
sed -i.bak -E "s/^date-released: .*/date-released: ${TODAY}/" CITATION.cff
rm -f CITATION.cff.bak

git add CITATION.cff
git commit -m "Release ${VERSION}"
git tag -a "${TAG}" -m "Release ${VERSION}"

echo
echo "Release ${VERSION} committed and tagged as ${TAG}."
echo "Push with: git push origin main && git push origin ${TAG}"
