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
import numpy
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB
# import matplotlib.pyplot as plot
# import seaborn

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


class Plotter(object):
    __slots__ = ("cmap", "_db", "__have_insertion_order", "__verbose")

    __pyplot = None
    __seaborn = None

    def __init__(self, db_filename, verbose=False):
        self._db = SQLiteDB(db_filename, read_only=True, text_factory=str)
        self.__have_insertion_order = True
        self.__verbose = verbose
        self.cmap = "plasma"

    def __enter__(self):
        return self._db.__enter__()

    def __exit__(self, *args):
        return self._db.__exit__(*args)

    def __do_chip_query(self, description):
        # Does the query in one of two ways, depending on schema version
        with self._db.transaction() as cur:
            if self.__have_insertion_order:
                try:
                    return cur.execute("""
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
            return cur.execute("""
                SELECT source_name AS "source", x, y,
                    description_name AS "description",
                    MAX(the_value) AS "value"
                FROM provenance_view
                WHERE description LIKE ?
                GROUP BY x, y, p
                """, (description, ))

    def get_per_chip_prov_types(self):
        query = """
            SELECT DISTINCT description_name AS "description"
            FROM provenance_view
            WHERE x IS NOT NULL AND p IS NULL AND "description" IS NOT NULL
            """
        with self._db.transaction() as cur:
            return frozenset(row["description"] for row in cur.execute(query))

    def get_per_chip_prov_details(self, info):
        data = []
        xs = []
        ys = []
        src = None
        name = None
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
        return ((src + "/" + name).replace("_", " "),
                max(xs) + 1, max(ys) + 1, ary)

    def __do_sum_query(self, description):
        # Does the query in one of two ways, depending on schema version
        with self._db.transaction() as cur:
            if self.__have_insertion_order:
                try:
                    return cur.execute("""
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
            return cur.execute("""
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

    def get_per_core_prov_types(self):
        query = """
            SELECT DISTINCT description_name AS "description"
            FROM provenance_view
            WHERE x IS NOT NULL AND p IS NOT NULL
                AND "description" IS NOT NULL
            """
        with self._db.transaction() as cur:
            return frozenset(row["description"] for row in cur.execute(query))

    def get_sum_chip_prov_details(self, info):
        data = []
        xs = []
        ys = []
        src = None
        name = None
        for row in self.__do_sum_query("%" + info + "%"):
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
        return name.replace("_", " "), max(xs) + 1, max(ys) + 1, ary

    @classmethod
    def __plotter_apis(cls):
        # Import here because otherwise CI fails
        # pylint: disable=import-error
        if not cls.__pyplot:
            import matplotlib.pyplot as plot
            cls.__pyplot = plot
        if not cls.__seaborn:
            import seaborn
            cls.__seaborn = seaborn
        return cls.__pyplot, cls.__seaborn

    def plot_per_core_data(self, key, output_filename):
        plot, seaborn = self.__plotter_apis()
        if self.__verbose:
            print("creating " + output_filename)
        (title, width, height, data) = self.get_sum_chip_prov_details(key)
        _fig, ax = plot.subplots(figsize=(width, height))
        plot.title(title)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axis("off")
        labels = data.astype(int)
        seaborn.heatmap(
            data, annot=labels, fmt="", square=True,
            cmap=self.cmap).invert_yaxis()
        plot.savefig(output_filename, bbox_inches='tight')
        plot.close()

    def plot_per_chip_data(self, key, output_filename):
        plot, seaborn = self.__plotter_apis()
        if self.__verbose:
            print("creating " + output_filename)
        (title, width, height, data) = self.get_per_chip_prov_details(key)
        _fig, ax = plot.subplots(figsize=(width, height))
        plot.title(title)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axis("off")
        labels = data.astype(int)
        seaborn.heatmap(
            data, annot=labels, fmt="", square=True,
            cmap=self.cmap).invert_yaxis()
        plot.savefig(output_filename, bbox_inches='tight')
        plot.close()


def main():
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
