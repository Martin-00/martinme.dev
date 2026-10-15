#!/usr/bin/env bash
# Build cartogram-cpp (Gastner lab, AGPL-3.0) locally. It runs offline as a tool; nothing of it ships with the site.
set -euo pipefail
CACHE_DIR="${CACHE_DIR:-$HOME/.cache/martinme-cartogram}"
REPO="$CACHE_DIR/cartogram-cpp"
COMMIT="9200b14"  # the version this map was built with

mkdir -p "$CACHE_DIR"
[ -d "$REPO" ] || git clone https://github.com/mgastner/cartogram-cpp.git "$REPO"
cd "$REPO"
git fetch --quiet --depth 1 origin "$COMMIT" 2>/dev/null || true

# Patch: the engine raises every target area below 0.01% of the total to that floor. That suits
# country maps, but would inflate 1,184 of Mexico's 2,469 municipios (11% of the map instead of 4.67%).
# 1e-7 puts the floor at ~13 people, below Mexico's smallest municipio (81 people), so nothing is inflated.
sed -i '' 's/constexpr double small_area_threshold_frac = 0.0001;/constexpr double small_area_threshold_frac = 1e-7;/' include/constants.hpp
# Patch: allow up to 400 integration rounds (default 100). Mexico's density range needs more rounds
# to reach the 1% area-error target; each round still shrinks the worst error by about a third.
sed -i '' 's/constexpr unsigned int max_integrations = 100;/constexpr unsigned int max_integrations = 400;/' include/constants.hpp

python3 -m venv .venv
.venv/bin/pip install -q -U -r requirements.txt
export PATH="$PWD/.venv/bin:$PATH"
conan remote update conancenter --url=https://center2.conan.io
conan profile detect 2>/dev/null || true
# Conan 2.16 predates Apple Clang 21 (Xcode 26); teach it the version.
SETTINGS="$HOME/.conan2/settings_user.yml"
grep -q '"21"' "$SETTINGS" 2>/dev/null || printf 'compiler:\n  apple-clang:\n    version: ["21", "21.0"]\n' >> "$SETTINGS"
conan install . --build=missing -s build_type=Release -s compiler.cppstd=20
cmake -B build/Release -S . -DCMAKE_TOOLCHAIN_FILE=build/Release/generators/conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Release
cmake --build build/Release -j"$(sysctl -n hw.ncpu)" --target cartogram
echo "engine ready: $REPO/build/Release/cartogram"
