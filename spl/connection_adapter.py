# -*- coding: utf-8 -*-
import splunklib.binding as spl_context
import splunklib.client as spl_client
from InquirerPy import inquirer
from rich import print  # pylint: disable=W0622
from rich.progress import track


class ConnectionAdapter:
    """Splunk API client adaper to use in other modules.

    Raises:
        ValueError: [description]
    """

    spl: spl_client.Service

    def __init__(self, parent: object, name: str, sharing="system"):
        self._name = name
        self._interactive = parent._interactive
        self._log = parent._log
        self._settings = parent._settings.CONNECTIONS[name]
        self._log.debug(f"Creating resource management interface for {name}.")
        self.client: spl_client.Service = spl_client.connect(
            host=self._settings["host"],
            port=self._settings["port"],
            username=self._settings["username"],
            password=self._settings["password"],
            sharing=sharing,
        )

    def custom_apps(self):
        """Provide list of custom (non-default) apps, installed on an instance."""
        for app in track(self.client.apps.list()):
            if app.name in self._settings.APPS.exclude:
                continue
            print(f" - Id:       '{app.name}'")
            if "author" in app.content:
                print(f"   Author:   {app.content['author']}")
            # if "description" in app.content.keys():
            #     print(f"   Author:   {app.content['description']}")
            if "label" in app.content:
                print(f"   Label:    {app.content['label']}")
            if "version" in app.content:
                print(f"   Version:  {app.content['version']}")
            print(
                "   State:    "
                + ("disabled" if app.content["disabled"] == "1" else "enabled")
                + "/"
                + ("visible" if app.content["visible"] == "1" else "hidden")
            )
            print("")

    def indexes(self):
        for index in self.client.indexes.list():
            print(f"- {index.name}")

    def users(self):
        for user in self.client.users.list():
            print(f"- {user.name}")

    def roles(self):
        for role in self.client.roles.list():
            print(f"- {role.name}: {role.content['capabilities']}")

    def __str__(self):
        return f"Connection adapter for '{self._name}'."

    def test(self):
        return "test"

    def namespace(self, app=None, sharing=None, owner=None):
        """Namespace context for splunk interaction.

        Args:
            app ([type], optional): [description]. Defaults to None.
            sharing ([type], optional): [description]. Defaults to None.
            owner ([type], optional): [description]. Defaults to None.

        Raises:
            ValueError: [description]
            ValueError: [description]
            ValueError: [description]

        Returns:
            [type]: [description]
        """
        if self._interactive and app is None:
            self.app = inquirer.select(
                message="Select an application context:",
                choices=[app.name for app in self.client.apps.list()],
                default="search",
            ).execute()
        elif app is None:
            self.app = "search"
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
                message="Select a sharing level:",
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

    @property
    def index_names(self):
        return [index.name for index in self.client.indexes.list()]

    @property
    def user_names(self):
        return [user.name for user in self.client.users.list()]

    @property
    def app_names(self):
        return [app.name for app in self.client.apps.list()]

    @property
    def role_names(self):
        return list(role.name for role in self.client.roles.list()).sort()

    def create_index(self, name: str = None, app=None, sharing=None, owner=None):
        if name is None:
            name = inquirer.text(message="Name of the index to create:").execute()
        self.client.indexes.create(
            name=name, namespace=self.namespace(app=app, sharing=sharing, owner=owner)
        )

    def create_role(self, role):
        self._log.warning(f"Creating role : {role.content}")
        args = {
            field: role.content[field]
            for field in role.fields["optional"]
            if field in role.content
            and role.content[field] is not None
            and field
            not in [
                "srchTimeEarliest",
            ]
        }
        try:
            self.client.roles.create(name=role.name, **args)
        except spl_context.HTTPError as error:
            self._log.error(error)
