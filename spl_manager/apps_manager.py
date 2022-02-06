"""Splunk Application-Manager.

List, Create & Validate/AppInspect Splunk Applications.
"""

import csv
import json
import logging
import os
from pathlib import Path
from time import sleep
from typing import Optional, Union

import docker
import requests
import splunk_appinspect
from InquirerPy import inquirer
from requests.auth import HTTPBasicAuth
from requests_toolbelt.multipart.encoder import MultipartEncoder
from rich import print  # pylint: disable=W0622
from rich.console import Console
from rich.progress import track
from rich.table import Table


class AppsManager:
    """Management interface for locally stored splunk apps.

    Returns:
        Management interface/module for local apps.
    """

    _apps = []
    _paths = []
    _results = {}

    def __init__(self, parent: object, path: Union[Path, str] = Path.cwd(), name: str = "*"):
        """Local application management module initialization.

        Args:
            parent (object): Manager with properties to propagate.
            path (Union[Path, str], optional): Working directory of applications or where to search.
                Defaults to Path.cwd().
            name (str, optional): Name or wildcard pattern to search for applications matching.
                Defaults to None.
        """
        if isinstance(path, str):
            path = Path(path)
        self._parent = parent
        self._settings = parent._settings
        self._log = parent._log
        self._interactive = parent._interactive
        self._work_dir = path.resolve().absolute()
        print(self._work_dir)
        self._docker = docker.APIClient(base_url=self._settings.DOCKER.SOCKET)
        if not name:
            self._paths = list(
                {app_path.parent.parent for app_path in self._work_dir.glob("**/app.conf")}
            )
        else:
            self._paths = list(
                {
                    app_path.parent.parent
                    for app_path in list(self._work_dir.glob("**/" + str(name) + "/**/app.conf"))
                }
            )

    def __str__(self):
        return (
            str(", ".join([app_path.name for app_path in self._paths]))
            if self._paths
            else "No apps found!"
        )

    @property
    def _apps(self):
        apps = []
        logging.getLogger("splunk_appinspect.app").disabled = True
        for path in track(self._paths):
            apps.append(
                splunk_appinspect.App(
                    location=path,
                    python_analyzer_enable=False,
                    trusted_libs_manager=False,
                )
            )
        apps.sort(key=lambda x: x.package_id)
        return apps

    def list(self, csv_file: Optional[str] = None):
        """Determine apps from local directory and print table or write to csv.

        Args:
            csv_file (str, optional): Name of the file to store csv table. Defaults to None.
        """
        if csv_file is None:
            table = Table(title="Local Splunk Applications")
            table.add_column("ID", style="cyan")
            table.add_column("Name")
            table.add_column("Version", style="green")
            # table.add_column('Author')
            # table.add_column('Description')
            for app in self._apps:
                table.add_row(app.package_id, app.label, app.version)
            console = Console()
            console.print(table)
        else:
            results = []
            for app in self._apps:
                results.append({"ID": app.package_id, "Name": app.label, "Version": app.version})
            with open(csv_file, "w", encoding="utf-8") as outfile:
                csv_writer = csv.writer(outfile)
                csv_writer.writerow(results[0].keys())
                csv_writer.writerows([result.values() for result in results])

    def validate(self, force: Optional[bool] = False, cloudvet=None):
        """Packaging, validation and vetting of selected apps.

        Packaging and local validation/appinspect routine using utility image with
        subsequent cloud vetting via appinspect API if requested via parameter.

        Args:
            force (bool, optional): Don't ask to rerun routine if result already exists.
                Defaults to False.
            cloudvet (bool, optional): Also run the cloud-vetting check via appinspect API.
                Defaults to None.
        """
        apps = self._apps
        if apps and self._interactive:
            selected_apps = inquirer.checkbox(
                message="Select the apps you want to validate:",
                choices=[app.name for app in apps],
            ).execute()
            apps = [app for app in apps if app.name in selected_apps]
        if apps == []:
            return
        if cloudvet is None and self._interactive:
            cloudvet = inquirer.confirm(
                message="Do you want to validate packages via cloud vetting?", default=False
            ).execute()
        elif cloudvet is None:
            cloudvet = False
        for app in apps:
            self.run_packaging(
                app_path=Path(app.app_dir),
                dist_path=Path(self._work_dir.parent / "dist", force=force),
            )
            if cloudvet:
                self.run_cloudvetting(
                    app_name=app.package_id,
                    dist_path=Path(self._work_dir.parent / "dist", force=force),
                )

    def run_packaging(self, app_path: Path, dist_path: Path, force: Optional[bool] = False):
        """Run application preperation, packaging, validation and appinspect via image.

        Args:
            app_path (Path): Path to the application directory to process.
            dist_path (Path): Distribution path to store resulting artifacts and reports.
            force (bool, optional): Whether to ask for rebuilding if results already exist.
                Defaults to False.
        """
        container_id = None
        result_dir = Path(dist_path / app_path.name)
        if force is not True and self._interactive is True and result_dir.exists():
            run = inquirer.confirm(
                message="There is already a built package for this application."
                + " Do you want to overwrite it?",
                default=True,
            ).execute()
        elif force is True or not result_dir.exists():
            run = True
        else:
            run = False
        if run:
            for container in self._docker.containers(all=True):
                if "splunk_package" in container["Names"][0]:
                    container_id = container["Id"]
                    self._log.info("Package container already exists.")
                    break
            if container_id is not None and (
                not self._interactive
                or inquirer.confirm(
                    message="Do you want to delete the old packaging container?", default=True
                ).execute()
            ):
                self._docker.remove_container(container_id)
            container_id = self._docker.create_container(
                name="splunk_package",
                hostname="splunk_package",
                image=self.package_image()["Id"],
                environment=["APP_DIR=/apps", "PKG_DIR=/dist", f"MYUSER={os.getuid()}"],
                volumes=[f"/apps/{app_path.name}", "/dist"],
                host_config=self._docker.create_host_config(
                    binds={
                        f"{str(app_path)}": {
                            "bind": f"/apps/{app_path.name}",
                            "mode": "rw",
                        },
                        f"{str(dist_path)}": {
                            "bind": "/dist",
                            "mode": "rw",
                        },
                    },
                ),
            )["Id"]
            sleep(5)
            states = self._docker.containers(all=True, filters={"id": container_id})
            self._docker.start(container_id)
            self._log.info(f"Running application packaging container for '{app_path.name}'.")
            while len(states) > 0 and states[0]["State"] != "exited":
                states = self._docker.containers(all=True, filters={"id": container_id})
                sleep(1)
            sleep(1)
            self._log.debug(self._docker.logs(container=container_id).decode("utf-8"))
            self._log.debug(f"Removing application packaging container for {app_path.name}.")
            self._docker.remove_container(container=container_id)

            if not result_dir.exists():
                self._log.error("Packaging produced no output files!")
            self._log.info(f"Finished packaging app '{app_path.name}'.")
        else:
            self._log.info(f"Using older packaging result for '{app_path.name}'.")

        with open(
            str(result_dir) + "/" + str(app_path.name) + "_appinspect.log", "r", encoding="utf-8"
        ) as log_file:
            self._log.info(log_file.read())

    def run_cloudvetting(
        self, app_name: str, dist_path: Path, force: Optional[bool] = False
    ):  # pylint: disable=R0914
        """Cloud vetting routine via AppInspect API. Can bring different results.

        Args:
            app_name (str): Name of the application to process.
            dist_path (Path): Distribution path to store resulting artifacts and reports.
            force (bool, optional): Whether to ask for rerun if results already exist.
                Defaults to False.
        """
        result = Path(dist_path / f"{app_name}_appinspect.html")
        package = list(Path(dist_path / app_name).glob("*.tar.gz"))
        if len(package) > 0:
            package = package[0]
        else:
            self._log.warning(f"Could not find package for '{app_name}'.")
            return
        self._log.info(f"Running cloudvetting for '{app_name}'")
        if result.exists() and not force and self._interactive:
            run = inquirer.confirm(
                message="There is already a cloudvetting report for this application."
                + " Do you want to overwrite it?",
                default=True,
            ).execute()
        elif force is True or not result.exists():
            run = True
        else:
            run = False
        if run:
            user_token = (
                requests.get(
                    self._settings.SPLUNKBASE.auth_uri,
                    auth=HTTPBasicAuth(
                        username=self._settings.SPLUNKBASE.username,
                        password=self._settings.SPLUNKBASE.password,
                    ),
                )
                .json()
                .get("data")
                .get("token")
            )
            fields = {}
            with open(package, "rb") as package_file:
                fields.update({"app_package": (package.name, package_file)})
                fields.update(
                    {
                        "included_tags": "cloud",
                    }
                )
                payload = MultipartEncoder(fields=fields)
                headers = {
                    "Authorization": f"bearer {user_token}",
                    "Content-Type": payload.content_type,
                }
                response = requests.post(
                    url=(self._settings.SPLUNKBASE.appinspect_uri + "/validate"),
                    data=payload,
                    headers=headers,
                ).json()
            self._log.info(f"Got response for '{app_name}': " + response.get("message"))
            if "request_id" not in response.keys():
                self._log.error(f"Failed to create cloud vetting job fir {app_name}.")
                return
            request_id = response["request_id"]
            sleep(2)
            while (
                requests.get(
                    self._settings.SPLUNKBASE.appinspect_uri + f"/validate/status/{request_id}",
                    headers=headers,
                )
                .json()
                .get("status")
                == "PROCESSING"
            ):
                sleep(1)
                self._log.debug(f"Waiting for cloud vetting with ID '{request_id}'.")
            self._log.info(f"Cloud vetting with ID '{request_id}' for '{app_name}' finished.")
            with open(
                Path(dist_path / f"{app_name}_appinspect.json"), "w", encoding="utf-8"
            ) as json_report_file:
                json_report = requests.get(
                    self._settings.SPLUNKBASE.appinspect_uri + f"/report/{response['request_id']}",
                    headers=headers,
                ).json()
                json.dump(obj=json_report, fp=json_report_file)
            with open(
                Path(dist_path / f"{app_name}_appinspect.html"), "w", encoding="utf-8"
            ) as html_report_file:
                headers["Content-Type"] = "text/html"
                html_report_file.write(
                    requests.get(
                        self._settings.SPLUNKBASE.appinspect_uri
                        + f"/report/{response['request_id']}",
                        headers=headers,
                    ).text
                )
            print(json_report["summary"])

    def package_image(self):
        """Check if image exists or pull.

        Returns:
            dict: Image properties.
        """
        for image in self._docker.images():
            tags = image["RepoTags"]
            # Skip checking tags if tags is None
            if tags is None:
                continue
            if len(tags) > 0 and self._settings.DOCKER.PACKAGE_IMAGE in tags:
                return image
        self._log.info("Couldn't find splunk packaging docker image locally.")
        return (
            self._docker.pull(self._settings.DOCKER.PACKAGE_IMAGE)
            if self._interactive
            and inquirer.confirm(
                message="Do you want to pull the latest splunk packaging container image?",
                default=False,
            ).execute()
            else None
        )
