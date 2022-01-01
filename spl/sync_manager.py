# -*- coding: utf-8 -*-
import logging
from string import digits
from typing import Tuple

import splunklib.client as spl_client
from deepdiff import DeepDiff
from InquirerPy import inquirer
from rich import inspect, print  # pylint: disable=W0622

from spl.connection_adapter import ConnectionAdapter
from spl.objects import Apps, Indexes, Roles, Users


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

    def roles(self, simulate: bool = False):
        print(Roles.diff(self.src, self.dest))
        handler = self.DiffHandler(
            parent=self,
            diff=Roles.diff,
            accessor=self.src.client.roles,
            subject=spl_client.Role,
            simulate=simulate,
            actions={
                "create": self.dest.roles.create,
                "*": self.dest.roles.update,
                # "content.srchIndexesDefault": self.dest.roles.update,
                # "remove": None,
            },
        ).sync()  # diff=self.user_diff)

    def users(self, simulate: bool = False):
        handler = self.DiffHandler(
            parent=self,
            diff=Users.diff,
            subject=spl_client.User,
            accessor=self.src.client.users,
            simulate=simulate,
            actions={
                "create": self.dest.users.create,
                "remove": self.dest.users.update,
                "capabilities": self.dest.users.update,
                "perm.read": self.dest.users.update,
            },
        ).sync()  # diff=self.user_diff)

    def apps(self, simulate: bool = False):
        handler = self.DiffHandler(
            parent=self,
            diff=Apps.diff,
            subject=spl_client.Application,
            accessor=self.src.client.apps,
            simulate=simulate,
            actions={
                # "create": self.dest.apps.create,
                "remove": self.dest.apps.delete,
                "capabilities": self.dest.apps.update,
                "perm.read": self.dest.apps.update,
            },
        ).sync()

    class DiffHandler:
        def __init__(
            self, parent, diff, accessor, subject: type, simulate: bool, actions: dict = {}
        ):
            self._diff_gen = diff
            self.src = parent.src
            self.dest = parent.dest
            self._sync_actions = actions
            self.subject = subject
            self.accessor = accessor
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
                    f"Missing '{self.subject.__name__}' objects {[item for item, _ in items]}."
                )
                for item, property in items:
                    if "create" not in self._sync_actions:
                        self._log.debug(
                            f"Ignoring creation of '{self.subject.__name__}' for '{item}'."
                        )
                        continue
                    if self.simulate:
                        self._log.info(
                            f"Simulated creation of '{self.subject.__name__}' for '{item}'."
                        )
                        continue
                    self._log.info(
                        f"Triggering creation of '{self.subject.__name__}' for '{item}'."
                    )
                    print(self.accessor)
                    print(item)
                    self._sync_actions["create"](self.accessor[item])

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
                    if self.simulate:
                        self._log.info(
                            f"Simulated removal of '{self.subject.__name__}' for '{item}'."
                        )
                        continue
                    self._log.info(f"Triggering removal of '{self.subject.__name__}' for '{item}'.")
                    self._sync_actions["delete"](self.dest.client, self.accessor[item])

        def _update(self):
            print(self._sync_actions)
            """Synchronize all changes between src entity and dest entity."""
            for mode in ["dictionary_item_added", "dictionary_item_removed"]:
                if mode in self.diff:
                    items = [
                        (entity_name, sanitized_path)
                        for entity_name, sanitized_path in [
                            self._sanitize_item_path(item) for item in self.diff[mode]
                        ]
                        if sanitized_path != ""
                    ]
                    for entity_name, sanitized_path in items:
                        print_path = sanitized_path.replace("content.", "")
                        self._log.debug(
                            f"Different '{self.subject.__name__}' property '{print_path}' for '{entity_name}'."
                        )
                        if (
                            sanitized_path not in self._sync_actions
                            and "*" not in self._sync_actions.keys()
                        ):
                            self._log.debug(
                                f"Ignoring '{self.subject.__name__}' update '{print_path}' for '{entity_name}'."
                            )
                            continue

                        if self.simulate:
                            self._log.info(
                                f"Simulated adding '{self.subject.__name__}' property '{print_path}' for '{entity_name}'."
                            )
                            continue
                        if sanitized_path in self._sync_actions or "*" in self._sync_actions:
                            self._log.info(
                                f"Synchronizing entity '{entity_name}' property '{print_path}' for '{entity_name}'."
                            )
                            try:
                                self._sync_actions[sanitized_path](
                                    self.accessor[entity_name], sanitized_path
                                )
                            except KeyError as key_error:
                                # print(str(key_error))
                                if not "import" in str(key_error):
                                    self._log.error(
                                        f"Failed to access '{self.subject.__name__}' property '{print_path}' for '{entity_name}'."
                                    )
                        else:
                            self._log.info(
                                f"No '{self.subject.__name__}' action defined to update '{print_path}' property for '{entity_name}'."
                            )
            for mode in ["values_changed", "type_changes"]:
                if mode in self.diff:
                    for item_path, value in self.diff[mode].items():
                        entity_name, sanitized_path = self._sanitize_item_path(str(item_path))
                        print_path = sanitized_path.replace("content.", "")
                        self._log.info(f"Detected diff for '{entity_name}' from '{print_path}'")
                        if (
                            sanitized_path not in self._sync_actions
                            and "*" not in self._sync_actions.keys()
                        ):
                            self._log.debug(
                                f"Ignoring '{self.subject.__name__}' property '{print_path}' from '{value['old_value']}' to '{value['new_value']}'."
                            )
                            continue

                        if self.simulate:
                            self._log.info(
                                f"Simulated '{self.subject.__name__}' update of property '{print_path}' from '{value['old_value']}' to '{value['new_value']}'."
                            )
                            continue
                        if sanitized_path in self._sync_actions or "*" in self._sync_actions:
                            self._log.info(
                                f"Synchronizing '{self.subject.__name__}' property '{print_path}' from '{value['old_value']}' to '{value['new_value']}'."
                            )
                            try:
                                self._sync_actions[sanitized_path](
                                    self.accessor[entity_name], sanitized_path
                                )
                            except KeyError as key_error:
                                # print(key_error)
                                self._log.info(
                                    f"No '{self.subject.__name__}' action defined to update '{print_path}' property for '{entity_name}'."
                                )

        @staticmethod
        def _sanitize_item_path(item) -> Tuple[str, str]:
            """Remove 'root' and unnecessary brackets aka convert to dot notation.

            Returns entity name and sanitized path as tuple.
            """
            split_path = (
                item.replace("root[", "")
                .replace("]['", ".")
                # .replace(".", "")
                .replace("'", "")
                # .replace("][", ".")
                .replace("]", "")
                .replace("[", "")
                .split(".")
            )
            return split_path[0], ".".join([path for path in split_path[1:] if not path.isdigit()])
