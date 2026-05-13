# eci-cli

ECI is the command-line interface for [Elice Cloud Infrastructure](https://elice.io/ko).

Launch and manage compute, network, and storage resources from your terminal.

> [!IMPORTANT]
> **Preview release.** Track or open issues at
> [elice-dev/eci-cli](https://github.com/elice-dev/eci-cli/issues).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/elice-dev/eci-cli/main/scripts/install.sh | sh
```

Supported platforms:

- macOS (arm64, Apple Silicon)
- Linux (x86_64)

## Quick start

```bash
eci config init
eci compute vm launch
eci compute ssh <vm-name>
```

## Configure

```bash
eci config set api_token <TOKEN>
eci config verify
```

Read the token from stdin to keep it out of shell history:

```bash
echo "$ECI_TOKEN" | eci config set api_token -
```

Environment variables override the config file: `ECI_API_TOKEN`,
`ECI_ZONE_ID`, `ECI_API_ENDPOINT`.

## Common tasks

```bash
# List VMs
eci compute vm list

# Launch a VM
eci compute vm launch --name vm-1 --instance-type C-4 \
  --image 'Ubuntu 24.04 LTS (Standard)' --size-gib 20 --password '...'

# SSH in, or run a remote command
eci compute ssh vm-1
eci compute ssh vm-1 tail -f /var/log/syslog

# Lifecycle
eci compute vm stop vm-1
eci compute vm start vm-1
eci compute vm delete vm-1 --cascade -y
```

`list` and `get` accept `--format {table,json,csv}` and `--query col1,col2`.

## Other commands

- `eci network` — vnets, subnets, NICs, public IPs
- `eci storage` — block storage, object storage, parallel file system
- `eci vm-spec` — saved launch presets
- `eci instance-type`, `eci image`, `eci pricing`, `eci org` — read-only catalogs

Run `eci <command> -h` for usage.

## Help

- `eci -h` for top-level, `-h` on any subcommand for details.
- Issues: [github.com/elice-dev/eci-cli/issues](https://github.com/elice-dev/eci-cli/issues).
