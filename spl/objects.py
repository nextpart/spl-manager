# -*- coding: utf-8 -*-
import logging
from datetime import datetime

import splunklib.binding as spl_context
import splunklib.client as spl_client
from deepdiff import DeepDiff
from InquirerPy import inquirer

# from rich import inspect, print  # pylint: disable=W0622
from rich.console import Console
from rich.progress import track
from rich.table import Table

"""Splunk object abstractions."""

TIME_FORMAT = "%d.%m.%Y %H:%M:%S"


class Object:
    """A singe splunk object instance."""

    SYNC_EXCLUDE = []
    __name__ = "generic"

    def __init__(self, client, obj):
        self.client = client
        self.obj = obj

    def __str__(self):
        return self.obj.name


class ObjectList:
    """Multiple splunk objects."""

    SUBTYPE = Object
    __name__ = SUBTYPE.__name__

    def __init__(self, client: spl_client.Service, accessor, interactive=False):
        """[summary]

        Args:
            client (spl_client.Service): The splunk service connection client in use.
            accessor (object): Property object access, like a splunklib.client.User
            interactive (bool, optional): Interactive CLI user questionary. Defaults to False.
        """
        self.client = client
        self._interactive = interactive
        self._accessor = accessor
        self.items = self.generate()

    def __str__(self):
        return str([str(item) for item in self.items])

    def generate(self) -> list:
        """Object list generator.

        Returns:
            list: List with subtypes incl. content list from remote.
        """
        return [
            self.SUBTYPE(client=self.client, obj=item)
            for item in self._accessor.list()
            if not ("_state" in item.__dict__ and "access" in item.__dict__["_state"])
            or (
                (
                    self.client.namespace["app"] is None
                    or self.client.namespace["app"] == item.access.app
                )
                and (
                    self.client.namespace["sharing"] is None
                    or self.client.namespace["sharing"] == item.access.sharing
                )
                and (
                    self.client.namespace["owner"] is None
                    or self.client.namespace["owner"] == item.access.owner
                )
            )
        ]

    @staticmethod
    def _diff(src_client, src_client_accessor, dest_client, dest_client_accessor) -> DeepDiff:
        """Differencial comparison of object lists from two instances.

        Args:
            src_client (spl.connection_adapter.ConnectionAdapter): [description]
            src_client_accessor (Any): Property object access, like splunklib.client.users
            dest_client (spl.connection_adapter.ConnectionAdapter): [description]
            dest_client_accessor (Any): Property object access, like splunklib.client.users

        Returns:
            DeepDiff: Source and destination object property list comparison
        """
        return DeepDiff(
            {
                str(item.name): {
                    # "access": item.access,
                    "content": item.content
                }
                for item in src_client_accessor
                if not ("_state" in item.__dict__ and "access" in item.__dict__["_state"])
                or (
                    (
                        src_client.namespace["app"] is None
                        or src_client.namespace["app"] == item.access.app
                    )
                    and (
                        src_client.namespace["sharing"] is None
                        or src_client.namespace["sharing"] == item.access.sharing
                    )
                    and (
                        src_client.namespace["owner"] is None
                        or src_client.namespace["owner"] == item.access.owner
                    )
                )
            },
            {
                str(item.name): {
                    # "access": item.access,
                    "content": item.content
                }
                for item in dest_client_accessor
                if not ("_state" in item.__dict__ and "access" in item.__dict__["_state"])
                or (
                    (
                        dest_client.namespace["app"] is None
                        or dest_client.namespace["app"] == item.access.app
                    )
                    and (
                        dest_client.namespace["sharing"] is None
                        or dest_client.namespace["sharing"] == item.access.sharing
                    )
                    and (
                        dest_client.namespace["owner"] is None
                        or dest_client.namespace["owner"] == item.access.owner
                    )
                )
            },
            ignore_order=True,
        )

    def check_create(self, reference_obj, simulate: bool = False) -> bool:
        """Object item creation verification by user/args or simulation.

        Args:
            reference_obj (Any): Reference object, like a splunklib.client.User
            simulate (bool, optional): Whether to simulate action or not. Defaults to False.

        Returns:
            bool: Evaluation result if operation should be performed.
        """
        if (
            self._interactive
            and not inquirer.confirm(
                message=f"Do you want to create {self.__name__} '{reference_obj.name}' on "
                + f"{self.client.host}?",
                default=True,
            ).execute()
        ):
            return False
        if simulate:
            logging.info(f"Simulated {self.__name__} creation of '{reference_obj.name}'.")
            return False
        logging.info(
            f"Creating {self.__name__} entity '{reference_obj.name}' on {self.client.host}."
        )
        return True

    def _create(self, reference_obj, simulate: bool = False):
        if not self.check_create(reference_obj=reference_obj, simulate=simulate):
            return
        args = {
            field: reference_obj.content[field]
            for field in reference_obj.fields["optional"]
            if field in reference_obj.content
            and reference_obj.content[field] is not None
            and reference_obj.content[field] != "-1"
            and field not in self.SUBTYPE.SYNC_EXCLUDE
        }

        if (
            "capabilities" in reference_obj.fields["required"]
            or "capabilities" in reference_obj.fields["optional"]
        ):
            args["capabilities"] = []
            for capability in reference_obj.capabilities:
                if capability in self.client.capabilities:
                    args["capabilities"].append(capability)
                else:
                    logging.warning(
                        f"The {self.__name__} {reference_obj.name} has an unknown capability "
                        + " ('{capability}') assigned. We'll skip this assignment."
                    )
        try:
            if isinstance(reference_obj, spl_client.User):
                self._accessor.create(
                    reference_obj.name, password="mySplunkDevDefaultP4ssw0rd!", **args
                )
            else:
                self._accessor.create(reference_obj.name, **args)
        except spl_context.HTTPError as error:
            logging.error(error)

    def check_update(self, reference_obj, prop, simulate: bool = False):
        try:
            old_value = self._accessor[reference_obj.name]
            for item in prop.split("."):
                old_value = old_value[item]
        except KeyError:
            old_value = None
        new_value = reference_obj
        try:
            for item in prop.split("."):
                new_value = new_value[item]
        except KeyError:
            new_value = None

        if (
            old_value in [None, "-1"]
            and new_value in [None, "-1"]
            or prop.replace("content.", "") in self.SUBTYPE.SYNC_EXCLUDE
        ):
            logging.info(
                f"Ignoring {self.__name__} update '{reference_obj.name}' for "
                + f"'{prop.replace('content.','')}' from '{old_value}' to '{new_value}'."
            )
            return False, None
        if (
            self._interactive
            and not inquirer.confirm(
                message=f"Do you want to update {self.__name__} '{reference_obj.name}' prop named "
                + f"{prop.replace('content.','')} from '{old_value}' to '{new_value}'?",
                default=False,
            ).execute()
        ):
            logging.info(
                f"Skipping {self.__name__} update '{reference_obj.name}' for "
                + f"'{prop.replace('content.','')}' from '{old_value}' to '{new_value}'."
            )
            return False, None
        if simulate:
            logging.info(
                f"Simulated {self.__name__} update '{reference_obj.name}' for "
                + f"'{prop.replace('content.','')}' from '{old_value}' to '{new_value}'."
            )
            return False, None
        logging.info(
            f"Updating {self.__name__} entity '{reference_obj.name}' prop "
            + f"'{prop.replace('content.','')}' from '{old_value}' to '{new_value}'."
        )
        return True, new_value

    def _update(self, reference_obj, prop, simulate: bool = False):
        update, new_value = self.check_update(
            reference_obj=reference_obj,
            prop=prop,
            simulate=simulate,
        )
        if not update:
            return
        logging.info(
            f"Updating {self.__name__} on {self.client.host}: {prop.replace('content.','')}"
        )
        try:
            self._accessor[reference_obj.name].update(**{prop.replace("content.", ""): new_value})
        except spl_context.HTTPError as error:
            logging.error(error)

    def check_delete(self, name: str, simulate: bool = False):
        """Object item deletion verification by user/args or simulation.

        Args:
            name (str): Object name that should be deleted.
            simulate (bool, optional): Whether to simulate action or not. Defaults to False.

        Returns:
            bool: Evaluation result if operation should be performed.
        """
        if (
            self._interactive
            and not inquirer.confirm(
                message=f"Do you want to delete {self.__name__} '{name}' on {self.client.host}?",
                default=False,
            ).execute()
        ):
            return False
        if simulate:
            logging.info(f"Simulated {self.__name__} creation of '{name}'.")
            return False
        logging.info(f"Deleting {self.__name__} entity '{name}'.")
        return True

    def _delete(self, name: str, simulate: bool = False):
        """[summary]

        Args:
            name (str): Object name that should be deleted.
            simulate (bool, optional): Whether to simulate action or not. Defaults to False.
        """
        if not self.check_delete(name=name, simulate=simulate):
            return
        logging.info(f"Deleting {self.__name__} '{name}' on {self.client.host}")
        try:
            self._accessor.delete(name=name)
        except spl_context.HTTPError as error:
            logging.error(error)

    def list(self, details: bool = False):
        """Tabular representation of object list.

        Args:
            details (bool, optional): Extended table with additional columns. Defaults to False.
        """
        if not details:
            table = Table(
                *self.SUBTYPE.OVERVIEW_FIELDS.keys(),
                title=f"{self.__name__} Overview",
                show_lines=False,
            )
        elif "access" not in self._accessor.list()[0].__dict__["_state"]:
            table = Table(
                *self.SUBTYPE.DETAIL_FIELDS.keys(),
                title=f"{self.__name__} Overview",
                show_lines=False,
            )
        else:
            table = Table(
                *(
                    list(self.SUBTYPE.DETAIL_FIELDS.keys())
                    + ["App", "Sharing", "Owner", "Read", "Write"]
                ),
                title=f"{self.__name__} Overview",
                show_lines=False,
            )
        for item in track(self._accessor.list()):
            # Context based selection
            if ("_state" in item.__dict__ and "access" in item.__dict__["_state"]) and (
                (
                    self.client.namespace["app"] is not None
                    and self.client.namespace["app"] != item.access.app
                )
                or (
                    self.client.namespace["sharing"] is not None
                    and self.client.namespace["sharing"] != item.access.sharing
                )
                or (
                    self.client.namespace["owner"] is not None
                    and self.client.namespace["owner"] != item.access.owner
                )
            ):
                continue

            row = [item.name]
            fields = (
                self.SUBTYPE.DETAIL_FIELDS.items()
                if details
                else self.SUBTYPE.OVERVIEW_FIELDS.items()
            )
            for key, val in fields:
                if val is None:
                    continue
                printable = item.content[val] if val in item.content else ""
                if val == "capabilities" and item.content[val] == item.capabilities:
                    printable = "all"
                try:
                    if val not in item.content:
                        raise KeyError
                    if isinstance(printable, list):
                        printable = ", ".join(item.content[val])
                    elif (
                        isinstance(printable, str) and printable.replace("-", "").isdigit()
                    ) or isinstance(printable, int):
                        printable = int(printable)
                        if printable < 0:
                            printable = None
                        elif printable == 0:
                            printable = False
                        elif printable == 1:
                            printable = True
                        elif val.startswith("last_"):
                            printable = datetime.utcfromtimestamp(printable).strftime(TIME_FORMAT)
                    elif isinstance(printable, str):
                        printable.encode("ascii")
                    row.append(str(printable))
                except:
                    row.append("")
            if details and "access" in item.__dict__["_state"]:
                row += [
                    item.access["app"],
                    item.access["sharing"],
                    item.access["owner"],
                    ", ".join(item.access["perms"]["read"]),
                    ", ".join(item.access["perms"]["write"]),
                ]
            table.add_row(*list(str(prop) for prop in row))
        console = Console()
        console.print(table)


class User(Object):

    OVERVIEW_FIELDS = {
        "User": None,
        "Type": "type",
        "Last Login": "last_successful_login",
    }
    DETAIL_FIELDS = {
        **OVERVIEW_FIELDS,
        **{
            "Email": "email",
            "Name": "realname",
            "Roles": "roles",
            "Capabilities": "capabilities",
            "Default App": "defaultApp",
        },
    }
    SYNC_EXCLUDE = ["capabilities", "password", "last_successful_login"]
    __name__ = "User"


class Users(ObjectList):

    SUBTYPE = User

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.users.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.users.list(),
        )


class Index(Object):

    OVERVIEW_FIELDS = {
        "Name": None,
        "Type": "datatype",
        "Size MB": "maxTotalDataSizeMB",
    }
    DETAIL_FIELDS = {
        **OVERVIEW_FIELDS,
        **{
            "Path": "homePath",
            "Integrity": "enableDataIntegrityControl",
            "Buckets MB": "maxDataSize",
            "Tsidx Optimization": "enableTsidxReduction",
        },
    }
    SYNC_EXCLUDE = []
    __name__ = "Index"


class Indexes(ObjectList):

    SUBTYPE = Index

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.indexes.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.indexes.list(),
        )


class App(Object):

    OVERVIEW_FIELDS = {"ID": None, "Title": "label", "Version": "version"}
    DETAIL_FIELDS = {
        **OVERVIEW_FIELDS,
        **{
            "Author": "author",
            "Disabled": "disabled",
            "Visible": "visible",
            "Splunkbase": "details",
            "Nav": "show_in_nav",
        },
    }
    SYNC_EXCLUDE = []
    __name__ = "App"


class Apps(ObjectList):

    SUBTYPE = App

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.apps.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.apps.list(),
        )


class Role(Object):

    OVERVIEW_FIELDS = {
        "Name": None,
        "Default App": "defaultApp",
        "Capabilities": "capabilities",
        "Imported Roles": "imported_roles",
    }
    DETAIL_FIELDS = {
        **OVERVIEW_FIELDS,
        **{
            "Indexes allowed": "srchIndexesAllowed",
            "Indexes disallowed": "srchIndexesDisallowed",
            "Search earliest": "srchTimeEarliest",
        },
    }
    SYNC_EXCLUDE = []
    __name__ = "Role"


class Roles(ObjectList):

    SUBTYPE = Role

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.roles.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.roles.list(),
        )


class EventType(Object):

    OVERVIEW_FIELDS = {
        "Name": None,
        "App": "eai:appName",
        # "Search": "search",
        "Tags": "tags",
    }
    DETAIL_FIELDS = {
        **OVERVIEW_FIELDS,
        **{"Description": "description", "Disabled": "disabled", "Priority": "priority"},
    }
    SYNC_EXCLUDE = []
    __name__ = "EventType"


class EventTypes(ObjectList):

    SUBTYPE = EventType

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.event_types.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.event_types.list(),
        )


class SavedSearch(Object):

    OVERVIEW_FIELDS = {"Name": None, "Search": "search"}
    DETAIL_FIELDS = {
        **OVERVIEW_FIELDS,
        **{
            "Visible": "is_visible",
            "Disabled": "disabled",
            "Scheduled": "is_scheduled",
        },
    }
    SYNC_EXCLUDE = []
    __name__ = "SavedSearch"


class SavedSearches(ObjectList):

    SUBTYPE = SavedSearch

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.saved_searches.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.saved_searches.list(),
        )


class Input(Object):

    OVERVIEW_FIELDS = {
        "Name": None,
    }
    DETAIL_FIELDS = {
        **OVERVIEW_FIELDS,
        **{},
    }
    SYNC_EXCLUDE = []
    __name__ = "Input"


class Inputs(ObjectList):

    SUBTYPE = Input

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.inputs.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.inputs.list(),
        )
