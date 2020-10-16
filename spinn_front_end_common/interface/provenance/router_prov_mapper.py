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


def router_prov_details(db_filename, info):
    data = []
    xs = []
    ys = []
    src = None
    name = None
    with sqlite3.connect(db_filename) as db:
        db.row_factory = sqlite3.Row
        for row in db.execute("""
                SELECT source_name AS "source", x, y, p,
                    description_name AS "description", MAX(the_value) AS "value"
                FROM provenance_view
                WHERE description LIKE ?
                GROUP BY x, y, p
                """, ("%" + info + "%", )):
            # Why is the provenance data duplicated sometimes?
            # At least we know these counts monotonically increase
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
    return ((src + "/" + name).replace("_", " "), max(xs) + 1, max(ys) + 1, ary)


def router_plot_data(db_filename, key, output_filename):
    # Check the existence of the database here
    # if the DB isn't there, the errors are otherwise *weird* if we don't check
    if not os.path.exists(db_filename):
        raise Exception("no such DB: " + db_filename)
    # Import here because otherwise CI fails
    import matplotlib.pyplot as plot
    import seaborn
    print("creating " + output_filename)
    (title, width, height, data) = router_prov_details(db_filename, key)
    _fig, ax = plot.subplots(figsize=(width, height))
    plot.title(title)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.axis("off")
    labels=data.astype(int)
    seaborn.heatmap(
        data, annot=labels, fmt="",
        cmap="plasma", square=True).invert_yaxis()
    plot.savefig(output_filename, bbox_inches='tight')
    plot.close()


def main():
    if len(sys.argv) != 2:
        raise Exception(
            "wrong number of arguments: needs just the prov DB filename")
    for term in PLOTTABLES:
        router_plot_data(sys.argv[1], term, term + ".png")


if __name__ == "__main__":
    main()
