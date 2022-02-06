""""Splunk Docker-Container Manager."""

import os
import tarfile
from pathlib import Path
from time import sleep
from typing import List, Optional, Union

import docker
from InquirerPy import inquirer
from InquirerPy.exceptions import InvalidArgument
from rich import print  # pylint: disable=W0622
from rich.progress import track


class DockerManager:
    """Splunk docker container management wrapper."""

    def __init__(self, parent: object = None):
        """Docker container management for splunk.

        Args:
            parent (object, optional): Splunk manager instance. Defaults to None.
            start: Start or restart splunk container.
        """
        self._parent = parent
        self._interactive = parent._interactive
        self._log = parent._log
        self._settings = parent._settings
        self._log.debug("Creating docker client interface.")
        self._docker = docker.APIClient(base_url=self._settings.DOCKER.SOCKET)
        self._container = self._get_or_create_container(interactive=False)

    def __str__(self):
        print(f" - Image:          '{self.image['RepoTags'][0]}'")
        if self._container is not None and "State" in self._container:
            print(f" - Container:      '{self._container['State']}'")
        return "Docker helper for Splunk development purposes."

    @property
    def image(self) -> Optional[dict]:
        """Splunk docker image.

        Existing or pulled

        Returns:
            dict: docker.Image properties
        """
        for image in self._docker.images():
            if "RepoTags" in image:
                tags = image["RepoTags"]
                if (
                    isinstance(tags, list)
                    and len(tags) > 0
                    and self._settings.DOCKER.IMAGE in tags[0]
                ):
                    return image
        self._log.info("Couldn't find Splunk docker image locally.")
        return (
            self._docker.pull(
                repository=self._settings.DOCKER.IMAGE.split(":")[0],
                tag=self._settings.DOCKER.IMAGE.split(":")[-1],
            )
            if self._interactive
            and inquirer.confirm(
                message="Do you want to pull the latest splunk container image?",
                default=False,
            ).execute()
            else None
        )

    @property
    def _splunk_var_volume(self) -> dict:
        for volume in self._docker.volumes()["Volumes"]:
            if "splunk" in volume["Name"] and "var" in volume["Name"]:
                self._log.info("Found an existing volume for 'splunk_var'.")
                return volume
        self._log.info("Creating new volume for 'splunk_var'.")
        return self._docker.create_volume(
            name="splunk_var",
            driver="local",
            labels={
                "io.nextpart.project": "nextpart_splunking",
                "io.nextpart.volume": "splunk_var",
            },
        )

    @property
    def _splunk_etc_volume(self) -> dict:
        for volume in self._docker.volumes()["Volumes"]:
            if "splunk" in volume["Name"] and "etc" in volume["Name"]:
                self._log.info("Found an existing volume for 'splunk_etc'.")
                return volume
        self._log.info("Creating new volume for 'splunk_etc'.")
        return self._docker.create_volume(
            name="splunk_etc",
            driver="local",
            labels={
                "io.nextpart.project": "nextpart_splunking",
                "io.nextpart.volume": "splunk_etc",
            },
        )

    def _check_running(self) -> bool:
        """Ensure container instance is running or try to start.

        Returns:
            bool: Container instance status is "Up*".
        """
        self._container = self._get_or_create_container()
        if self._container:
            while "State" not in self._container:
                sleep(1)
            if "Up" in self._container["Status"]:
                return True
            if (
                inquirer.confirm(
                    message="Do you want to start the container?", default=True
                ).execute()
                or not self._interactive
            ):
                self.start()
        return False

    def _get_or_create_container(self, interactive=None) -> dict:
        """Create Splunk docker container if not exists.

        A created or existing docker container for splunk image.

        Returns:
            dict: docker.Container properties
        """
        for container in self._docker.containers(all=True):
            if container["Names"][0] == "/splunk":
                self._container_id = container["Id"]
                return container
        self._log.info("Splunk container does not exist.")
        if (interactive is not None and interactive is True) or (
            self._interactive
            and not inquirer.confirm(
                message="Do you want to create the container?", default=True
            ).execute()
        ):
            return None
        return self._docker.create_container(
            name="splunk",
            hostname="splunk",
            image=self.image["Id"],
            environment=[
                "SPLUNK_START_ARGS=--accept-license",
                "SPLUNK_PASSWORD=mySplunkDevPw",
                f"SPLUNKBASE_USERNAME={self._settings.SPLUNKBASE.USERNAME}",
                f"SPLUNKBASE_PASSWORD={self._settings.SPLUNKBASE.PASSWORD}",
                "PATH: $PATH:/opt/splunk/bin",
                f"SPLUNK_APPS_URL={self._splunkbase_installs()}",
            ],
            volumes=[
                "/opt/splunk/etc",  # splunk_etc_volume.name,
                "/opt/splunk/var",  # splunk_var_volume.name,
            ],
            host_config=self._docker.create_host_config(
                mounts=[
                    docker.types.Mount(
                        target="/opt/splunk/var",
                        source=self._splunk_var_volume["Name"],
                    ),
                    docker.types.Mount(
                        target="/opt/splunk/etc",
                        source=self._splunk_etc_volume["Name"],
                    ),
                ],
                port_bindings={8000: 8000, 9997: 9997, 8088: 8088, 8089: 8090},
            ),
            user="root",
            detach=True,
        )

    def _get_custom_apps_installed_in_container(self) -> List[str]:
        """Connect to Splunk Container and get all installed custom apps.

        Returns:
            List[str]: A list of all installed custom apps that were found.
        """
        # Get all installed apps in $SPLUNKHOME/etc/apps
        container_apps = self._docker.exec_start(
            self._docker.exec_create(
                container="splunk",
                workdir="/opt/splunk/etc/apps",
                cmd=(
                    "bash -c '"
                    + "find . -name app.conf"
                    + r" -exec dirname {} \; | xargs dirname"
                    + "'"
                ),
            )["Id"]
        ).decode("utf-8")
        # Get all custom apps
        container_apps = [
            app.replace("./", "")
            for app in container_apps.split("\n")
            if "/" not in app.replace("./", "")
            and app.replace("./", "") not in self._settings.APPS.exclude
        ]
        return container_apps

    def _splunkbase_installs(self) -> str:
        """Build SPLUNK_APPS_URL env var for container.

        Returns:
            str: Chained list of splunkbase download links.
        """
        apps = inquirer.checkbox(
            message="What apps do you want to install from Splunkbase?",
            choices=self._settings.SPLUNKBASE.APPS.keys(),
            default=self._settings.SPLUNKBASE.APPS.keys(),
        ).execute()
        apps_urls = []
        for app_name in apps:
            apps_urls.append(
                "https://splunkbase.splunk.com/app/"
                + self._settings.SPLUNKBASE.APPS[app_name].ID
                + "/release/"
                + self._settings.SPLUNKBASE.APPS[app_name].VERSION
                + "/download"
            )
        return ",".join(apps_urls)

    def start(self) -> dict:
        """Start or restart splunk container.

        Returns:
            dict: docker client container (re)start response dict.
        """
        seconds_to_wait = 1
        while True:
            self._container = self._get_or_create_container()  # Update container instance
            try:
                if self._container["Status"] == "Created":  # pylint: disable=R1705
                    self._container = self._docker.start(self._container["Id"])
                    self._log.info("Container starting...")
                    return self._container
                elif "Exited" in self._container["Status"]:
                    self._log.info("Restarting stopped Splunk container.")
                    self._container = self._docker.restart(self._container["Id"])
                elif "Up" in self._container["Status"]:
                    self._log.info("Container already exists and is running.")
                    return None
                else:
                    self._log.warning("Strange... restarting...")
                    self._container = self._docker.restart(self._container["Id"])
                    return self._container
            except KeyError:
                self._log.info("Waiting for Container to start...")
                seconds_to_wait *= 2  # Wait exponentially
                sleep(seconds_to_wait)
                continue

    def stop(self):
        """Stop the container instance."""
        if "Up" in self._container["Status"]:
            self._log.info(f"Stopping container: {self._container['Id']}")
            self._docker.stop(self._container["Id"])
        else:
            self._log.warning("No Splunk Container to stop!")

    def list(self):
        """Get a list of all installed custom apps in the container."""
        return self._get_custom_apps_installed_in_container()

    def upload(self, path: Union[Path, str] = Path.cwd(), app: str = None):
        """Upload local splunk apps to container instance.

        Args:
            path (Union[Path, str], optional): Source path to find apps. Defaults to Path.cwd().
            app (str, optional): Application name wildcard. Defaults to None.
        """
        if not self._check_running():
            self._log.error("Splunk container is not running. Will skip step.")
            return
        # Check if path exists
        if isinstance(path, str) and not Path(path).exists():
            self._log.error("The specified path does not exist. Please provide a valid path.")
            return
        apps = self._parent.apps(path=path, name=app)._paths
        apps.sort()
        try:
            if self._interactive:
                apps_selected = inquirer.checkbox(
                    message="What apps do you want to upload to your instance?",
                    choices=[app.name for app in apps],
                    default=[app.name for app in apps],
                ).execute()
                apps = [app for app in apps if app.name in apps_selected]
            self._log.info("Uploading apps '" + "', '".join([app.name for app in apps]) + "'.")
        except InvalidArgument:
            self._log.error("Current path does not contain any Splunk Apps. Hint: Try --path")
            return
        Path.cwd()
        for tmp_app in track(apps):
            with tarfile.open(str(tmp_app) + ".tar", mode="w") as tar:
                os.chdir(tmp_app.parent)
                try:
                    tar.add(str(tmp_app.name))
                finally:
                    tar.close()
            with open(str(tmp_app) + ".tar", "rb") as tar_file:
                if not self._docker.put_archive(
                    container="splunk",
                    path="/opt/splunk/etc/apps",
                    data=tar_file.read(),
                ):
                    self._log.warning("Failed to upload app to container instance")
                else:
                    self._log.debug(f"Uploaded '{tmp_app.name}' to container instance")

            os.remove(Path(str(tmp_app) + ".tar"))
            self.fix_app_permissions(app_name=tmp_app.name)

    def download(
        self, path: Union[Path, str] = Path.cwd(), app: str = None
    ):  # pylint: disable=R0912
        """Download splunk container instance application to local filesystem.

        Args:
            path (Union[Path, str], optional): Path to store app. Defaults to Path.cwd().
            app (str, optional): App name wildcard. Defaults to None.
        """
        if not self._check_running():
            self._log.error("Splunk container is not running. Will skip step.")
            return
        # Check if path exists
        if isinstance(path, str) and not Path(path).exists():
            self._log.warn("The specified path for storing Splunk Apps does not exist.")
            if inquirer.confirm(
                message=f"Do you want to create the folder: {path}?", default=True
            ).execute():
                self._log.info(f"Creating dir(s): {path}")
                os.makedirs(path)
            else:
                self._log.error("You have to specify an existing folder.")
                return
        local_apps = self._parent.apps(path=path)._paths
        container_apps = self._get_custom_apps_installed_in_container()
        selected_apps = []
        if app:
            app = app.replace("*", "")
            for container_app in container_apps:
                if app in container_app:
                    selected_apps.append(container_app)
            if self._interactive:
                selected_apps = inquirer.checkbox(
                    message="What apps do you want to download from your instance?",
                    choices=selected_apps,
                    default=selected_apps,
                ).execute()
        elif self._interactive:
            selected_apps = inquirer.checkbox(
                message="What apps do you want to download from your instance?",
                choices=container_apps,
                default=container_apps,
            ).execute()
        else:
            for container_app in container_apps:
                if container_app in local_apps:
                    selected_apps.append(container_app)
        self._log.info("Downloading apps '" + "', '".join(selected_apps) + "'.")
        Path.cwd()
        for tmp_app in track(selected_apps):
            if isinstance(path, Path):
                path = "."
            bits, stat = self._docker.get_archive(
                container="splunk", path=f"/opt/splunk/etc/apps/{tmp_app}"
            )
            self._log.debug(f"Downloaded {tmp_app} archive with properties {stat}")
            with open(str(path + "/" + tmp_app) + ".tar", mode="wb") as file_handle:
                for chunk in bits:
                    file_handle.write(chunk)
            self._log.debug(f"Wrote download content for {tmp_app} to local file")
            with tarfile.open(str(path + "/" + tmp_app) + ".tar", mode="r") as tar:
                tar.extractall(path)
            self._log.debug("Extracted downloaded artifact for {tmp_app}.")
            os.remove(Path(str(path + "/" + tmp_app) + ".tar"))
            self._log.debug("Removed downloaded archive {tmp_app}.tar after extraction.")

    def fix_app_permissions(self, app_name: Optional[str] = None):
        """Fix splunk application permissions in container instance.

        Args:
            app_name (Optional[str]): Name of the app. Defaults to None.
        """
        container_apps = self._get_custom_apps_installed_in_container()
        selected_apps = []
        if self._interactive and not app_name:
            selected_apps = inquirer.checkbox(
                message="For which apps should the permissions be fixed on your instance?",
                choices=container_apps,
                default=container_apps,
            ).execute()
        elif app_name and app_name in container_apps:
            selected_apps.append(app_name)
        else:
            for app in container_apps:
                selected_apps.append(app)
        for app in selected_apps:
            execution = self._docker.exec_create(
                container="splunk",
                workdir="/opt/splunk/etc/apps",
                cmd=(
                    "bash -c '"
                    + f"chown -R splunk. {app} ;"
                    + f"chmod 755 {app} ;"
                    + f"find {app} -maxdepth 1 -name 'azure-pipelines.yml'"
                    + r" -exec rm {} \;  >/dev/null 2>&1 ;"
                    + f"find {app} -maxdepth 1 -name '*.rst'"
                    + r" -exec rm {} \;  >/dev/null 2>&1 ;"
                    + f"find {app} -maxdepth 1 -name '.git*'"
                    + r" -exec rm {} \;  >/dev/null 2>&1 ;"
                    + f"find {app} -maxdepth 1 -name '.pre-commit-config.yaml'"
                    + r" -exec rm {} \;  >/dev/null 2>&1 ;"
                    + f"find {app} -type d"
                    + r" -exec chmod -R 700 {} \;  >/dev/null 2>&1 ;"
                    + f"find {app} -type f"
                    + r" -exec chmod -R 644 {} \;  >/dev/null 2>&1 ;"
                    + f"find {app}/local {app}/default {app}/static -type f"
                    + r" -exec chmod 600 {} \; >/dev/null 2>&1 ;"
                    + f"find {app}/bin -type f"
                    + r" -exec chmod 655 {} \;  >/dev/null 2>&1 ;"
                    + f"find {app}/static -type d"
                    + r" -exec chmod 710 {} \;  >/dev/null 2>&1 ;"
                    + f"find {app}/static -name app.manifest"
                    + r" -exec chmod 600 {} \;  >/dev/null 2>&1 ;"
                    + "'"
                ),
            )
            self._log.debug(self._docker.exec_start(execution["Id"]).decode("utf-8"))
        self._log.info("Fixed Permissions for Splunk Apps: ['" + "', '".join(selected_apps) + "'].")
