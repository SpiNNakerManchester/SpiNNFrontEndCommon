# Copyright (c) 2020 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import os
import sqlite3
import numpy
# import matplotlib.pyplot as plot
# import seaborn

# The types of router provenance that we'll plot
PLOTTABLES = (
    "default_routed_external_multicast_packets",
    "Dropped_FR_Packets",
    "Dropped_Multicast_Packets",
    "Dropped_Multicast_Packets_via_local_transmission",
    "Dropped_NN_Packets",
    "Dropped_P2P_Packets",
    "Dumped_from_a_Link",
    "Dumped_from_a_processor",
    "Error",
    "External_FR_Packets",
    "External_Multicast_Packets",
    "External_NN_Packets",
    "External_P2P_Packets",
    "Local_Multicast_Packets",
    "Local_P2P_Packets",
    "Local_NN_Packets",
    "Local_FR_Packets",
    "Missed_For_Reinjection",
    "Received_For_Reinjection",
    "Reinjected",
    "Reinjection_Overflows")


class Plotter(object):
    __slots__ = ("_db", "__have_insertion_order", "__verbose")

    def __init__(self, db_filename, verbose=False):
        # Check the existence of the database here
        # if the DB isn't there, the errors are otherwise *weird* if we don't check
        if not os.path.exists(db_filename):
            raise Exception("no such DB: " + db_filename)
        # TODO: use magic to open a read-only connection once we're Py3 only
        # See: https://stackoverflow.com/a/21794758/301832
        self._db = sqlite3.connect(db_filename)
        self._db.row_factory = sqlite3.Row
        self.__have_insertion_order = True
        self.__verbose = verbose

    def __enter__(self):
        return self._db.__enter__()

    def __exit__(self, *args):
        return self._db.__exit__(*args)

    def _do_query(self, description):
        # Does the query in one of two ways, depending on schema version
        if self.__have_insertion_order:
            try:
                return self._db.execute("""
                    SELECT source_name AS "source", x, y, p,
                        description_name AS "description",
                        the_value AS "value"
                    FROM provenance_view
                    WHERE description LIKE ?
                    GROUP BY x, y, p
                    HAVING insertion_order = MAX(insertion_order)
                    """, (description, ))
            except sqlite3.Error:
                self.__have_insertion_order = 0
        return self._db.execute("""
            SELECT source_name AS "source", x, y, p,
                description_name AS "description",
                MAX(the_value) AS "value"
            FROM provenance_view
            WHERE description LIKE ?
            GROUP BY x, y, p
            """, (description, ))

    def get_router_prov_details(self, info):
        data = []
        xs = []
        ys = []
        src = None
        name = None
        for row in self._do_query("%" + info + "%"):
            if src is None:
                src = row["source"]
            if name is None:
                name = row["description"]
            data.append((row["x"], row["y"], row["p"], row["value"]))
            xs.append(row["x"])
            ys.append(row["y"])
        ary = numpy.full((max(ys) + 1, max(xs) + 1), float("NaN"))
        for (x, y, _p, value) in data:
            ary[y, x] = value
        return ((src + "/" + name).replace("_", " "),
                max(xs) + 1, max(ys) + 1, ary)

    def router_plot_data(self, key, output_filename):
        # Import here because otherwise CI fails
        # pylint: disable=import-error
        import matplotlib.pyplot as plot
        import seaborn
        if self.__verbose:
            print("creating " + output_filename)
        (title, width, height, data) = self.get_router_prov_details(key)
        _fig, ax = plot.subplots(figsize=(width, height))
        plot.title(title)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axis("off")
        labels = data.astype(int)
        seaborn.heatmap(
            data, annot=labels, fmt="",
            cmap="plasma", square=True).invert_yaxis()
        plot.savefig(output_filename, bbox_inches='tight')
        plot.close()


def main():
    ap = argparse.ArgumentParser(
        description="Generate heat maps from SpiNNaker provenance databases.")
    ap.add_argument("-q", "--quiet", action="store_true", default=False,
                    help="don't print progress information")
    ap.add_argument("dbfile", metavar="database_file",
                    help="the provenance database to extract data from; "
                    "usually called 'provenance.sqlite3'")
    ap.add_argument("term", metavar="metadata_name", nargs="?", default=None,
                    help="the name of the metadata to plot, or a unique "
                    "fragment of it")
    args = ap.parse_args()
    plotter = Plotter(args.dbfile, not args.quiet)
    with plotter:
        if args.term:
            plotter.router_plot_data(args.term, os.path.abspath("Plot.png"))
        else:
            for term in PLOTTABLES:
                plotter.router_plot_data(term, os.path.abspath(term + ".png"))


if __name__ == "__main__":
    main()
