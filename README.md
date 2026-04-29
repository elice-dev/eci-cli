# eci-cli

ECI — Elice Cloud Infrastructure CLI.

A command-line interface for managing compute, network, and storage resources on Elice Cloud.

## Installation

From a built artifact:

```bash
uv tool install eci_cli-0.1.0-py3-none-any.whl
```

From source:

```bash
git clone <repo-url> eci-cli
cd eci-cli
uv sync
```

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
eci config set vm_defaults.username ubuntu
eci config show
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
# End-to-end VM provisioning (VM + disk + NIC + IP + boot)
eci vm launch \
  --name demo \
  --pricing M-8 \
  --image ubuntu-22.04 \
  --size-gib 100 \
  --subnet default

# Reuse a saved spec from vm_defaults
eci vm launch --name demo2 --defined default

# Lifecycle
eci vm                          # list
eci vm demo                     # show
eci vm start demo
eci vm stop demo
eci vm delete demo              # cascades attached disk/NIC/IP by default

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
eci vm --format json
eci vm --format csv --query name,status,instance_type
eci vm demo --format json --query name,zone     # zone_id auto-resolved to name
```

When JSON format is used without `--query`, all `*_id` fields are resolved to names (`zone_id` → `zone`, etc.) where possible.

## Zone override

Run a single command against a different zone without touching config:

```bash
eci --zone kr-north vm
```

## Development

```bash
uv sync                  # install runtime + dev dependencies
make format              # ruff format + ruff check --fix + mypy
make check               # CI checks (no auto-fix)
make test                # pytest with coverage
make build               # sdist + wheel into dist/
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
│   ├── compute/          # vm, cluster, launch
│   ├── network/          # vnet, subnet, nic, ip
│   ├── storage/          # block (+ snapshot, scheduler), obj, pfs
│   ├── configure.py      # `eci configure` and `eci config ...`
│   └── image.py / instance_type.py / org.py / pricing.py / region.py / zone.py
└── utils/
    ├── name_resolver.py  # name → UUID resolution + caching
    ├── options.py        # filter/output decorators
    ├── output.py         # render_list / render_one (table/json/csv)
    ├── registration.py   # register_list_get auto-registers list/get commands
    └── resource_group.py # ResourceGroup: positional arg → __get__
```

Most resource `list`/`get` commands are auto-registered via `register_list_get()` from a `FilterSpec` list, which is why each `commands/*.py` is short. `NameResolver` lazily calls `list_*` to translate human-readable names into UUIDs at the API boundary.
