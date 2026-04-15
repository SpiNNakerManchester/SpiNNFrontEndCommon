# Copyright (c) 2020 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import sqlite3
from types import ModuleType, TracebackType
from typing import (
    Any, ContextManager, FrozenSet, Iterable, List, Optional, Tuple, Type,
    cast)

import numpy
from typing_extensions import Literal

from spinn_front_end_common.utilities.sqlite_db import SQLiteDB
from spinn_front_end_common.utilities.exceptions import ConfigurationException

# The types of router provenance that we'll plot
ROUTER_PLOTTABLES = (
    "Default_Routed_External_Multicast_Packets",
    "Dropped_FR_Packets",
    "Dropped_Multicast_Packets",
    "Dropped_Multicast_Packets_via_Local_Transmission",
    "Dropped_NN_Packets",
    "Dropped_P2P_Packets",
    "Dumped_from_a_Link",
    "Dumped_from_a_Processor",
    "Error",
    "External_FR_Packets",
    "External_Multicast_Packets",
    "External_NN_Packets",
    "External_P2P_Packets",
    "Local_Multicast_Packets",
    "Local_P2P_Packets",
    "Local_NN_Packets",
    "Local_FR_Packets",
    "Missed_for_Reinjection",
    "Received_for_Reinjection",
    "Reinjected",
    "Reinjection_Overflows")
SINGLE_PLOTNAME = "Plot.png"


class Plotter(ContextManager[SQLiteDB]):
    """
    Code to plot provenance data from the database
    """
    __slots__ = ("cmap", "_db", "__have_insertion_order", "__verbose")

    __pyplot: Optional[ModuleType] = None
    __seaborn: Optional[ModuleType] = None

    def __init__(self, db_filename: str, verbose: bool = False):
        """
        :param db_filename:
            The name of a file that contains (or will contain) an SQLite
            database holding the data.
        :param verbose: Flag to trigger print messages
        """
        self._db = SQLiteDB(db_filename, read_only=True, text_factory=str)
        self.__have_insertion_order = True
        self.__verbose = verbose
        self.cmap = "plasma"

    def __enter__(self) -> SQLiteDB:
        return self._db.__enter__()

    def __exit__(self, exc_type: Optional[Type],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> Literal[False]:
        return self._db.__exit__(exc_type, exc_val, exc_tb)

    def __do_chip_query(self, description: str) -> Iterable[sqlite3.Row]:
        # Does the query in one of two ways, depending on schema version
        if self.__have_insertion_order:
            try:
                return self._db.cursor().execute("""
                    SELECT source_name AS "source", x, y,
                        description_name AS "description",
                        the_value AS "value"
                    FROM provenance_view
                    WHERE description LIKE ?
                    GROUP BY x, y, p
                    HAVING insertion_order = MAX(insertion_order)
                    """, (description, ))
            except sqlite3.OperationalError as e:
                if "no such column: insertion_order" != str(e):
                    raise
                self.__have_insertion_order = False
        return self._db.cursor().execute("""
            SELECT source_name AS "source", x, y,
                description_name AS "description",
                MAX(the_value) AS "value"
            FROM provenance_view
            WHERE description LIKE ?
            GROUP BY x, y, p
            """, (description, ))

    def get_per_chip_prov_types(self) -> FrozenSet[str]:
        """
        :returns: A set of the descriptions available at chip level
        """
        query = """
            SELECT DISTINCT description_name AS "description"
            FROM provenance_view
            WHERE x IS NOT NULL AND p IS NULL AND "description" IS NOT NULL
            """
        return frozenset(row["description"]
                         for row in self._db.cursor().execute(query))

    def get_per_chip_prov_details(self, info: str) -> Tuple[
            str, int, int, numpy.ndarray]:
        """
        Gets the provenance of a per chip basis

        :param info:
            The name of the metadata to sum
        :return: name, max x, max y and data
        """
        data = []
        xs = []
        ys = []
        src: Optional[str] = None
        name: Optional[str] = None
        for row in self.__do_chip_query("%" + info + "%"):
            if src is None:
                src = row["source"]
            if name is None:
                name = row["description"]
            data.append((row["x"], row["y"], row["value"]))
            xs.append(row["x"])
            ys.append(row["y"])
        ary = numpy.full((max(ys) + 1, max(xs) + 1), float("NaN"))
        for (x, y, value) in data:
            ary[y, x] = value
        assert src is not None and name is not None, "no such chip"
        return (f"{src}/{name}".replace("_", " "),
                max(xs) + 1, max(ys) + 1, ary)

    def __do_sum_query(self, description: str) -> Iterable[sqlite3.Row]:
        # Does the query in one of two ways, depending on schema version
        if self.__have_insertion_order:
            try:
                return self._db.cursor().execute("""
                    SELECT "source", x, y, "description",
                        SUM("value") AS "value"
                    FROM (
                        SELECT source_name AS "source", x, y, p,
                            description_name AS "description",
                            the_value AS "value"
                        FROM provenance_view
                        WHERE description LIKE ? AND p IS NOT NULL
                        GROUP BY x, y, p
                        HAVING insertion_order = MAX(insertion_order))
                    GROUP BY x, y
                    """, (description, ))
            except sqlite3.OperationalError as e:
                if "no such column: insertion_order" != str(e):
                    raise
                self.__have_insertion_order = False
        return self._db.cursor().execute("""
            SELECT "source", x, y, "description",
                SUM("value") AS "value"
            FROM (
                SELECT source_name AS "source", x, y,
                    description_name AS "description",
                    MAX(the_value) AS "value"
                FROM provenance_view
                WHERE description LIKE ? AND p IS NOT NULL
                GROUP BY x, y, p)
            GROUP BY x, y
            """, (description, ))

    def get_per_core_prov_types(self) -> FrozenSet[str]:
        """
        :returns: A set of the descriptions available at core level
        """
        query = """
            SELECT DISTINCT description_name AS "description"
            FROM provenance_view
            WHERE x IS NOT NULL AND p IS NOT NULL
                AND "description" IS NOT NULL
            """
        return frozenset(
            cast(str, row["description"])
            for row in self._db.cursor().execute(query))

    def get_sum_chip_prov_details(self, info: str) -> Tuple[
            str, int, int, numpy.ndarray]:
        """
        Gets the sum of the provenance

        :param info:
            The name of the metadata to sum
        :return: name, max x, max y and data
        """
        data: List[Tuple[int, int, Any]] = []
        xs: List[int] = []
        ys: List[int] = []
        name: Optional[str] = None
        for row in self.__do_sum_query("%" + info + "%"):
            if name is None:
                name = row["description"]
            data.append((row["x"], row["y"], row["value"]))
            xs.append(row["x"])
            ys.append(row["y"])
        assert name is not None, "no chips match query"
        ary = numpy.full((max(ys) + 1, max(xs) + 1), float("NaN"))
        for (x, y, value) in data:
            ary[y, x] = value
        return name.replace("_", " "), max(xs) + 1, max(ys) + 1, ary

    @classmethod
    def __plotter_apis(cls) -> Tuple[ModuleType, ModuleType]:
        # Import here because otherwise CI fails
        # pylint: disable=import-error,import-outside-toplevel
        if not cls.__pyplot:
            import matplotlib.pyplot as plot  # type: ignore[import]
            cls.__pyplot = plot
        if not cls.__seaborn:
            import seaborn  # type: ignore[import]
            cls.__seaborn = seaborn
        if cls.__pyplot is None or cls.__seaborn is None:
            raise ConfigurationException(
                "no plotting APIs present; please install "
                "matplotlib and seaborn to plot router provenance")
        return cls.__pyplot, cls.__seaborn

    def plot_per_core_data(self, key: str, output_filename: str) -> None:
        """
        Plots the metadata for this key/term to the file at a core level

        :param key:
            The name of the metadata to plot, or a unique fragment of it
        :param output_filename:
        """
        plot, seaborn = self.__plotter_apis()
        if self.__verbose:
            print("creating " + output_filename)
        (title, width, height, data) = self.get_sum_chip_prov_details(key)
        _fig, ax = plot.subplots(figsize=(width, height))
        plot.title(title)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axis("off")
        labels = data.astype(numpy.uint32)
        seaborn.heatmap(
            data, annot=labels, fmt="", square=True,
            cmap=self.cmap).invert_yaxis()
        plot.savefig(output_filename, bbox_inches='tight')
        plot.close()

    def plot_per_chip_data(self, key: str, output_filename: str) -> None:
        """
        Plots the metadata for this key/term to the file at a chip level

        :param key:
            The name of the metadata to plot, or a unique fragment of it
        :param output_filename:
        """
        plot, seaborn = self.__plotter_apis()
        if self.__verbose:
            print("creating " + output_filename)
        (title, width, height, data) = self.get_per_chip_prov_details(key)
        _fig, ax = plot.subplots(figsize=(width, height))
        plot.title(title)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axis("off")
        labels = data.astype(numpy.uint32)
        seaborn.heatmap(
            data, annot=labels, fmt="", square=True,
            cmap=self.cmap).invert_yaxis()
        plot.savefig(output_filename, bbox_inches='tight')
        plot.close()


def main() -> None:
    """
    Generate heat maps from SpiNNaker provenance databases
    """
    ap = argparse.ArgumentParser(
        description="Generate heat maps from SpiNNaker provenance databases.")
    ap.add_argument("-c", "--colourmap", nargs="?", default="plasma",
                    help="colour map rule for plot; default 'plasma'")
    ap.add_argument("-l", "--list", action="store_true", default=False,
                    help="list the types of metadata available")
    ap.add_argument("-q", "--quiet", action="store_true", default=False,
                    help="don't print progress information")
    ap.add_argument("-s", "--sumcores", action="store_true", default=False,
                    help="compute information by summing data from the cores "
                    "of each chip; needs a metadata_name as well unless the "
                    "--list option is also given")
    ap.add_argument("dbfile", metavar="database_file",
                    help="the provenance database to extract data from; "
                    "usually called 'provenance.sqlite3'")
    ap.add_argument("term", metavar="metadata_name", nargs="?", default=None,
                    help="the name of the metadata to plot, or a unique "
                    "fragment of it; if omitted, maps will be produced for "
                    "all the router provenance categories")
    args = ap.parse_args()

    plotter = Plotter(args.dbfile, not args.quiet)
    plotter.cmap = args.colourmap
    with plotter:
        if args.list:
            if args.sumcores:
                for term in plotter.get_per_core_prov_types():
                    print(term)
            else:
                for term in plotter.get_per_chip_prov_types():
                    print(term)
        elif args.term:
            if args.sumcores:
                plotter.plot_per_core_data(
                    args.term, os.path.abspath(SINGLE_PLOTNAME))
            else:
                plotter.plot_per_chip_data(
                    args.term, os.path.abspath(SINGLE_PLOTNAME))
        else:
            if args.sumcores:
                raise ValueError(
                    "cannot use --sumcores with default router provenance")
            for term in ROUTER_PLOTTABLES:
                plotter.plot_per_chip_data(
                    term, os.path.abspath(term + ".png"))


if __name__ == "__main__":
    main()
