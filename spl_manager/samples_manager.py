"""Splunk Samples Manager."""

import _thread
import csv
from pathlib import Path
from time import sleep
from typing import Optional, Union

import splunklib.results as spl_results
from InquirerPy import inquirer
from rich import print  # pytlint: disable=W0622

from spl_manager.connection_adapter import ConnectionAdapter


class SamplesManager:
    """Manage event samples from you Splunk instance.

    The SampleManager allows you to download event samples from an specified Splunk instance.
    """

    def __init__(self, parent: object, path: Union[Path, str] = Path.cwd()):
        self._interactive = parent._interactive
        self._settings = parent._settings
        self._log = parent._log
        self._parent = parent
        self.src = parent._src
        self._work_dir = path

    def __str__(self):
        print(list(self._settings.SAMPLES.to_dict().keys()))
        return ""

    def _query_to_file(self, sample, sample_props, connection, path):
        """Create search job, wait for results and store them to file.

        Args:
            sample (str): Name of the sample data set.
            sample_props (dict): Sample properties from settings.
            connection (src): Connection to use to get samples if not set in src.
            path (Path): Place to store resulting sample data set as file.
        """
        self._log.info(f"About to download sample '{sample}':")
        self._log.debug(sample_props)
        search_args = {
            "earliest_time": sample_props["earliest"],
            "latest_time": sample_props["latest"],
            "search_mode": "normal",
        }

        job = connection.client.jobs.create("search " + sample_props["query"], **search_args)
        self._log.debug(f"Created search job on '{connection._name}'.")
        sleep(2)
        while True:
            job.refresh()
            self._log.info(
                f"Splunk data fetch status: '{float(job['doneProgress']) * 100}'"
                + " percent - '{int(job['scanCount'])}' scanned - '{int(job['eventCount'])}'"
                + " matched - '{int(job['resultCount'])}' results"
            )
            if job["isDone"] == "1":
                break
            sleep(2)
        kwargs_options = {"count": 0}
        self._log.info("Finished job. Reading results now.")
        results = list(spl_results.ResultsReader(job.results(**kwargs_options)))
        self._log.info(f"Fetched {len(results)} events")
        if len(results) <= 1:
            self._log.warning("Did not write any data to remote service as query result was empty.")
        else:
            self._log.info(f"Writing results to {path+'/'+sample}.csv")
            with open(path + f"/{sample}.csv", "w", encoding="utf-8") as outfile:
                csv_writer = csv.writer(outfile)
                csv_writer.writerow(results[0].keys())
                csv_writer.writerows([result.values() for result in results])

    def download(self, name: Optional[str] = None, connection: str = None):
        """Download sample data endpoint triggering query & store threads.

        Args:
            name (Optional[str], optional): Name of sample set(s) to download. Defaults to None.
            connection (str, optional): Connection to use for query. Defaults to None.

        Raises:
            ValueError: Invalid parameter definition
        """
        samples = []
        connections = []
        if connection is None and not hasattr(self._parent, "_src"):
            connections = []
        elif connection is not None and connection in self._settings.CONNECTIONS:
            connections = [ConnectionAdapter(parent=self._parent, name=connection)]
            self._log.info(f"Using '{connections[0]._name}' as connection")
        elif connection is None and hasattr(self._parent, "_src"):
            self._log.info(f"Using '{self._parent._src._name}' as connection")
            connections = [self._parent._src]
        self._log.info(f"Connections: {[connection._name for connection in connections]}")
        if not self._interactive and name is None:
            raise ValueError
        if name is not None:
            if name in self._settings.SAMPLES and self._settings.SAMPLES[name]["src"] in [
                connection._name for connection in connections
            ]:
                samples = list(self._settings.SAMPLES.keys())
            else:
                self._log.info(name)
                raise ValueError("FATAAAAAL!!!")
        else:
            samples = [
                key
                for key, val in self._settings.SAMPLES.to_dict().items()
                if val["src"] in [connection._name for connection in connections]
            ]
            if samples == []:
                self._log.warning("No samples found.")
                return
            samples = inquirer.checkbox(
                message="Select the samples you want to download:",
                choices=samples,
            ).execute()
        if samples == []:
            self._log.warning("No samples to get.")
            return
        self._log.info("Sample selection: '" + "', '".join(samples) + "'.")
        if not self._interactive:
            # Find a proper samples path
            if (Path().cwd() / "apps/SA-Eventgen/samples").exists():
                path = Path().cwd() / "apps/SA-Eventgen/samples"
            elif (Path().cwd() / "samples").exists():
                path = Path().cwd() / "samples"
            else:
                path = Path().cwd()
        else:
            path_candidates = [self._work_dir, self._work_dir / "samples"]
            path_candidates = path_candidates + list(
                Path(self._work_dir).glob("**/SA-Eventgen/samples")
            )
            path_candidates = path_candidates + [
                path
                for path in Path(self._work_dir).glob("**/samples")
                if "SA-Eventgen" not in str(path)
            ]
            path = inquirer.select(
                message="Select a targetdirectory:",
                choices=[
                    str(self._work_dir / path.relative_to(self._work_dir))
                    for path in path_candidates
                ],
                default=str(path_candidates[0]),
            ).execute()
        self._log.info(f"Selected directory to store samples is '{path}'")
        # Download Data:
        for index in range(len(samples)):
            sample_props = self._settings.SAMPLES[samples[index]].to_dict()
            connection = [
                connection for connection in connections if connection._name == sample_props["src"]
            ][0]
            try:
                _thread.start_new_thread(
                    self._query_to_file(samples[index], sample_props, connection, path),
                    (
                        f"Query-{index}",
                        index,
                    ),
                )
            except Exception:
                self._log.error("Unable to start thread.")
                return
