# eci-cli

ECI — Elice Cloud Infrastructure CLI.

A command-line interface for managing compute, network, and storage resources on Elice Cloud.

`eci -V` / `eci --version` prints the installed version. Transient `5xx`/`429`
responses from the API are automatically retried (3 attempts, exponential
backoff, `Retry-After` honored).

## Installation

### From a release (recommended) — Linux x86_64

Each tagged release publishes a directory bundle as
`eci-linux-x86_64-<tag>.tar.gz` (Nuitka `--standalone`, AWS CLI v2-style:
the launcher and its dependencies live under one directory, with a symlink
on `PATH`). Warm startup is ~85ms.

The repo ships an installer that downloads the right tarball for your
OS/arch, verifies its sha256, unpacks the bundle, and symlinks the launcher
into `PATH`. Run it with `API_BASE` pointing at the host that serves the
release assets:

```bash
# When the release host is wired up:
curl -fsSL https://api.elice.cloud/cli/install.sh | sh

# Or from a checked-out repo (for now, until /cli/install.sh is hosted):
API_BASE=<release-host> sh scripts/install.sh
```

By default the bundle is installed to `/usr/local/eci-cli` with the
launcher symlinked to `/usr/local/bin/eci` (falls back to `~/.local/...`
without sudo if those paths are not writable). Override with
`ROOT_DIR=...` and `INSTALL_DIR=...`.

### From source (Python 3.11+)

For macOS / Windows, or when you want to develop against the CLI:

```bash
git clone <repo-url> eci-cli
cd eci-cli
uv sync
uv run eci --help
```

To build a directory bundle locally (same shape the installer expects):

```bash
make build-standalone
# Output: dist/entry.dist/   (launcher: dist/entry.dist/eci)
mkdir -p ~/.local/eci-cli ~/.local/bin
cp -R dist/entry.dist/. ~/.local/eci-cli/
ln -sf ~/.local/eci-cli/eci ~/.local/bin/eci
```

`make build` produces a cross-platform wheel under `dist/` for ad-hoc local
distribution. CI does not publish wheels — only the standalone tarball.

### Corporate SSL inspection

The CLI calls `truststore.inject_into_ssl()` at startup so requests trusts
whatever root CAs are installed in the OS trust store (Keychain on macOS,
`ca-certificates` on Linux, Cert Store on Windows). This makes
`eci configure verify` work behind corporate SSL inspection (Netskope,
Zscaler, etc.) without any extra setup.

## Configuration

Set up API credentials and a default zone interactively:

```bash
eci configure
```

The config is stored at `~/.eci/config.yaml` with mode `0600`. Environment variables override the file:

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

`config set` stores values as strings — it does not coerce digit-only inputs to
int or `true`/`false` to bool. For typed VM defaults (e.g. `size_gib`), use
`eci vm-spec save`, which validates fields and writes the right types.

### Saved VM specs

Reusable launch specs (templates) live under `vm-spec`:

```bash
eci vm-spec save default \
  --instance-type M-8 --image ubuntu-22.04 --size-gib 100 --subnet default --username ubuntu
eci vm-spec save spot --instance-type M-8 --price-type spot --image ubuntu-22.04 --size-gib 100 --subnet default
eci vm-spec list
eci vm-spec show default
eci vm-spec save default --instance-type M-16 --force      # overwrite
eci vm-spec delete old
```

Use a saved spec at launch time:

```bash
eci compute vm launch --name demo --spec default
eci compute vm launch --name demo --spec default --size-gib 200   # override → prompts to re-save
```

## Usage

All `list`/`get` commands accept `--format {table,json,csv}` and `--query col1,col2`. UUIDs and names are interchangeable wherever a resource is referenced.

### Read-only

```bash
eci zone                        # list zones
eci zone kr-central             # show one (positional → get)
eci instance-type --activated true --format json
eci pricing --resource-kind vm_allocation
eci org info
eci org usage
```

### Compute

```bash
# Easiest first launch — everything else is prompted with defaults
# (instance-type=C-2, image+size auto-selected for CPU vs GPU instance,
#  a default vnet/subnet 'eci-default-vnet' is auto-created and reused)
eci compute vm launch --name demo

# Fully non-interactive (recommended for scripts / AI agents)
eci compute vm launch \
  --name demo \
  --instance-type C-2 \
  --image 'Ubuntu 24.04 LTS (Standard)' \
  --size-gib 20 \
  --password 'Vk7m@p2qLn5!'

# GPU instance — defaults auto-pick the AI/GPU image (NVIDIA drivers + CUDA)
eci compute vm launch --name ml-1 --instance-type G-NHHS-80 \
  --password 'Vk7m@p2qLn5!'

# Spot price
eci compute vm launch --name demo --instance-type C-2 --price-type spot \
  --image 'Ubuntu 24.04 LTS (Standard)' --size-gib 20 \
  --password 'Vk7m@p2qLn5!'

# Pick a pricing UUID directly (when --instance-type has multiple ondemand pricings)
eci compute vm launch --name demo --pricing-id <UUID> \
  --image 'Ubuntu 24.04 LTS (Standard)' --size-gib 20 \
  --password 'Vk7m@p2qLn5!'

# Reuse a saved spec (see "Saved VM specs" section)
eci compute vm launch --name demo2 --spec default --password '...'

# Lifecycle
eci compute vm                  # list
eci compute vm demo             # show
eci compute vm start demo
eci compute vm stop demo
eci compute vm delete demo                # delete VM only (attached disk/NIC/IP are kept)
eci compute vm delete demo --cascade      # also delete attached disk/NIC/IP (data loss!)

# SSH (uses the VM's stored username + first attached public IP)
eci compute ssh demo
eci compute ssh demo -l root -p 2222 -i ~/.ssh/id_rsa
eci compute ssh demo -- -L 8080:localhost:8080  # forward extra ssh args after `--`

# Clusters
eci compute cluster create --name c1 --instance-type M-8
eci compute cluster start c1
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
eci storage block scheduler create --name nightly --block data \
  --cron "0 0 * * *" --max-snapshots 7

eci storage object create --name bucket --size-gib 500
eci storage object user create --name alice
eci storage object user grant create --bucket bucket --user alice --permission read_write

eci storage pfs create --name fs --size-gib 1000
eci storage pfs member create --pfs fs --vm demo
```

## Output and querying

```bash
eci compute vm --format json
eci compute vm --format csv --query name,status,instance_type
eci compute vm demo --format json --query name,zone     # zone_id auto-resolved to name
```

When JSON format is used without `--query`, all `*_id` fields are resolved to names (`zone_id` → `zone`, etc.) where possible.

## Zone override

Run a single command against a different zone without touching config:

```bash
eci --zone kr-north compute vm
```

## Development

```bash
uv sync                  # install runtime + dev dependencies
make format              # ruff format + ruff check --fix + mypy
make check               # CI checks (no auto-fix)
make test                # pytest with coverage
make build               # sdist + wheel into dist/
make build-standalone    # Nuitka --standalone bundle into dist/entry.dist/
```

Tests live under [tests/](tests/) and mirror the [app/](app/) layout. Run a subset:

```bash
uv run pytest tests/commands/network/        # network commands only
uv run pytest tests/test_cli.py -v
```

Set `ECI_DEBUG=1` to print internal warnings to stderr (e.g. when name resolution silently falls back to UUIDs).

## Architecture

```
app/
├── cli.py                # top-level Click group, error handling
├── client.py             # HTTP client (ECIClient) wrapping the ECI API
├── config.py             # YAML config + env var overrides
├── commands/
│   ├── compute/          # vm (+ launch, ssh), cluster
│   ├── network/          # vnet, subnet, nic, public_ip
│   ├── storage/          # block (+ snapshot, scheduler), object (+ user, grant), pfs (+ member)
│   ├── configure.py      # `eci configure` and `eci config ...`
│   ├── vm_spec.py        # `eci vm-spec ...` (saved launch templates)
│   └── image.py / instance_type.py / org.py / pricing.py / region.py / zone.py
└── utils/
    ├── name_resolver.py  # name → UUID resolution + caching
    ├── options.py        # filter/output decorators
    ├── output.py         # render_list / render_one (table/json/csv)
    ├── registration.py   # register_list_get auto-registers list/get commands
    └── resource_group.py # ResourceGroup: positional arg → __get__
```

Most resource `list`/`get` commands are auto-registered via `register_list_get()` from a `FilterSpec` list, which is why each `commands/*.py` is short. `NameResolver` lazily calls `list_*` to translate human-readable names into UUIDs at the API boundary.
