#!/bin/sh
# Install script for the ECI (Elice Cloud Infrastructure) CLI.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/elice-dev/eci-cli/main/scripts/install.sh | sh
#
# Environment variables:
#   VERSION       Specific version to install (e.g., "0.1.0"). Defaults to latest.
#   INSTALL_DIR   Directory to symlink the launcher into. Defaults to /usr/local/bin
#                 or ~/.local/bin if /usr/local/bin is not writable.
#   ROOT_DIR      Directory that holds the unpacked bundle. Defaults to /usr/local/eci-cli
#                 or ~/.local/eci-cli if /usr/local is not writable.

set -eu

BINARY_NAME="eci"
GITHUB_REPO="elice-dev/eci-cli"
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
      sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
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
    x86_64 | amd64)
      # Apple Silicon under Rosetta reports x86_64 here; the arm64-only
      # release would 404. sysctl.proc_translated == 1 means we're translated.
      if [ "$(uname -s)" = "Darwin" ] \
         && [ "$(sysctl -n sysctl.proc_translated 2>/dev/null)" = "1" ]; then
        echo "arm64"
      else
        echo "x86_64"
      fi
      ;;
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

  existing_version=""
  if [ -x "$install_dir/$BINARY_NAME" ]; then
    existing_version="$("$install_dir/$BINARY_NAME" --version 2>/dev/null | awk '{print $NF}')" || existing_version=""
  fi

  if [ -n "$FROM_DIR" ]; then
    if [ ! -x "${FROM_DIR}/${BINARY_NAME}" ]; then
      printf "Error: %s/%s not found or not executable\n" "$FROM_DIR" "$BINARY_NAME" >&2
      exit 1
    fi
    version="local build"
    source_label="$FROM_DIR"
  else
    version="$(resolve_version)"
    source_label="GitHub Releases (v${version})"
  fi

  printf "\n"
  printf "  ECI CLI installer\n"
  if [ -n "$FROM_DIR" ]; then
    printf "  Action:    install (local build)\n"
  elif [ -n "$existing_version" ] && [ "$existing_version" != "$version" ]; then
    printf "  Action:    upgrade %s → %s\n" "$existing_version" "$version"
  elif [ -n "$existing_version" ]; then
    printf "  Action:    reinstall %s\n" "$version"
  else
    printf "  Action:    install %s\n" "$version"
  fi
  printf "  Platform:  %s %s\n" "$os" "$arch"
  printf "  Source:    %s\n" "$source_label"
  printf "  Bundle:    %s\n" "$root_dir"
  printf "  Launcher:  %s/%s\n" "$install_dir" "$BINARY_NAME"
  printf "\n"

  if [ -n "$FROM_DIR" ]; then
    bundle_dir="${tmpdir}/bundle"
    cp -R "$FROM_DIR" "$bundle_dir"
  else
    asset="${BINARY_NAME}-${os}-${arch}-${version}.tar.gz"
    url="${RELEASE_BASE}/${version}/${asset}"

    printf "Downloading...\n"
    # --progress-bar shows a real bar; -fL keeps fail-on-error + follow.
    curl -fL --progress-bar -o "${tmpdir}/${asset}" "$url"
    curl -fsSL -o "${tmpdir}/checksums.txt" "${RELEASE_BASE}/${version}/checksums.txt"

    printf "Verifying...  "
    expected="$(grep "${asset}" "${tmpdir}/checksums.txt" | awk '{print $1}')"
    if [ -z "$expected" ]; then
      printf "\nError: checksum not found for %s in checksums.txt\n" "$asset" >&2
      exit 1
    fi
    verify_checksum "${tmpdir}/${asset}" "$expected"
    printf "✓\n"

    printf "Extracting... "
    tar xzf "${tmpdir}/${asset}" -C "$tmpdir"
    printf "✓\n"

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
    *":${install_dir}:"*)
      ;;
    *)
      profile=""
      # Idempotency marker — match against this instead of $install_dir, which
      # would false-positive on a similar prefix (e.g. ~/.local/bin-old).
      marker="# Added by eci-cli installer"

      case "${SHELL:-}" in
        */zsh)  profile="$HOME/.zshrc" ;;
        */bash)
          # macOS Terminal.app reads ~/.bash_profile (login shell); Linux reads ~/.bashrc.
          if [ "$os" = "darwin" ]; then
            profile="$HOME/.bash_profile"
          else
            profile="$HOME/.bashrc"
          fi
          ;;
        */fish) profile="$HOME/.config/fish/config.fish" ;;
      esac

      if [ -n "$profile" ]; then
        mkdir -p "$(dirname "$profile")"
        touch "$profile"
        if grep -qsF "$marker" "$profile" 2>/dev/null; then
          printf "\nPATH already configured in %s.\n" "$profile"
        else
          if [ "$profile" = "$HOME/.config/fish/config.fish" ]; then
            {
              printf "\n%s\n" "$marker"
              printf "set -gx PATH %s \$PATH\n" "$install_dir"
            } >> "$profile"
          else
            {
              printf "\n%s\n" "$marker"
              printf 'export PATH="%s:$PATH"\n' "$install_dir"
            } >> "$profile"
          fi
          printf "\nAdded %s to PATH in %s\n" "$install_dir" "$profile"
        fi
        printf "Restart your shell or run: source %s\n" "$profile"
      else
        printf "\nWarning: %s is not in PATH.\n" "$install_dir"
        printf "Add this to your shell rc:\n"
        printf "  export PATH=\"%s:\$PATH\"\n" "$install_dir"
      fi
      ;;
  esac

  printf "\nRun '%s --help' to get started.\n" "$BINARY_NAME"
}

main
