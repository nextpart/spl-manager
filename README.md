# `nextpart-splunk`

The library `nextpart-splunk` aka `spl` is a abstraction for splunk related development
and maintenance operations. Providing you a single CLI or SDK brings you a comfortable
utility to perform day-to-day operations, like fetching samples, building apps,
comparing instances and knowledge object management.

# Getting Started

You can download the package from the package feed via `pip install spl` or install from
source with `poetry install` after cloning the repository.

Then you can issue your first command to get the help page:

```bash
python -m spl -h
```

or

```bash
poetry run python -m spl -h
```

if you use poetry. Anyhow it's recommended to set a alias:

```bash
alias spl="python -m spl"
```

# Using the library

Please note that, when using the library as an SDK you need to pass the
`interactive=False` flag to not run into issues because in _interactive_ mode it asks
for user inputs via CLI methods.

```python
from spl import SplManager

spl = SplManager(interactive=False)
```

# Using the CLI

If you wish to get more information about any command within `spl`, you can pass the
`-h` parameter.

## Top-level `spl` Options

- `--interactive`: Wether or not to run in interactive mode.
- `--src`: The name of the source connection provided in settings.
- `--dest`: The name of the destination connection provided in settings.

## Top-level `spl` Modules

- `connections` provides you a list of connections in the configuration.

- `docker` helps you to manage the local splunk container instance.

- `apps` abstracts the handling of local application folders at a given `--path` and
  helps with validation, packaging, vetting, etc.

- `samples` are based on the configured queries for a `--connection` or `--src` and can
  download results and store them automatically at a `--path` to use for _SA-Eventgen_.

- `manager` acts as a direct `ConnectionAdapter` interface for the specified `--dest`
  parameter.

- `sync` will handle `manager`s for `--src` and `--dest` connections, enabling you to
  compare, move and update between those instances.
