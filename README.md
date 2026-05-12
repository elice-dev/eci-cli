# eci-cli

ECI is the command-line interface for [Elice Cloud Infrastructure](https://elice.io/ko).
Launch and manage compute, network, and storage resources from your terminal.

> [!IMPORTANT]
> **Preview release.** The CLI is under active development and the
> interface may change before v1. Track or open issues at
> [elice-dev/eci-cli](https://github.com/elice-dev/eci-cli/issues).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/elice-dev/eci-cli/main/scripts/install.sh | sh
```

The installer picks the right tarball for your platform, verifies its
sha256, unpacks the bundle to `/usr/local/eci-cli` (or `~/.local/eci-cli`
if `/usr/local` is not writable) and symlinks `eci` onto your `PATH`.

**Supported platforms**

- macOS (arm64, Apple Silicon)
- Linux (x86_64)

**Pin a version**

```bash
VERSION=0.1.0 curl -fsSL https://raw.githubusercontent.com/elice-dev/eci-cli/main/scripts/install.sh | sh
```

**Choose install paths**

```bash
INSTALL_DIR=~/bin ROOT_DIR=~/opt/eci-cli \
    curl -fsSL https://raw.githubusercontent.com/elice-dev/eci-cli/main/scripts/install.sh | sh
```

The CLI is a Nuitka `--standalone` directory bundle (AWS CLI v2 style)
with a warm startup of about 85 ms. It honors the OS trust store
(Keychain on macOS, `ca-certificates` on Linux), so it works behind
corporate SSL inspection (Netskope, Zscaler, etc.) without extra setup.

## Quick start

```bash
# 1) Authenticate and pick a default zone
eci config init

# 2) Launch your first VM (interactive — every field has a sensible default)
eci compute vm launch

# 3) SSH in
eci compute ssh <vm-name>
```

That's it. The launcher creates the VM, attaches a disk, NIC, and
public IP, starts it, and prints a summary block with the IP and
the SSH command you can copy.

## Configure

```bash
eci config init          # interactive setup
eci config show          # current config
eci config verify        # check that auth + zone resolve correctly
```

Config is stored at `~/.eci/config.yaml` with mode `0600`. Edit values
individually:

```bash
eci config set api_token <TOKEN>
eci config set zone_id auto    # auto-pick if there's only one zone
```

To keep secrets out of shell history / `ps` / CI logs, read the value
from stdin:

```bash
echo "$ECI_TOKEN" | eci config set api_token -
```

Environment variables override the config file:

| Variable           | Purpose                                    |
| ------------------ | ------------------------------------------ |
| `ECI_API_ENDPOINT` | API base URL                               |
| `ECI_API_TOKEN`    | Bearer token                               |
| `ECI_ZONE_ID`      | Default zone UUID                          |
| `ECI_CONFIG`       | Path to the config file                    |
| `ECI_DEBUG`        | Print resolver / internal warnings         |

## Common tasks

UUIDs and names are interchangeable wherever a resource is referenced.
All `list` and `get` commands accept `--format {table,json,csv}` and
`--query col1,col2`.

### Compute

```bash
# Easiest launch — every other field is prompted with a default
eci compute vm launch

# Fully non-interactive (recommended for scripts and CI)
eci compute vm launch \
  --name web-1 \
  --instance-type C-2 \
  --image 'Ubuntu 24.04 LTS (Standard)' \
  --size-gib 20 \
  --password 'Vk7m@p2qLn5!'

# GPU instance — defaults auto-pick the AI/GPU image
eci compute vm launch --name ml-1 --instance-type G-NHHS-80 --password '...'

# Save common launch settings as a 'default' spec; auto-applied next time
eci vm-spec save default \
  --instance-type C-2 --image ubuntu --size-gib 20 --subnet default
eci compute vm launch --password '...'

# Lifecycle
eci compute vm                    # list
eci compute vm web-1              # get one
eci compute vm start web-1
eci compute vm stop web-1
eci compute vm delete web-1       # interactive; prompts about attached disk/NIC/IP
eci compute vm delete web-1 --cascade -y   # non-interactive cascade

# SSH
eci compute ssh web-1
eci compute ssh web-1 echo hello                  # run a remote command
eci compute ssh web-1 -- -L 8080:localhost:8080   # forward extra ssh args
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
eci storage block attach data --vm web-1
eci storage block snapshot create --name daily --block data

eci storage object create --name bucket --size-gib 500
eci storage pfs create --name fs --size-gib 1000
```

## Output formats

```bash
eci compute vm --format json
eci compute vm --format csv --query name,status,instance_type
eci compute vm web-1 --format json --query name,zone     # zone_id auto-resolved
```

When JSON is used without `--query`, `*_id` fields are resolved to
names (e.g. `zone_id` → `zone`) where possible.

## Run a single command in a different zone

```bash
eci --zone kr-central compute vm
```

## Help & feedback

- **Run `eci -h`** for the top-level help, or `-h` on any subcommand.
- **Issues and feature requests**:
  [github.com/elice-dev/eci-cli/issues](https://github.com/elice-dev/eci-cli/issues).
- **Product info**: [elice.io/ko](https://elice.io/ko).
