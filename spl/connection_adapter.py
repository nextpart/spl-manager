# -*- coding: utf-8 -*-

from typing import Optional

import splunklib.binding as spl_context
import splunklib.client as spl_client
from InquirerPy import inquirer
from rich import inspect, print  # pylint: disable=W0622

from spl.objects import Apps, EventTypes, Indexes, Inputs, Roles, SavedSearches, Users

TIME_FORMAT = "%d.%m.%Y %H:%M:%S"


class ConnectionAdapter:
    """Splunk API client adaper to use in other modules.

    Raises:
        ValueError: [description]
    """

    spl: spl_client.Service

    def __init__(self, parent: object, name: str):
        self._name = name
        self._interactive = parent._interactive
        self._log = parent._log
        self._settings = parent._settings
        self.client: spl_client.Service = spl_client.connect(
            host=self._settings.CONNECTIONS[name]["host"],
            port=self._settings.CONNECTIONS[name]["port"],
            username=self._settings.CONNECTIONS[name]["username"],
            password=self._settings.CONNECTIONS[name]["password"],
        )
        # self.namespace(app, sharing, owner)
        self._log.info(
            f"Connection adapter for '{self._name}' ({self.client.authority})"
            + f" as user '{self.client.username}' with namespace: {self.client.namespace}."
        )

    @property
    def roles(self):
        return Roles(self.client, accessor=self.client.roles, interactive=self._interactive)

    @property
    def users(self):
        return Users(self.client, accessor=self.client.users, interactive=self._interactive)

    @property
    def apps(self):
        return Apps(self.client, accessor=self.client.apps, interactive=self._interactive)

    @property
    def indexes(self):
        return Indexes(self.client, accessor=self.client.indexes, interactive=self._interactive)

    @property
    def event_types(self):
        return EventTypes(
            self.client, accessor=self.client.event_types, interactive=self._interactive
        )

    @property
    def saved_searches(self):
        return SavedSearches(
            self.client, accessor=self.client.saved_searches, interactive=self._interactive
        )

    @property
    def inputs(self):
        return Inputs(
            client=self.client, accessor=self.client.inputs, interactive=self._interactive
        )

    def __str__(self):
        self._log.info(f"Connection user {self.client.username}")
        return (
            f"Connection adapter for '{self._name}' ({self.client.authority})"
            + f" as user '{self.client.username}'."
        )

    def test(self):
        return "test"

    def restart(self):
        if self._name in ["localhost", "nxtp-onprem"]:
            self._log.info("Restarting instance...")
            self.client.restart(timeout=360)
            self._log.info("Up again.")

    def namespace(
        self,
        app: Optional[str] = None,  # "system",
        sharing: Optional[str] = None,  # "system",
        owner: Optional[str] = None,  # "admin",
    ):
        """Namespace context for splunk interaction.

        Args:
            app ([type], optional): [description]. Defaults to None.
            sharing ([type], optional): [description]. Defaults to None.
            owner ([type], optional): [description]. Defaults to None.

        Raises:
            ValueError: [description]

        """
        if app not in [app.name for app in self.client.apps.list()]:
            app = None
        if self._interactive and app is None:
            self.app = inquirer.select(
                message="Select an application context:",
                choices=["system"]
                + [
                    app.name
                    for app in self.client.apps.list()
                    if app.name not in self._settings.APPS.exclude
                ],
                default="system",
            ).execute()
        elif app is None:
            self.app = "system"
        elif app not in [app.name for app in self.client.apps.list()]:
            raise ValueError(f"Application '{app}' does not exist")
        if self._interactive and sharing is None:
            self.sharing = inquirer.select(
                message="Select a sharing level:",
                choices=["global", "system", "app", "user"],
                default="system",
            ).execute()
        elif sharing is None:
            self.sharing = "system"
        elif sharing not in ["global", "system", "app", "user"]:
            raise ValueError("Invalid sharing mode")
        if self._interactive and owner is None:
            self.owner = inquirer.select(
                message="Select an owner:",
                choices=[user.name for user in self.client.users.list()],
                default="admin",
            ).execute()
        elif owner is None:
            self.owner = "admin"
        elif owner not in [user.name for user in self.client.users.list()]:
            raise ValueError("User does not exist")
        # if self.sharing != sharing or self.owner != owner or self.app != app:
        self.client.namespace = spl_context.namespace(
            sharing=sharing,
            app=app,
            owner=owner,
        )
        return self.client.namespace

    # def create_index(self, name: str = None, app=None, sharing=None, owner=None):
    #     if name is None:
    #         name = inquirer.text(message="Name of the index to create:").execute()
    #     self.client.indexes.create(
    #         name=name, namespace=self.namespace(app=app, sharing=sharing, owner=owner)
    #     )

    # def create_role(self, role):
    #     args = {
    #         field: role.content[field]
    #         for field in role.fields["optional"]
    #         if field in role.content
    #         and role.content[field] is not None
    #         and role.content[field] != "-1"
    #         and field
    #         not in [
    #             "capabilities",
    #         ]
    #     }
    #     args["capabilities"] = []
    #     for capability in role.capabilities:
    #         if capability in self.client.capabilities:
    #             args["capabilities"].append(capability)
    #         else:
    #             self._log.warning(
    #                 f"The role {role.name} has an unknown capability {capability}"
    #                 + " assignes. We'll skip this assignment. You can sync later on."
    #             )
    #     try:
    #         self.client.roles.create(name=role.name, **args)
    #     except spl_context.HTTPError as error:
    #         self._log.error(error)

    # def update_role(self, **kwargs):
    #     print(kwargs)
    # args = {
    #     field: role.content[field]
    #     for field in role.fields["optional"]
    #     if field in role.content
    #     and role.content[field] is not None
    #     and role.content[field] != "-1"
    #     and field
    #     not in [
    #         "capabilities",
    #     ]
    # }
    # args["capabilities"] = []
    # for capability in role.capabilities:
    #     if capability in self.client.capabilities:
    #         args["capabilities"].append(capability)
    #     else:
    #         self._log.warning(f"The role {role.name} has an unknown capability {capability}"
    #         + " assignes. We'll skip this assignment. You can sync later on.")
    # try:
    #     self.client.roles.create(name=role.name, **args)
    # except spl_context.HTTPError as error:
    #     self._log.error(error)
