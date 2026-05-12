#!/bin/sh
# Install script for the ECI (Elice Cloud Infrastructure) CLI.
#
# Usage:
#   # Latest release from GitHub:
#   curl -fsSL https://raw.githubusercontent.com/elice-dev/eci-cli/main/scripts/install.sh | sh
#
#   # From a local build (after `make build-standalone`):
#   sh scripts/install.sh --from dist/entry.dist
#
# Environment variables:
#   VERSION       Specific version to install (e.g., "0.1.0"). Defaults to latest.
#   INSTALL_DIR   Directory to symlink the launcher into. Defaults to /usr/local/bin
#                 or ~/.local/bin if /usr/local/bin is not writable.
#   ROOT_DIR      Directory that holds the unpacked bundle. Defaults to /usr/local/eci-cli
#                 or ~/.local/eci-cli if /usr/local is not writable.
#   GITHUB_REPO   Override the source repo (default: elice-dev/eci-cli).

set -eu

BINARY_NAME="eci"
GITHUB_REPO="${GITHUB_REPO:-elice-dev/eci-cli}"
RELEASE_BASE="https://github.com/${GITHUB_REPO}/releases/download"
GITHUB_API="https://api.github.com/repos/${GITHUB_REPO}"
FROM_DIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --from)
      FROM_DIR="${2:-}"
      if [ -z "$FROM_DIR" ]; then
        printf "Error: --from requires a directory path\n" >&2
        exit 1
      fi
      shift 2
      ;;
    -h | --help)
      sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      printf "Error: unknown option: %s\n" "$1" >&2
      exit 1
      ;;
  esac
done

detect_os() {
  case "$(uname -s)" in
    Darwin) echo "darwin" ;;
    Linux) echo "linux" ;;
    *)
      printf "Error: unsupported OS: %s\n" "$(uname -s)" >&2
      exit 1
      ;;
  esac
}

detect_arch() {
  case "$(uname -m)" in
    x86_64 | amd64) echo "x86_64" ;;
    aarch64 | arm64) echo "arm64" ;;
    *)
      printf "Error: unsupported architecture: %s\n" "$(uname -m)" >&2
      exit 1
      ;;
  esac
}

detect_install_dir() {
  if [ -n "${INSTALL_DIR:-}" ]; then
    echo "$INSTALL_DIR"
    return
  fi
  if [ -d /usr/local/bin ] && [ -w /usr/local/bin ]; then
    echo "/usr/local/bin"
  else
    echo "$HOME/.local/bin"
  fi
}

detect_root_dir() {
  if [ -n "${ROOT_DIR:-}" ]; then
    echo "$ROOT_DIR"
    return
  fi
  if [ -d /usr/local ] && [ -w /usr/local ]; then
    echo "/usr/local/eci-cli"
  else
    echo "$HOME/.local/eci-cli"
  fi
}

resolve_version() {
  if [ -n "${VERSION:-}" ]; then
    echo "$VERSION"
    return
  fi
  tag=$(curl -fsSL "${GITHUB_API}/releases/latest" |
    grep '"tag_name"' |
    head -1 |
    sed 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/')
  if [ -z "$tag" ]; then
    printf "Error: could not determine latest version. Set VERSION explicitly.\n" >&2
    exit 1
  fi
  echo "$tag"
}

verify_checksum() {
  file="$1"
  expected="$2"
  if command -v sha256sum >/dev/null 2>&1; then
    actual="$(sha256sum "$file" | cut -d' ' -f1)"
  elif command -v shasum >/dev/null 2>&1; then
    actual="$(shasum -a 256 "$file" | cut -d' ' -f1)"
  else
    printf "Warning: neither sha256sum nor shasum found, skipping verification\n" >&2
    return 0
  fi
  if [ "$actual" != "$expected" ]; then
    printf "Error: checksum mismatch.\n  expected: %s\n  actual:   %s\n" "$expected" "$actual" >&2
    exit 1
  fi
}

main() {
  os="$(detect_os)"
  arch="$(detect_arch)"
  install_dir="$(detect_install_dir)"
  root_dir="$(detect_root_dir)"

  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' EXIT

  if [ -n "$FROM_DIR" ]; then
    if [ ! -x "${FROM_DIR}/${BINARY_NAME}" ]; then
      printf "Error: %s/%s not found or not executable\n" "$FROM_DIR" "$BINARY_NAME" >&2
      exit 1
    fi
    printf "Installing %s from %s (%s/%s)\n" "$BINARY_NAME" "$FROM_DIR" "$os" "$arch"
    printf "  bundle: %s\n" "$root_dir"
    printf "  launcher: %s/%s\n" "$install_dir" "$BINARY_NAME"

    bundle_dir="${tmpdir}/bundle"
    cp -R "$FROM_DIR" "$bundle_dir"
  else
    version="$(resolve_version)"
    asset="${BINARY_NAME}-${os}-${arch}-${version}.tar.gz"
    url="${RELEASE_BASE}/v${version}/${asset}"

    printf "Installing %s v%s (%s/%s)\n" "$BINARY_NAME" "$version" "$os" "$arch"
    printf "  bundle: %s\n" "$root_dir"
    printf "  launcher: %s/%s\n" "$install_dir" "$BINARY_NAME"

    printf "Downloading...\n"
    curl -fsSL -o "${tmpdir}/${asset}" "$url"
    curl -fsSL -o "${tmpdir}/checksums.txt" "${RELEASE_BASE}/v${version}/checksums.txt"

    printf "Verifying checksum...\n"
    expected="$(grep "${asset}" "${tmpdir}/checksums.txt" | awk '{print $1}')"
    if [ -z "$expected" ]; then
      printf "Error: checksum not found for %s in checksums.txt\n" "$asset" >&2
      exit 1
    fi
    verify_checksum "${tmpdir}/${asset}" "$expected"

    printf "Extracting...\n"
    tar xzf "${tmpdir}/${asset}" -C "$tmpdir"

    bundle_dir="${tmpdir}/${BINARY_NAME}-${os}-${arch}-${version}"
    if [ ! -d "$bundle_dir" ]; then
      bundle_dir="$(find "$tmpdir" -mindepth 1 -maxdepth 1 -type d | head -1)"
    fi
  fi

  if [ -d "$root_dir" ]; then
    if [ -w "$(dirname "$root_dir")" ]; then
      rm -rf "$root_dir"
    else
      sudo rm -rf "$root_dir"
    fi
  fi

  if [ -w "$(dirname "$root_dir")" ]; then
    mv "$bundle_dir" "$root_dir"
  else
    sudo mv "$bundle_dir" "$root_dir"
  fi

  mkdir -p "$install_dir"
  if [ -w "$install_dir" ]; then
    ln -sf "$root_dir/$BINARY_NAME" "$install_dir/$BINARY_NAME"
  else
    sudo ln -sf "$root_dir/$BINARY_NAME" "$install_dir/$BINARY_NAME"
  fi

  printf "\nInstalled %s to %s/%s\n" "$BINARY_NAME" "$install_dir" "$BINARY_NAME"

  case ":${PATH}:" in
    *":${install_dir}:"*) ;;
    *)
      printf "\nWarning: %s is not in PATH.\n" "$install_dir"
      printf "Add this to your shell rc:\n"
      printf "  export PATH=\"%s:\$PATH\"\n" "$install_dir"
      ;;
  esac

  printf "\nGet started:\n"
  printf "  %s config init\n" "$BINARY_NAME"
  printf "  %s --help\n" "$BINARY_NAME"
}

main
