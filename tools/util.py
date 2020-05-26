import re


def hex_dump():
    pass


def parse_apps(apps):
    if re.match(r"^\d+$", apps):
        apps = int(apps)
        if apps < 256:
            return apps, 255
        return None, None
    m = re.match(r"^(\d+)-(\d+)$", apps)
    if not m:
        return None, None
    app_id = int(m.group(1))
    max_id = int(m.group(2))
    id_range = max_id - app_id + 1
    if id_range < 1 or app_id % id_range != 0 or app_id + id_range > 256:
        return None, None
    app_mask = 255 & ~(id_range - 1)
    return app_id, app_mask


def parse_bits():
    pass


def parse_cores():
    pass


def parse_region():
    pass


def read_file():
    pass


def sllt_version():
    pass
