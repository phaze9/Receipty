#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"
export SWIFTPM_MODULECACHE_OVERRIDE="$SCRIPT_DIR/.build/module-cache"
export CLANG_MODULE_CACHE_PATH="$SCRIPT_DIR/.build/clang-module-cache"
swift build -c release
APP="$SCRIPT_DIR/build/ReceiptyPhotosHelper.app"
mkdir -p "$APP/Contents/MacOS"
cp "$SCRIPT_DIR/.build/release/ReceiptyPhotosHelper" "$APP/Contents/MacOS/ReceiptyPhotosHelper"
cp "$SCRIPT_DIR/Info.plist" "$APP/Contents/Info.plist"
codesign --force --deep --sign - --entitlements "$SCRIPT_DIR/ReceiptyPhotosHelper.entitlements" "$APP"
printf '%s\n' "$APP"

