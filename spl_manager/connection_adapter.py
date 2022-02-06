"""Splunk Connection-Adapter.

Let's you list certain properties of a connected Splunk Instance,
such as Apps, Event_Types, Indexes, Roles, SavedSearches, Users, ...
"""

from typing import Optional

import splunklib.client as spl_client
from InquirerPy import inquirer

from spl_manager.objects import Apps, EventTypes, Indexes, Inputs, Roles, SavedSearches, Users

TIME_FORMAT = "%d.%m.%Y %H:%M:%S"


class ConnectionAdapter:  # pylint: disable=R0902
    """Splunk API client adaper to use in other modules."""

    spl: spl_client.Service

    def __init__(self, parent: object, name: str):
        self._name = name
        self._interactive = parent._interactive
        self._log = parent._log
        self._settings = parent._settings
        self.owner = None
        self.sharing = None
        self.user = None
        self.client: spl_client.Service = spl_client.connect(
            host=self._settings.CONNECTIONS[name]["host"],
            port=self._settings.CONNECTIONS[name]["port"],
            username=self._settings.CONNECTIONS[name]["username"],
            password=self._settings.CONNECTIONS[name]["password"],
        )
        self._log.info(
            f"Connection adapter for '{self._name}' ({self.client.authority})"
            + f" as user '{self.client.username}' with namespace: {self.client.namespace}."
        )

    def __str__(self):
        self._log.info(f"Connection user {self.client.username}")
        return (
            f"Connection adapter for '{self._name}' ({self.client.authority})"
            + f" as user '{self.client.username}'."
        )

    @property
    def roles(self):
        """Splunk Roles."""
        return Roles(self.client, accessor=self.client.roles, interactive=self._interactive)

    @property
    def users(self):
        """Splunk Users."""
        return Users(self.client, accessor=self.client.users, interactive=self._interactive)

    @property
    def apps(self):
        """Splunk Applications."""
        return Apps(self.client, accessor=self.client.apps, interactive=self._interactive)

    @property
    def indexes(self):
        """Splunk Indexes."""
        return Indexes(self.client, accessor=self.client.indexes, interactive=self._interactive)

    @property
    def event_types(self):
        """Splunk Event_Types."""
        return EventTypes(
            self.client, accessor=self.client.event_types, interactive=self._interactive
        )

    @property
    def saved_searches(self):
        """Splunk SavedSearches."""
        return SavedSearches(
            self.client, accessor=self.client.saved_searches, interactive=self._interactive
        )

    @property
    def inputs(self):
        """Splunk Inputs."""
        return Inputs(
            client=self.client, accessor=self.client.inputs, interactive=self._interactive
        )

    def restart(self):
        """Restart the connected Splunk Instance."""
        if self._name in ["localhost", "nxtp-onprem"]:
            self._log.info("Restarting instance...")
            self.client.restart(timeout=360)
            self._log.info("Up again.")

    def namespace(
        self,
        context: bool,
        app: Optional[str] = None,  # "system",
        sharing: Optional[str] = None,  # "system",
        owner: Optional[str] = None,  # "admin",
    ):  # pylint: disable=R0912
        """Set the namespace context used during Splunk interaction.

        Args:
            context (bool): Whether or not to use context
                (If True, asks for context input).
            app (str, optional): The app scope to use for context.
            sharing (str, optional): The sharing scope to use for context.
            owner (str, optional): The owner scope to use for context.
        """
        if context:
            self._log.info(f"Determining namespace/context for connection '{self._name}'")
        app_list = ["-", None] + [
            app.name for app in self.client.apps.list() if app.content.disabled != "1"
        ]
        owner_list = [None, "-", "nobody"] + [user.name for user in self.client.users.list()]
        sharing_list = [None, "-", "global", "system", "app", "user"]
        # APP
        if context and self._interactive and app is None:
            self.app = inquirer.select(  # pylint: disable=W0201
                message=f"Select an application context for {self._name}:",
                choices=app_list,
                default=None,
            ).execute()
        elif app not in app_list:
            raise ValueError(f"Application '{app}' does not exist")
        else:
            self.app = app  # pylint: disable=W0201
        # SHARING
        if context and self._interactive and sharing is None:
            self.sharing = inquirer.select(
                message="Select a sharing level:",
                choices=sharing_list,
                default=None,
            ).execute()
        elif sharing not in sharing_list:
            raise ValueError("Invalid sharing mode")
        else:
            self.sharing = sharing
        # OWNER
        if context and self._interactive and owner is None:
            self.owner = inquirer.select(
                message="Select an owner:",
                choices=owner_list,
                default=None,
            ).execute()
        elif owner not in owner_list:
            raise ValueError("User does not exist")
        else:
            self.owner = owner
        if self.app is not None:
            self.client.namespace["app"] = self.app
        if self.sharing is not None:
            self.client.namespace["sharing"] = self.sharing
        if self.owner is not None:
            self.client.namespace["owner"] = self.owner
        self._log.info(f"Switched to namespace: {self.client.namespace} for current execution.")
        return self.client.namespace
