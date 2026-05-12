# eci-cli

ECI — Elice Cloud Infrastructure CLI.

A command-line interface for managing compute, network, and storage
resources on [Elice Cloud Infrastructure](https://portal.elice.cloud).

## Install

One line. Picks the right tarball for your OS/arch, verifies its
sha256, unpacks to `/usr/local/eci-cli` (or `~/.local/eci-cli` without
sudo) and symlinks `eci` onto `PATH`.

```bash
curl -fsSL https://raw.githubusercontent.com/elice-dev/eci-cli/main/scripts/install.sh | sh
```

Pin to a specific version:

```bash
VERSION=0.1.0 curl -fsSL https://raw.githubusercontent.com/elice-dev/eci-cli/main/scripts/install.sh | sh
```

Override the install paths:

```bash
INSTALL_DIR=~/bin ROOT_DIR=~/opt/eci-cli \
    curl -fsSL https://raw.githubusercontent.com/elice-dev/eci-cli/main/scripts/install.sh | sh
```

Pre-built binaries are published on
[GitHub Releases](https://github.com/elice-dev/eci-cli/releases) for:

- **macOS** (arm64, Apple Silicon)
- **Linux** (x86_64)

The CLI is a Nuitka `--standalone` directory bundle (AWS CLI v2-style),
warm startup ~85 ms.

### Corporate SSL inspection

The CLI calls `truststore.inject_into_ssl()` at startup so it trusts
whatever root CAs are installed in the OS trust store (Keychain on
macOS, `ca-certificates` on Linux). `eci config verify` works behind
corporate SSL inspection (Netskope, Zscaler, etc.) without extra setup.

## Configure

Set up API credentials and a default zone interactively:

```bash
eci config init
```

Config is stored at `~/.eci/config.yaml` with mode `0600`. Environment
variables override the file:

| Variable           | Purpose                                    |
| ------------------ | ------------------------------------------ |
| `ECI_API_ENDPOINT` | API base URL                               |
| `ECI_API_TOKEN`    | Bearer token                               |
| `ECI_ZONE_ID`      | Default zone UUID                          |
| `ECI_CONFIG`       | Override the config file path              |
| `ECI_DEBUG`        | Print resolver/internal warnings to stderr |

You can also edit values one at a time:

```bash
eci config set api_token <TOKEN>
eci config show
eci config verify          # auth + zone + vm-spec references resolve
```

For secrets, read the value from stdin (keeps the token out of shell
history / ps / CI logs):

```bash
pbpaste | eci config set api_token -
echo "$ECI_TOKEN" | eci config set api_token -
```

## Usage

All `list`/`get` commands accept `--format {table,json,csv}` and
`--query col1,col2`. UUIDs and names are interchangeable wherever a
resource is referenced.

### Compute

```bash
# Easiest first launch — everything else is prompted with defaults
eci compute vm launch

# Fully non-interactive (recommended for scripts / AI agents)
eci compute vm launch \
  --name demo \
  --instance-type C-2 \
  --image 'Ubuntu 24.04 LTS (Standard)' \
  --size-gib 20 \
  --password 'Vk7m@p2qLn5!'

# GPU instance — defaults auto-pick the AI/GPU image (NVIDIA drivers + CUDA)
eci compute vm launch --name ml-1 --instance-type G-NHHS-80 --password '...'

# Reuse a saved spec
eci vm-spec save default --instance-type C-2 --image ubuntu --size-gib 20 --subnet default
eci compute vm launch --password '...'   # auto-applies 'default' spec

# Lifecycle
eci compute vm                       # list
eci compute vm demo                  # show
eci compute vm start demo
eci compute vm stop demo
eci compute vm delete demo           # interactive: prompts about attached resources
eci compute vm delete demo --cascade -y   # non-interactive cascade delete

# SSH
eci compute ssh demo
eci compute ssh demo echo hello      # remote command
eci compute ssh demo -- -L 8080:localhost:8080   # extra ssh args after `--`
```

### Network

```bash
eci network vnet create --name main --cidr 10.0.0.0/16
eci network subnet create --name s --network main --gateway 10.0.0.1
eci network nic create --name n --subnet s
eci network ip create --pricing "Public IP"
eci network ip attach 1.2.3.4 --nic n
```

### Storage

```bash
eci storage block create --name data --size-gib 100 --pricing "Block Storage"
eci storage block attach data --vm demo
eci storage block snapshot create --name daily --block data

eci storage object create --name bucket --size-gib 500
eci storage pfs create --name fs --size-gib 1000
```

### Output formats

```bash
eci compute vm --format json
eci compute vm --format csv --query name,status,instance_type
eci compute vm demo --format json --query name,zone     # zone_id auto-resolved
```

When JSON format is used without `--query`, `*_id` fields are resolved
to names (`zone_id` → `zone`, etc.) where possible.

### Run a single command against a different zone

```bash
eci --zone kr-north compute vm
```

## Reporting issues

Bug reports and feature requests on
[GitHub Issues](https://github.com/elice-dev/eci-cli/issues).
