# Splunk Management Utility

This library is an abstraction for Splunk-related development, maintenance, or migration operations. It provides a single CLI or SDK to conveniently perform various operations such as managing a local development container, retrieving sample-data, building applications, comparing instances, managing knowledge objects and hopefully much more in the future.

## Motivation



```
<Development Repository>
├── apps                          # Folder where to store applications
│   └── Defender_TA_nxtp          # Generic custom Splunk app
├── dist                          # Place for built packages and reports 
├── scripts                       
├── config                        # Settings and secrets
│   └── settings.yaml             # General purpose settings for this lib
│   └── .secrets.yaml             # API settings for connections and secrets
└── share                         # Custom splunkbase or builtin app content
```

### We want to ...

* Spin up a local development container:
  ```bash
  spl docker start
  ```
* Put my local application(s) there for testing purposes:
  ```bash
  spl docker upload --app="Defender*"
  ```
* Get sample data for Eventgen:
  ```bash
  spl --src="onprem"  samples --path="./apps/SA-Eventgen" download --name="WinDefender"
  ```
* Download apps from development container to local folder:
  ```bash
  spl docker download --app="Defender*"
  ```
* Run AppInspect, Packaging, etc.:
  ```bash
  spl apps --name="Defender_TA*" validate
  ```
* List various objects on an instance:
  ```bash
  spl manager --conn="onprem" users list
  ```
* Create or modify objects on an instance:
  ```bash
  spl manager --conn="onprem" roles update --name "investigator"
  ```
* Sync objects and their properties from one instance to another:
  ```bash
  spl --src="onprem" --dest="localhost" sync users --create --update
  ```

and probably much more, so pull requests are welcome!

## Getting Started

You can download the package from the package feed via `pip install spl-mngmt` or install from
source with [poetry](https://python-poetry.org/) after cloning the repository.

Then you can issue your first command to get the help page:

```bash
python -m spl -h
```

or `poetry run python -m spl -h`. Anyhow it's recommended to set the `alias spl="python -m spl` for easier handling.

## Using the library

Please note that, when using the library as an SDK you need to pass the
`interactive=False` flag to not run into issues because in _interactive_ mode it asks
for user inputs via CLI methods.

```python
from spl import SplManager

spl = SplManager(interactive=False)
```

## Using the CLI

If you wish to get more information about any command within `spl`, you can pass the
`-h` parameter.

### Top-level `spl` Options

- `--interactive`: Wether or not to run in interactive mode.
- `--src`: The name of the source connection provided in settings.
- `--dest`: The name of the destination connection provided in settings.

### Top-level `spl` Modules

- `connections` provides you a list of connections in the configuration.

- `docker` helps you to manage the local splunk container instance.

- `apps` abstracts the handling of local application folders at a given `--path` and
  helps with validation, packaging, vetting, etc.

- `samples` are based on the configured queries for a `--connection` or `--src` and can
  download results and store them automatically at a `--path` to use for _SA-Eventgen_.

- `manager` acts as a direct `ConnectionAdapter` interface for the specified `--conn`
  parameter.

- `sync` will handle `manager`s for `--src` and `--dest` connections, enabling you to
  compare, move and update between those instances.


## References

- [Splunk Python SDK](https://docs.splunk.com/Documentation/PythonSDK)
- [Python Docker SDK (low-level API)](https://docker-py.readthedocs.io)
- [Python Rich Outputs](https://rich.readthedocs.io)
- [InquirerPy User Inputs](https://inquirerpy.readthedocs.io/)
- [Python Fire CLI](https://github.com/google/python-fire)
- [DeepDiff](https://zepworks.com/deepdiff/current/)
- [Cerberus Schema Validation](https://docs.python-cerberus.org/)
- [Splunk AppInspect](https://dev.splunk.com/enterprise/reference/appinspect)
- [Splunk PAckaging Toolkit](https://dev.splunk.com/enterprise/reference/packagingtoolkit)
- [Splunk Eventgen](http://splunk.github.io/eventgen/)

## License & Copyright

Copyright © Nextpart Security Intelligence GmbH - All Rights Reserved

*Unauthorized copying via any medium is strictly prohibited.*

*Proprietary and confidential*

