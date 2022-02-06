# pylint: disable=R0903,R0912,R0913
"""Splunk object abstractions."""

import logging
from datetime import datetime
from typing import Dict, List

import splunklib.binding as spl_context
import splunklib.client as spl_client
from deepdiff import DeepDiff
from InquirerPy import inquirer
from rich.console import Console
from rich.progress import track
from rich.table import Table

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
        self.__name__ = type(self._accessor).__name__

    def __str__(self):
        return str([str(item) for item in self.items])

    def generate(self) -> List:
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
            src_client (spl.connection_adapter.ConnectionAdapter): Source Instance Client
            src_client_accessor (Any): Property object access, like splunklib.client.users
            dest_client (spl.connection_adapter.ConnectionAdapter): Destination Instance Client
            dest_client_accessor (Any): Property object access, like splunklib.client.users

        Returns:
            DeepDiff: Source and destination object property list comparison
        """
        return DeepDiff(
            {str(item.name): {"content": item.content} for item in src_client_accessor},
            {str(item.name): {"content": item.content} for item in dest_client_accessor},
            ignore_order=True,
        )

    def get_args_right(self, reference_obj) -> Dict:
        """Check if specified arguments can be assigned to the Splunk instance.

        Args:
            reference_obj (Any): Reference object, like a splunklib.client.User

        Returns:
            Dict: Arguments that can be assigned to the Splunk instance.
        """
        args = {
            field: reference_obj.content[field]
            for field in reference_obj.__dict__["_state"]["content"].keys()
            if field in reference_obj.content
            and reference_obj.content[field] is not None
            and reference_obj.content[field] != "-1"
            and reference_obj.fields["required"] + reference_obj.fields["optional"]
            and field not in self.SUBTYPE.SYNC_EXCLUDE + ["defaultApp"]
        }

        # Check if required capabilities exist on target system
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
                        + f"('{capability}') assigned. We'll skip this assignment."
                    )

        if (
            "defaultApp" in reference_obj.fields["required"]
            or "defaultApp" in reference_obj.fields["optional"]
        ):
            if reference_obj["defaultApp"] in [app.name for app in self.client.apps.list()]:
                args["defaultApp"] = reference_obj["defaultApp"]
            elif reference_obj["defaultApp"]:
                logging.warning(
                    f"The {self.__name__} {reference_obj.name} has an unknown default App "
                    + f"('{reference_obj['defaultApp']}') assigned. We'll skip this assignment."
                )

        # Check if required roles exist on target system
        if (
            "roles" in reference_obj.fields["required"]
            or "roles" in reference_obj.fields["optional"]
        ):
            args["roles"] = []
            for role in reference_obj.roles:
                if role in self.client.roles:
                    args["roles"].append(role)
                else:
                    logging.warning(
                        f"The {self.__name__} {reference_obj.name} has an unknown role "
                        + f"('{role}') assigned. We'll skip this assignment."
                    )
        return args

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
            for field in reference_obj.__dict__["_state"]["content"].keys()
            if field in reference_obj.content
            and reference_obj.content[field] is not None
            and reference_obj.content[field] != "-1"
            and field not in self.SUBTYPE.SYNC_EXCLUDE + ["defaultApp"]
            and (
                reference_obj.fields["required"] + reference_obj.fields["optional"] == []
                or field in reference_obj.fields["required"] + reference_obj.fields["optional"]
            )
        }

        # Check if required capabilities exist on target system
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
                        + f"('{capability}') assigned. We'll skip this assignment."
                    )
        if (
            "imported_roles" in reference_obj.fields["required"]
            or "imported_roles" in reference_obj.fields["optional"]
        ):
            args["imported_roles"] = []
            for imported_role in reference_obj.content["imported_roles"]:
                if imported_role in [role.name for role in self.client.roles.list()]:
                    args["imported_roles"].append(imported_role)
                else:
                    logging.warning(
                        f"The {self.__name__} {reference_obj.name} has an unknown imported role "
                        + f"('{imported_role}'). We'll skip this assignment."
                    )
        if (
            "defaultApp" in reference_obj.fields["required"]
            or "defaultApp" in reference_obj.fields["optional"]
        ):
            if reference_obj["defaultApp"] in [app.name for app in self.client.apps.list()]:
                args["defaultApp"] = reference_obj["defaultApp"]
            elif reference_obj["defaultApp"]:
                logging.warning(
                    f"The {self.__name__} {reference_obj.name} has an unknown default App "
                    + f"('{reference_obj['defaultApp']}') assigned. We'll skip this assignment."
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

    def check_update(
        self, reference_obj, prop, simulate: bool = False, src_value=None, dest_value=None
    ):
        """Check if Splunk Objects on destination instance can be updated.

        Args:
            reference_obj (Any): Reference object, like a splunklib.client.User
        """
        # Cut 'content.' from prop
        print_prop = prop.replace("content.", "")

        if not (
            print_prop in self._accessor[reference_obj.name].content
            and self._accessor[reference_obj.name].content[print_prop] is not None
            and self._accessor[reference_obj.name].content[print_prop] != "-1"
            and print_prop not in self.SUBTYPE.SYNC_EXCLUDE + ["defaultApp"]
            and (
                self._accessor[reference_obj.name].fields["required"]
                + self._accessor[reference_obj.name].fields["optional"]
                == []
                or print_prop
                in self._accessor[reference_obj.name].fields["required"]
                + self._accessor[reference_obj.name].fields["optional"]
            )
        ):
            logging.info(
                f"Ignoring {type(reference_obj).__name__} update '{reference_obj.name}' for "
                + f"'{print_prop}' from '{dest_value}' to '{src_value}'."
            )
            return False

        if dest_value in [None, "-1"] and src_value in [None, "-1"]:
            logging.info(
                f"Ignoring {type(reference_obj).__name__} update '{reference_obj.name}' for "
                + f"'{print_prop}' from '{dest_value}' to '{src_value}'."
            )
            return False
        if print_prop == "capabilities":
            if src_value is not None and not src_value in self.client.capabilities:
                logging.error(
                    f"Can not assign capability '{src_value}' to {type(reference_obj).__name__} "
                    + f"'{reference_obj.name}' as it does not exist on destination instance!"
                )
                return False
        if print_prop == "defaultApp":
            if src_value is not None and not src_value in [
                app.name for app in self.client.apps.list()
            ]:
                logging.error(
                    f"Can not assign default app '{src_value}' to {type(reference_obj).__name__} "
                    + f"'{reference_obj.name}' as it does not exist on destination instance!"
                )
                return False
        if print_prop == "imported_roles":
            if src_value is not None and not src_value in [
                role.name for role in self.client.roles.list()
            ]:
                logging.error(
                    f"Can not assign role '{src_value}' to {type(reference_obj).__name__} "
                    + f"'{reference_obj.name}' as it does not exist on destination instance!"
                )
                return False
        # USER QUESTION
        if self._interactive:
            if dest_value is None and src_value is not None:
                if not inquirer.confirm(
                    message=f"Do you want to set {self.__name__} '{reference_obj.name}' prop named "
                    + f"'{print_prop}' to '{src_value}'?",
                    default=False,
                ).execute():
                    logging.info(
                        f"Skipping {self.__name__} update '{reference_obj.name}' for "
                        + f"'{print_prop}' from '{dest_value}' to '{src_value}'."
                    )
                    return False
            elif dest_value is not None and src_value is None:
                if not inquirer.confirm(
                    message=f"Do you want to unset {self.__name__} '{reference_obj.name}' "
                    + f"prop named '{print_prop}' of '{dest_value}'?",
                    default=False,
                ).execute():
                    logging.info(
                        f"Skipping {self.__name__} update '{reference_obj.name}' for "
                        + f"'{print_prop}' from '{dest_value}' to '{src_value}'."
                    )
                    return False
            elif not inquirer.confirm(
                message=f"Do you want to update {self.__name__} '{reference_obj.name}' prop named "
                + f"'{print_prop}' from '{dest_value}' to '{src_value}'?",
                default=False,
            ).execute():
                logging.info(
                    f"Skipping {self.__name__} update '{reference_obj.name}' for "
                    + f"'{print_prop}' from '{dest_value}' to '{src_value}'."
                )
                return False
        if simulate:
            logging.info(
                f"Simulated {self.__name__} update '{reference_obj.name}' for "
                + f"'{print_prop}' from '{dest_value}' to '{src_value}'."
            )
            return False
        if src_value is not None and dest_value is None:
            logging.info(
                f"Setting {self.__name__} entity '{reference_obj.name}' prop "
                + f"'{print_prop}' with value '{src_value}'."
            )
        elif src_value is None and dest_value is not None:
            logging.info(
                f"Unsetting {self.__name__} entity '{reference_obj.name}' prop "
                + f"'{print_prop}' of value '{dest_value}'."
            )
        else:
            logging.info(
                f"Updating {self.__name__} entity '{reference_obj.name}' prop "
                + f"'{print_prop}' from '{src_value}' to '{dest_value}'."
            )
        return True

    def _update(self, reference_obj, prop, simulate: bool = False, src_value=None, dest_value=None):
        update = self.check_update(
            reference_obj=reference_obj,
            prop=prop,
            simulate=simulate,
            src_value=src_value,
            dest_value=dest_value,
        )
        if not update:
            return
        if isinstance(
            self._accessor[reference_obj.name].content[prop.replace("content.", "")], list
        ):
            dest_value = (
                self._accessor[reference_obj.name]
                .content[prop.replace("content.", "")]
                .append(dest_value)
            )
        try:
            if prop == "content.capabilities":
                if dest_value is None and not src_value is None:
                    response = self._accessor[reference_obj.name].grant(src_value)
                else:
                    response = self._accessor[reference_obj.name].revoke(src_value)
            else:
                response = self._accessor[reference_obj.name].update(
                    **{prop.replace("content.", ""): src_value}
                )
            self._accessor[reference_obj.name].refresh()
            logging.info(response)
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
        """Delete the specified object on the Splunk instance.

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
                    self.client.namespace["app"] not in ["-", None]
                    and self.client.namespace["app"] != item.access.app
                )
                or (
                    self.client.namespace["sharing"] not in ["-", None]
                    and self.client.namespace["sharing"] != item.access.sharing
                )
                or (
                    self.client.namespace["owner"] not in ["-", None]
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
                    ", ".join(item.access["perms"]["read"])
                    if "access" in item.__dict__.keys()
                    and "perms" in item.access.keys()
                    and "read" in item.access["perms"].keys()
                    else "",
                    ", ".join(item.access["perms"]["write"])
                    if "access" in item.__dict__.keys()
                    and "perms" in item.access.keys()
                    and "write" in item.access["perms"].keys()
                    else "",
                ]
            table.add_row(*list(str(prop) for prop in row))
        console = Console()
        console.print(table)


class App(Object):
    """Splunk App Object."""

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
    """List of Splunk App Objects."""

    SUBTYPE = App

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        """Detect changes between source & destination Splunk instance."""
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.apps.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.apps.list(),
        )


class EventType(Object):
    """Splunk EventType Object."""

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
    """List of Splunk EventType Objects."""

    SUBTYPE = EventType

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        """Detect changes between source & destination Splunk instance."""
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.event_types.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.event_types.list(),
        )


class Index(Object):
    """Splunk Index Object."""

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
    STATIC_VALUES = {"archiver.maxDataArchiveRetentionPeriod": "0"}
    __name__ = "Index"


class Indexes(ObjectList):
    """List of Splunk Index Objects."""

    SUBTYPE = Index

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        """Detect changes between source & destination Splunk instance."""
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.indexes.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.indexes.list(),
        )


class Input(Object):
    """Splunk Input Object."""

    OVERVIEW_FIELDS = {
        "Name": None,
    }
    DETAIL_FIELDS = {
        **OVERVIEW_FIELDS,
        **{},
    }
    SYNC_EXCLUDE = ["assureUTF8"]
    __name__ = "Input"


class Inputs(ObjectList):
    """List of Splunk Input Objects."""

    SUBTYPE = Input

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        """Detect changes between source & destination Splunk instance."""
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.inputs.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.inputs.list(),
        )


class Role(Object):
    """Splunk Role Object."""

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
    SYNC_EXCLUDE = [
        "imported_capabilities",
        "imported_srchIndexesAllowed",
        "imported_srchIndexesDefault",
        "imported_rtSrchJobsQuota",
        "imported_srchDiskQuota",
        "imported_srchJobsQuota",
    ]
    __name__ = "Role"


class Roles(ObjectList):
    """List of Splunk Role Objects."""

    SUBTYPE = Role

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        """Detect changes between source & destination Splunk instance."""
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.roles.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.roles.list(),
        )


class SavedSearch(Object):
    """Splunk SavedSearch Object."""

    OVERVIEW_FIELDS = {
        "Name": None,
        # "Search": "search"
    }
    DETAIL_FIELDS = {
        **OVERVIEW_FIELDS,
        **{
            "Visible": "is_visible",
            "Disabled": "disabled",
            "Scheduled": "is_scheduled",
        },
    }
    SYNC_EXCLUDE = ["embed.enabled"]
    __name__ = "SavedSearch"


class SavedSearches(ObjectList):
    """List of Splunk SavedSearch Objects."""

    SUBTYPE = SavedSearch

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        """Detect changes between source & destination Splunk instance."""
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.saved_searches.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.saved_searches.list(),
        )


class User(Object):
    """Splunk User Object."""

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
    SYNC_EXCLUDE = [
        "capabilities",
        "password",
        "last_successful_login",
        "defaultAppIsUserOverride",
        "defaultAppSourceRole",
        "type",
    ]
    __name__ = "User"


class Users(ObjectList):
    """List of Splunk User Objects."""

    SUBTYPE = User

    @staticmethod
    def diff(src_client, dest_client) -> DeepDiff:
        """Detect changes between source & destination Splunk instance."""
        return ObjectList._diff(
            src_client=src_client,
            src_client_accessor=src_client.users.list(),
            dest_client=dest_client,
            dest_client_accessor=dest_client.users.list(),
        )

    # def _migrate_capabilities(self, reference_obj, prop, simulate: bool = False):
    #     prop = prop.replace("capabilities.", "")
    #     src_capabilities = reference_obj.capabilities
    #     dest_capabilities = self._accessor[reference_obj.name].capabilities
    #     missing = [
    #         capability for capability in src_capabilities if capability not in dest_capabilities
    #     ]
