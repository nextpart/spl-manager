# pylint: disable=R0903
"""Manager for syncing differences of two instances."""
import logging
from typing import Tuple


class DiffConverter:
    """Logic to execute sync of diff from src to dest."""

    def __init__(self, diff_gen, sync_actions, src, dest):
        self._diff_gen = diff_gen
        self._src = src
        self._dest = dest
        logging.info(
            f"Differential synchronization for '{src._name}' to '{dest._name}'"
            + f" of '{diff_gen.__name__.split('_diff')[0]}'."
        )
        self._sync_actions = sync_actions

    def _sync_missing(self, diff):
        """Sync completely missing entities (i.e. User, Index, ...)."""
        if "dictionary_item_removed" in diff:
            for item in diff["dictionary_item_removed"]:
                self._sync_actions["root"](self._src, self._dest, str(item).split("'")[1])

    @staticmethod
    def _sanitize_item_path(item) -> Tuple[str, str]:
        """Remove 'root' and unnecessary brackets aka convert to dot notation.

        Returns entity name and sanitized path as tuple.
        """
        split_path = (
            item.replace("root", "")
            .replace("][", ".")
            .replace("[", "")
            .replace("]", "")
            .replace("'", "")
            .split(".")
        )
        return split_path[0], ".".join(split_path[1:])

    def _sync_content(self, diff):
        """Synchronize all changes between src entity and dest entity."""
        if "values_changed" in diff:
            for item_path, value in diff["values_changed"].items():
                entity_name, sanitized_path = DiffConverter._sanitize_item_path(str(item_path))
                logging.info(
                    f"Synchronizing entity '{entity_name}' with property '{sanitized_path}' to"
                    + f" new value '{value['new_value']}'"
                )
                try:
                    self._sync_actions[sanitized_path](
                        self._src, self._dest, entity_name, value["new_value"]
                    )
                except KeyError:
                    logging.info(
                        f"No action defined to update '{sanitized_path}' property for "
                        + f"'{entity_name}' with new value '{value['new_value']}'"
                    )

        if "iterable_item_removed" in diff:
            for item_path, value in diff["iterable_item_removed"].items():
                entity_name, sanitized_path = DiffConverter._sanitize_item_path(str(item_path))
                sanitized_path = ".".join(sanitized_path.split(".")[:-1])
                logging.info(f"'{entity_name}': '{sanitized_path}' -> '{value}'")
                try:
                    self._sync_actions[sanitized_path](self._src, self._dest, entity_name, value)
                except KeyError:
                    logging.info(f"No action defined for '{sanitized_path}', thus skipping.")

        # TODO add necessary logic for deletion of items on dest

    def sync_diff(self):
        """Sync the differences between source and destination instance."""
        diff = self._diff_gen(self._src, self._dest)
        logging.info("Determine whole missing entities and transfering them.")
        self._sync_missing(diff)
        # if creation is properly implemented,
        # new diff will contain everything necessary to create for new user
        logging.info("Determine differences in existing entities and update content.")
        diff = self._diff_gen(self._src, self._dest)
        self._sync_content(diff)
