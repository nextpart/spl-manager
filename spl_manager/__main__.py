"""Splunk Development and Maintenance Operations Manager."""

import logging
from pathlib import Path
from typing import Union

import fire
from cerberus import Validator  # Receive and work with what we expect
from dynaconf import Dynaconf
from rich import print  # pylint: disable=W0622
from rich.logging import RichHandler

from spl_manager.apps_manager import AppsManager
from spl_manager.connection_adapter import ConnectionAdapter
from spl_manager.docker_manager import DockerManager
from spl_manager.samples_manager import SamplesManager
from spl_manager.schemata import CONFIG_SCHEMA
from spl_manager.sync_manager import SyncManager

logFormatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s] | %(message)s")
rootLogger = logging.getLogger()
fileHandler = logging.FileHandler(Path.cwd() / "spl.log")
fileHandler.setFormatter(logFormatter)

logging.basicConfig(
    level="INFO", format="%(message)s", datefmt="[%X]", handlers=[RichHandler(), fileHandler]
)


class SplManager:
    """Main Splunk manager object used by CLI or as SDK main."""

    def __init__(
        self,
        interactive=True,
        level: str = "INFO",
        src: str = None,
        dest: str = None,
        context=False,
    ):  # pylint: disable=R0913
        """Splunk management object initialization and module declaration.

        Args:
            interactive (bool, optional): Wether or not to run in interactive mode.
                Defaults to True.
            src (str, optional): The name of the source connection provided in settings.
                Defaults to None.
            dest (str, optional): The name of the destination connection provided in settings.
                Defaults to None.
        """
        self._interactive = interactive
        logging.basicConfig(
            level=level,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(), logging.FileHandler(Path.cwd() / "spl.log")],
        )
        self._log = logging.getLogger(__name__)
        self._log.debug("Initializing settings from file.")
        # print(self._log.level)
        self._settings = Dynaconf(
            load_dotenv=True,
            environments=True,
            merge_enabled=True,
            settings_files=["settings.yaml", ".secrets.yaml"],
        )
        self._context = context
        validator = Validator(schema=CONFIG_SCHEMA, allow_unknown=True, require_all=True)
        if validator.validate(self._settings.to_dict()):
            self._log.debug("Settings validated successfully.")
        else:
            self._log.error(f"Settings validation failed with {validator.errors}")
            raise ValueError(f"Settings validation failed with {validator.errors}")
        # self.docker = DockerManager(self)
        if src is not None and src in self._settings.CONNECTIONS:
            self._src = ConnectionAdapter(parent=self, name=src)
        else:
            self._src = None
        if dest is not None and dest in self._settings.CONNECTIONS:
            self._dest = ConnectionAdapter(parent=self, name=dest)
        else:
            self._dest = None

        if self._src is not None and self._dest is not None:
            self._src.namespace(context=self._context)
            self._dest.namespace(context=self._context)
            self.sync = SyncManager(
                self, interactive=self._interactive, src=self._src, dest=self._dest
            )

    @property
    def connections(self):
        """Available connections from settings.

        Returns:
            str: Concatenated list of connection names, that can be used.
        """
        return (
            "Possible connections are: '"
            + str("', '".join(self._settings.CONNECTIONS.keys()))
            + "'."
        )

    def manager(self, conn: str = "localhost") -> ConnectionAdapter:
        """Splunk connection management.

        Returns:
            ConnectionAdapter: Splunk connection wrapper.
        """
        conn_adapter = ConnectionAdapter(self, name=conn)
        conn_adapter.namespace(context=self._context)
        return conn_adapter

    def docker(self) -> DockerManager:
        """Docker container management for splunk local development.

        Returns:
            DockerManager: Splunk docker container management wrapper.
        """
        return DockerManager(self)

    def samples(self, path: Union[Path, str] = Path.cwd()) -> SamplesManager:
        """Sample management module provider for SamplesManager.

        Samples are based on the configured queries for a `--connection` or `--src` and can
        download results and store them automatically at a `--path` to use for _SA-Eventgen_.

        Args:
            path (Union[Path, str], optional): [description]. Defaults to Path.cwd().

        Returns:
            SamplesManager: Management interface/module for samples.
        """
        # if self._src is None: raise ValueError(f"Source required")
        return SamplesManager(self, path=Path(path))

    def apps(self, path: Union[Path, str] = Path.cwd(), name: str = "None") -> AppsManager:
        """Local residing application management.

        Apps abstracts the handling of local application folders at a given `--path` and
        helps with validation, packaging, vetting, etc.

        Args:
            path (Union[Path, str], optional): The working directory for operations.
                Defaults to Path.cwd().
            name (str, optional): Name wildcard for application folder. Defaults to None.

        Returns:
            AppsManager: Management interface/module for local apps.

        """
        return AppsManager(self, path=path, name=name)


def main():
    try:
        fire.Fire(name="spl", component=SplManager)
    except KeyboardInterrupt:
        print("Bye! 🖖")


# CLI Entrypoint:
if __name__ == "__main__":
    main
