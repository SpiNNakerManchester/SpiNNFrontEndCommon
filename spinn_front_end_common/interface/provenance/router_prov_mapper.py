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

import os
import sqlite3
import sys
import numpy

# The types of router provenance that we'll plot
PLOTTABLES = (
    "Local_Multicast_Packets",
    "External_Multicast_Packets",
    "Dropped_Multicast_Packets",
    "Dropped_Multicast_Packets_via_local_transmission",
    "default_routed_external_multicast_packets",
    "Local_P2P_Packets",
    "External_P2P_Packets",
    "Dropped_P2P_Packets",
    "Local_NN_Packets",
    "External_NN_Packets",
    "Dropped_NN_Packets",
    "Local_FR_Packets",
    "External_FR_Packets",
    "Dropped_FR_Packets",
    "Received_For_Reinjection",
    "Missed_For_Reinjection",
    "Reinjection_Overflows",
    "Reinjected",
    "Dumped_from_a_Link",
    "Dumped_from_a_processor",
    "Error")
HAVE_INSERTION_ORDER = 1  # So we don't try schema errors several times


def _do_query(db, description):
    # Does the query in one of two ways, depending on schema version
    global HAVE_INSERTION_ORDER
    if HAVE_INSERTION_ORDER:
        try:
            return db.execute("""
                SELECT source_name AS "source", x, y, p,
                    description_name AS "description",
                    the_value AS "value"
                FROM provenance_view
                WHERE description LIKE ?
                GROUP BY x, y, p
                HAVING insertion_order = MAX(insertion_order)
                """, (description, ))
        except sqlite3.Error:
            HAVE_INSERTION_ORDER = 0
    return db.execute("""
        SELECT source_name AS "source", x, y, p,
            description_name AS "description",
            MAX(the_value) AS "value"
        FROM provenance_view
        WHERE description LIKE ?
        GROUP BY x, y, p
        """, (description, ))


def router_prov_details(db, info):
    data = []
    xs = []
    ys = []
    src = None
    name = None
    for row in _do_query(db, "%" + info + "%"):
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
    return (src + "/" + name).replace("_", " "), max(xs) + 1, max(ys) + 1, ary


def router_plot_data(db, key, output_filename):
    # Import here because otherwise CI fails
    # pylint: disable=import-error
    import matplotlib.pyplot as plot
    import seaborn
    print("creating " + output_filename)
    (title, width, height, data) = router_prov_details(db, key)
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
    if len(sys.argv) != 2:
        raise Exception(
            "wrong number of arguments: needs just the prov DB filename")
    db_filename = sys.argv[1]
    # Check the existence of the database here
    # if the DB isn't there, the errors are otherwise *weird* if we don't check
    if not os.path.exists(db_filename):
        raise Exception("no such DB: " + db_filename)
    with sqlite3.connect(db_filename) as db:
        db.row_factory = sqlite3.Row
        for term in PLOTTABLES:
            router_plot_data(db, term, term + ".png")


if __name__ == "__main__":
    main()
