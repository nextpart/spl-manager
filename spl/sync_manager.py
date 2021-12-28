# -*- coding: utf-8 -*-
import logging
from string import digits
from typing import Tuple

import splunklib.client as spl_client
from deepdiff import DeepDiff
from InquirerPy import inquirer
from rich import inspect, print  # pylint: disable=W0622

from spl.connection_adapter import ConnectionAdapter


class SyncManager:
    """Synchronization interface between source and destination connections."""

    def __init__(
        self, parent: object, interactive: bool, src: ConnectionAdapter, dest: ConnectionAdapter
    ):
        self._interactive = interactive
        self._log = parent._log
        self._settings = parent._settings
        self._log.info(f"Creating sync management from {src._name} to {dest._name}.")
        self.src = src
        self.dest = dest
        self._log.level = logging.DEBUG

    @staticmethod
    def user_diff(src: ConnectionAdapter, dest: ConnectionAdapter) -> object:
        return DeepDiff(
            {user.name: user.content for user in src.client.users.list()},
            {user.name: user.content for user in dest.client.users.list()},
            ignore_order=True,
        )

    @staticmethod
    def role_diff(src: ConnectionAdapter, dest: ConnectionAdapter) -> object:
        return DeepDiff(
            {role.name: role.content for role in src.client.roles.list()},
            {role.name: role.content for role in dest.client.roles.list()},
            ignore_order=True,
        )

    def create_role(self, role_name):
        self._log.info(
            f"Creating new role '{role_name}' based on '{self.src._name}' on instance '{self.dest._name}'."
        )
        self.dest.create_role(self.src.client.roles[role_name])

    def roles(self, simulate: bool = False):
        handler = self.DiffHandler(
            parent=self,
            subject=spl_client.Role,
            simulate=simulate,
            diff=self.role_diff,
            actions={
                "create": self.create_role,
                "srchTimeEarliest": None,
                "srchIndexesDefault": None,
                "imported_srchIndexesDefault": None
                # "remove": None,
            },
        ).sync()  # diff=self.user_diff)

    @staticmethod
    def user_diff(src, dest):
        return DeepDiff(
            {user.name: user.content for user in src.client.users.list()},
            {user.name: user.content for user in dest.client.users.list()},
            ignore_order=True,
        )

    def users(self, simulate: bool = False):
        handler = self.DiffHandler(
            parent=self,
            subject=spl_client.User,
            simulate=simulate,
            diff=self.user_diff,
            actions={
                "create": None,
                "remove": None,
                "capabilities": None,
                "perm.read": None,
            },
        ).sync()  # diff=self.user_diff)

    class DiffHandler:
        def __init__(self, parent, diff, subject: type, simulate: bool, actions: dict = {}):
            self._diff_gen = diff
            self.src = parent.src
            self.dest = parent.dest
            self._sync_actions = actions
            self.subject = subject
            self.interactive = parent._interactive
            self.simulate = simulate
            self._log = parent._log
            self._log.info(
                f"Differential synchronization of '{subject.__name__}' from '{self.src._name}'"
                + f" to '{self.dest._name}' for properties: {list(actions.keys())}"
            )

        def sync(self, create: bool = True, modify: bool = True, delete: bool = False):
            self.diff = self._diff_gen(self.src, self.dest)
            if create:
                self._create()
                self.diff = self._diff_gen(self.src, self.dest)
            if modify:
                self._update()
                self.diff = self._diff_gen(self.src, self.dest)
            if delete:
                self._delete()
                self.diff = self._diff_gen(self.src, self.dest)

        def _create(self):
            """Sync completely missing entities (i.e. User, Index, ...)."""
            if "dictionary_item_removed" in self.diff:
                items = [
                    (item, property)
                    for item, property in [
                        self._sanitize_item_path(item)
                        for item in self.diff["dictionary_item_removed"]
                    ]
                    if property == ""  # Add property in update.
                ]
                self._log.info(
                    f"Missing'{self.subject.__name__}' objects {[item for item, _ in items]}."
                )
                for item, property in items:
                    if "create" not in self._sync_actions:
                        self._log.debug(
                            f"Ignoring creation of '{self.subject.__name__}' for '{item}'."
                        )
                        continue
                    if (
                        self.interactive
                        and inquirer.confirm(
                            message=f"Do you want to create {self.subject.__name__} '{item}'?",
                            default=True,
                        ).execute()
                        is not True
                    ):
                        continue
                    if self.simulate:
                        self._log.info(
                            f"Simulated creation of '{self.subject.__name__}' for '{item}'."
                        )
                        continue
                    self._log.info(
                        f"Triggering creation of '{self.subject.__name__}' for '{item}'."
                    )
                    self._sync_actions["create"](item)

        def _delete(self):
            """Sync completely missing entities (i.e. User, Index, ...)."""
            if "dictionary_item_added" in self.diff:
                items = [
                    (item, property)
                    for item, property in [
                        self._sanitize_item_path(item)
                        for item in self.diff["dictionary_item_added"]
                    ]
                    if property == ""  # Remove properties in update.
                ]
                self._log.info(
                    f"Missing {self.subject.__name__} objects {[item for item, _ in items]}."
                )
                for item, property in items:
                    if "remove" not in self._sync_actions:
                        self._log.debug(
                            f"Ignoring removal of '{self.subject.__name__}' for '{item}'."
                        )
                        continue
                    if (
                        self.interactive
                        and inquirer.confirm(
                            message=f"Do you want to remove {self.subject.__name__} '{item}'?",
                            default=False,
                        ).execute()
                        is not True
                    ):
                        continue
                    if self.simulate:
                        self._log.info(
                            f"Simulated removal of '{self.subject.__name__}' for '{item}'."
                        )
                        continue
                    self._log.info(f"Triggering removal of '{self.subject.__name__}' for '{item}'.")
                    self._sync_actions["create"](item)

        def _update(self):
            """Synchronize all changes between src entity and dest entity."""
            # print({key: val for key,val in self.diff.items() if key not in ["dictionary_item_added", "dictionary_item_added"]})
            if "dictionary_item_removed" in self.diff:
                items = [
                    (entity_name, sanitized_path)
                    for entity_name, sanitized_path in [
                        self._sanitize_item_path(item)
                        for item in self.diff["dictionary_item_removed"]
                    ]
                    if sanitized_path != ""
                ]
                for entity_name, sanitized_path in items:
                    self._log.info(
                        f"Missing '{self.subject.__name__}' property '{sanitized_path}' for '{entity_name}'."
                    )
                    if sanitized_path not in self._sync_actions:
                        self._log.debug(
                            f"Ignoring '{self.subject.__name__}' update '{sanitized_path}' for '{entity_name}'."
                        )
                        continue
                    if (
                        self.interactive
                        and inquirer.confirm(
                            message=f"Do you want to add {self.subject.__name__} property '{sanitized_path}' for '{entity_name}'.",
                            default=True,
                        ).execute()
                        is not True
                    ):
                        continue
                    if self.simulate:
                        self._log.info(
                            f"Simulated adding '{self.subject.__name__}' property '{sanitized_path}' for '{entity_name}'."
                        )
                        continue
                    if sanitized_path in self._sync_actions and not self.simulate:
                        self._log.info(
                            f"Synchronizing entity '{entity_name}' property '{sanitized_path}' for '{entity_name}'."
                        )
                        try:
                            self._sync_actions[sanitized_path](entity_name, sanitized_path)
                        except KeyError:
                            self._log.info(
                                f"No '{self.subject.__name__}' action defined to update '{sanitized_path}' property for '{entity_name}'."
                            )
            if "dictionary_item_added" in self.diff:
                print(
                    [self._sanitize_item_path(item) for item in self.diff["dictionary_item_added"]]
                )
                items = [
                    (entity_name, sanitized_path)
                    for entity_name, sanitized_path in [
                        self._sanitize_item_path(item)
                        for item in self.diff["dictionary_item_added"]
                    ]
                    if sanitized_path != ""
                ]
                for entity_name, sanitized_path in items:
                    self._log.info(
                        f"Additional '{self.subject.__name__}' property '{sanitized_path}' for '{entity_name}'."
                    )
                    if sanitized_path not in self._sync_actions:
                        self._log.debug(
                            f"Ignoring '{self.subject.__name__}' property '{sanitized_path}' update for '{entity_name}'."
                        )
                        continue
                    if (
                        self.interactive
                        and inquirer.confirm(
                            message=f"Do you want to remove '{self.subject.__name__}' property '{sanitized_path}' for '{entity_name}'.",
                            default=True,
                        ).execute()
                        is not True
                    ):
                        continue
                    if self.simulate:
                        self._log.info(
                            f"Simulated '{self.subject.__name__}' update of property '{sanitized_path}' for '{entity_name}'."
                        )
                        continue
                    if sanitized_path in self._sync_actions and not self.simulate:
                        self._log.info(
                            f"Synchronizing '{self.subject.__name__}' entity '{entity_name}' property '{sanitized_path}'."
                        )
                        try:
                            self._sync_actions[sanitized_path](entity_name, sanitized_path)
                        except KeyError:
                            self._log.info(
                                f"No '{self.subject.__name__}' defined to update '{sanitized_path}' property for '{entity_name}'."
                            )
            if "values_changed" in self.diff:
                for item_path, value in self.diff["values_changed"].items():
                    entity_name, sanitized_path = self._sanitize_item_path(str(item_path))
                    self._log.info(f"Detected diff for '{entity_name}' from '{sanitized_path}'")
                    if sanitized_path not in self._sync_actions:
                        self._log.debug(
                            f"Ignoring '{self.subject.__name__}' property '{sanitized_path}' from '{value['old_value']}' to '{value['new_value']}'."
                        )
                        continue
                    if (
                        self.interactive
                        and inquirer.confirm(
                            message=f"Do you want to update '{self.subject.__name__}' property '{sanitized_path}' from '{value['old_value']}' to '{value['new_value']}'?",
                            default=True,
                        ).execute()
                        is not True
                    ):
                        continue
                    if self.simulate:
                        self._log.info(
                            f"Simulated '{self.subject.__name__}' update of property '{sanitized_path}' from '{value['old_value']}' to '{value['new_value']}'."
                        )
                        continue
                    if sanitized_path in self._sync_actions and not self.simulate:
                        self._log.info(
                            f"Synchronizing '{self.subject.__name__}' property '{sanitized_path}' from '{value['old_value']}' to '{value['new_value']}'."
                        )
                        try:
                            self._sync_actions[sanitized_path](
                                self._src, self._dest, entity_name, value["new_value"]
                            )
                        except KeyError:
                            self._log.info(
                                f"No action defined to update update '{self.subject.__name__}' property '{sanitized_path}' from '{value['old_value']}' to '{value['new_value']}'."
                            )

        @staticmethod
        def _sanitize_item_path(item) -> Tuple[str, str]:
            """Remove 'root' and unnecessary brackets aka convert to dot notation.

            Returns entity name and sanitized path as tuple.
            """
            remove_digits = str.maketrans("", "", digits)
            split_path = (
                item.replace("root", "")
                .replace(".", "")
                .translate(remove_digits)
                .replace("']['", ".")
                .replace("['", "")
                .replace("[", "")
                .replace("]", "")
                .replace("]'", "")
                .replace("'", "")
                .split(".")
            )
            return split_path[0], ".".join(split_path[1:])
