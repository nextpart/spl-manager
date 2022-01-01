import logging
from datetime import datetime
from typing import Any

import splunklib.binding as spl_context
import splunklib.client as spl_client
from deepdiff import DeepDiff
from InquirerPy import inquirer
from rich import inspect, print  # pylint: disable=W0622
from rich.console import Console
from rich.progress import track
from rich.table import Column, Table

TIME_FORMAT = "%d.%m.%Y %H:%M:%S"


class Object:
    def __init__(self, client, object):
        self.client = client
        self.object = object

    def __str__(self):
        return self.object.name


class ObjectList:
    def __init__(self, client: spl_client.Service, interactive=False):
        self.client = client
        self.items = self.generate()
        self._interactive = interactive

    def __str__(self):
        return str([str(item) for item in self.items])

    def generate(self):
        return []

    def list(self, details: bool = False):
        print()

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        return None

    def confirm_create(self, name: str):
        return self.interactive and inquirer.confirm(
            message=f"Do you want to create {self.__name__} '{name}' on {self.client.host}?",
            default=True,
        )

    def create(self, reference_obj):
        if not self.confirm_create(self, reference_obj.name):
            return
        logging.info(f"Creating {self.__name__} on {self.client.hostname}")

    def confirm_update(self, name, prop: str, old_val: str, new_val: str):
        return self.interactive and inquirer.confirm(
            message=f"Do you want to update {self.__name__} '{name}' property named "
            + f"{prop} from '{old_val}' to '{new_val}'?",
            default=False,
        )

    def update(self, **kwargs):
        # if not self.confirm_update(self, ??? ): return
        logging.info(f"Updating {self.__name__} on {self.client.hostname}: {kwargs}")

    def confirm_delete(self, name: str):
        return self.interactive and inquirer.confirm(
            message=f"Do you want to delete {self.__name__} '{name}' on {self.client.host}?",
            default=False,
        )

    def delete(self, name):
        if not self.confirm_delete(self, name=name):
            return
        logging.info(f"Deleting {self.__name__} '{name}' on {self.client.host}")


class Role(Object):

    type = spl_client.Role
    grouping = spl_client.Roles
    listing = grouping.list


class User(Object):

    type = spl_client.User
    grouping = spl_client.Users
    listing = grouping.list


class Roles(ObjectList):

    __name__ = "Role"

    def generate(self):
        return [Role(client=self.client, object=role) for role in self.client.roles.list()]

    def list(self, details: bool = False):
        table = (
            Table(
                "Name",
                "Default App",
                "Capabilities",
                "Imported Roles",
                Column("Indexes allowed"),
                "Indexes disallowed",
                "Search earliest",
                "Owner",
                "App",
                "Sharing",
                title="Role Overview",
            )
            if details
            else Table(
                "Name", "Default App", "Capabilities", "Imported Roles", title="Role Overview"
            )
        )
        for role in track(self.client.roles.list()):
            if not details:
                table.add_row(
                    role.name,
                    role.content["defaultApp"]
                    if "defaultApp" in role.content and role.content["defaultApp"]
                    else "",
                    str(len(role.content["capabilities"]))
                    if "capabilities" in role.content and role.content["capabilities"]
                    else "",
                    ", ".join(role.content["imported_roles"])
                    if "imported_roles" in role.content and role.content["imported_roles"]
                    else "",
                )
            else:
                table.add_row(
                    role.name,
                    role.content["defaultApp"]
                    if "defaultApp" in role.content and role.content["defaultApp"]
                    else "",
                    ", ".join(role.content["capabilities"])
                    if "capabilities" in role.content and role.content["capabilities"]
                    else "",
                    ", ".join(role.content["imported_roles"])
                    if "imported_roles" in role.content and role.content["imported_roles"]
                    else "",
                    ", ".join(role.content["srchIndexesAllowed"])
                    if "srchIndexesAllowed" in role.content and role.content["srchIndexesAllowed"]
                    else "",
                    ", ".join(role.content["srchIndexesDisallowed"])
                    if "srchIndexesDisallowed" in role.content
                    and role.content["srchIndexesDisallowed"]
                    else "",
                    role.content["srchTimeEarliest"]
                    if "srchTimeEarliest" in role.content
                    and role.content["srchTimeEarliest"] != "-1"
                    else "",
                    role.access["owner"] if "owner" in role.access and role.access["owner"] else "",
                    role.access["app"] if "app" in role.access and role.access["app"] else "",
                    role.access["sharing"]
                    if "sharing" in role.access and role.access["sharing"]
                    else "",
                )
        console = Console()
        console.print(table)

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        return DeepDiff(
            {
                str(role.name): {"access": role.access, "content": role.content}
                for role in src_client.client.roles.list()
            },
            {
                str(role.name): {"access": role.access, "content": role.content}
                for role in dest_client.client.roles.list()
            },
            ignore_order=True,
        )

    def create(self, reference_obj: spl_client.Role):
        args = {
            field: reference_obj.content[field]
            for field in reference_obj.fields["optional"]
            if field in reference_obj.content
            and reference_obj.content[field] is not None
            and reference_obj.content[field] != "-1"
            and field
            not in [
                "capabilities",
            ]
        }
        args["capabilities"] = []
        for capability in reference_obj.capabilities:
            if capability in self.client.capabilities:
                args["capabilities"].append(capability)
            else:
                logging.warning(
                    f"The role {reference_obj.name} has an unknown capability {capability}"
                    + " assignes. We'll skip this assignment. You can sync later on."
                )
        try:
            self.client.roles.create(name=reference_obj.name, **args)
        except spl_context.HTTPError as error:
            logging.error(error)

    def update(self, reference_obj, property):
        # print(property)
        old_value = self.client.roles[reference_obj.name]
        new_value = reference_obj
        try:
            for item in property.split("."):
                old_value = old_value[item]
        except KeyError as wrong_key:
            new_value = None
            pass
        try:
            for item in property.split("."):
                new_value = new_value[item]
        except KeyError as wrong_key:
            new_value = None
        logging.info(
            f"The {self.__name__} entity '{reference_obj.name}' changed at {property}"
            + " from '{old_value}' to '{new_value}'."
        )


class Users(ObjectList):
    def generate(self):
        return [User(client=self.client, object=role) for role in self.client.roles.list()]

    def list(self, details: bool = False):
        table = (
            Table(
                "User",
                "Email",
                "Name",
                "Type",
                "Roles",
                "Capabilities",
                "Default App",
                "Last Login",
            )
            if details
            else Table("User", "Type", "Last Login", title="User Overview")
        )
        for user in track(self.client.users.list()):
            if not details:
                table.add_row(
                    user.name,
                    user.content["type"] if "type" in user.content else "",
                    (
                        datetime.utcfromtimestamp(
                            int(user.content["last_successful_login"])
                        ).strftime(TIME_FORMAT)
                        if "last_successful_login" in user.content
                        else ""
                    ),
                )
            else:
                table.add_row(
                    user.name,
                    user.content["email"] if "email" in user.content else "",
                    user.content["realname"] if "realname" in user.content else "",
                    user.content["type"] if "type" in user.content else "",
                    ", ".join(user.content["roles"]) if "roles" in user.content else "",
                    str(len(user.content["capabilities"])) if "capabilities" in user.content else 0,
                    user.content["defaultApp"] if "defaultApp" in user.content else "",
                    (
                        str(
                            datetime.utcfromtimestamp(
                                int(user.content["last_successful_login"])
                            ).strftime(TIME_FORMAT)
                        )
                        if "last_successful_login" in user.content
                        else ""
                    ),
                )
        console = Console()
        console.print(table)

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        return DeepDiff(
            {
                str(user.name): {"access": user.access, "content": user.content}
                for user in src_client.client.users.list()
            },
            {
                str(user.name): {"access": user.access, "content": user.content}
                for user in dest_client.client.users.list()
            },
            ignore_order=True,
        )

    def create(self, reference_obj: spl_client.Role):
        # print(reference_obj.__dict__)
        pass

    def update(self, **kwargs):
        # print(kwargs)
        pass


class Indexes(ObjectList):
    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        return DeepDiff(
            {
                str(index.name): {"access": index.access, "content": index.content}
                for index in src_client.client.indexes.list()
            },
            {
                str(index.name): {"access": index.access, "content": index.content}
                for index in dest_client.client.indexes.list()
            },
            ignore_order=True,
        )


class Apps(ObjectList):
    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        return DeepDiff(
            {
                str(app.name): {"access": app.access, "content": app.content}
                for app in src_client.client.apps.list()
            },
            {
                str(app.name): {"access": app.access, "content": app.content}
                for app in dest_client.client.apps.list()
            },
            ignore_order=True,
        )
