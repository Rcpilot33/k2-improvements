#!/usr/bin/env python3
"""Seed the Fluidd layout for the Cartographer calibration macros."""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


CATEGORY_NAME = "Cartographer Calibration"
CATEGORY_ID = str(
    uuid.uuid5(
        uuid.NAMESPACE_URL,
        "https://github.com/Rcpilot33/k2-improvements/fluidd/cartographer-calibration",
    )
)

MACRO_LAYOUT = (
    ("A11_CARTO_SELECT_DEFAULT", "DEFAULT", "#1AED07"),
    ("A12_CARTO_SELECT_TEXTURED_PEI", "TEXTURED_PEI", "#1AED07"),
    ("A13_CARTO_SELECT_EPOXY", "EPOXY", "#1AED07"),
    ("A14_CARTO_SELECT_HIGH_TEMP", "HIGH_TEMP", "#1AED07"),
    ("A15_CARTO_SELECT_CUSTOM", "CUSTOM", "#1AED07"),
    ("A21_CARTO_SCAN_SELECTED", "CARTO_SCAN_CALIBRATE", "#FF9800"),
    ("A22_CARTO_TOUCH_SELECTED", "CARTO_TOUCH_CALIBRATE", "#FF9800"),
    ("A23_CARTO_LOAD_SELECTED", "CARTO_LOAD", "#2196F3"),
    ("A61_CARTO_TOUCH_HOME", "CARTO_TOUCH_HOME", "#2196F3"),
    ("A62_CARTO_LIST_MODELS", "CARTO_LIST_MODELS", "#2196F3"),
    ("A63_CARTO_INFO", "CARTO_INFO", "#2196F3"),
)

PLATE_SELECTOR_NAMES = {
    "A12_CARTO_SELECT_TEXTURED_PEI",
    "A13_CARTO_SELECT_EPOXY",
    "A14_CARTO_SELECT_HIGH_TEMP",
    "A15_CARTO_SELECT_CUSTOM",
}


class LayoutError(RuntimeError):
    pass


def merge_layout(namespace, show_plate_selectors=False):
    """Return Fluidd namespace data with Cartographer layout defaults added.

    A core installation hides the four named plate selectors. The optional
    plate workflow asks to reveal them explicitly.
    """
    if not isinstance(namespace, dict):
        raise LayoutError("Fluidd database namespace is not an object")

    result = dict(namespace)
    macros = result.get("macros", {})
    if not isinstance(macros, dict):
        raise LayoutError("Fluidd macros database item is not an object")
    macros = dict(macros)

    categories = macros.get("categories", [])
    stored = macros.get("stored", [])
    if not isinstance(categories, list):
        raise LayoutError("Fluidd macro categories are not a list")
    if not isinstance(stored, list):
        raise LayoutError("Fluidd stored macros are not a list")
    if any(not isinstance(item, dict) for item in categories):
        raise LayoutError("Fluidd macro categories contain an invalid entry")
    if any(not isinstance(item, dict) for item in stored):
        raise LayoutError("Fluidd stored macros contain an invalid entry")

    categories = [dict(item) for item in categories]
    stored = [dict(item) for item in stored]

    category = next(
        (
            item
            for item in categories
            if str(item.get("name", "")).casefold() == CATEGORY_NAME.casefold()
            and item.get("id")
        ),
        None,
    )
    if category is None:
        category_id = CATEGORY_ID
        used_ids = {str(item.get("id")) for item in categories}
        if category_id in used_ids:
            category_id = str(uuid.uuid4())
        categories.append({"id": category_id, "name": CATEGORY_NAME})
    else:
        category_id = str(category["id"])

    valid_category_ids = {str(item.get("id")) for item in categories if item.get("id")}
    by_name = {
        str(item.get("name", "")).casefold(): index
        for index, item in enumerate(stored)
        if item.get("name")
    }

    for name, alias, color in MACRO_LAYOUT:
        is_plate_selector = name in PLATE_SELECTOR_NAMES
        index = by_name.get(name.casefold())
        if index is None:
            stored.append(
                {
                    "name": name,
                    "alias": alias,
                    "visible": show_plate_selectors or not is_plate_selector,
                    "disabledWhilePrinting": False,
                    "color": color,
                    "categoryId": category_id,
                }
            )
            by_name[name.casefold()] = len(stored) - 1
            continue

        item = stored[index]
        # Preserve aliases and valid category choices the user has intentionally
        # customized. Colors are installer-managed so all 11 buttons retain the
        # requested, consistent palette.
        if not item.get("alias"):
            item["alias"] = alias
        item["color"] = color
        if is_plate_selector:
            item["visible"] = show_plate_selectors
        current_category = str(item.get("categoryId", "0"))
        if current_category == "0" or current_category not in valid_category_ids:
            item["categoryId"] = category_id

    macros["categories"] = categories
    macros["stored"] = stored
    result["macros"] = macros
    return result


def _result_value(payload):
    if not isinstance(payload, dict):
        raise LayoutError("Moonraker returned a non-object response")
    if "error" in payload:
        raise LayoutError("Moonraker database request failed: {}".format(payload["error"]))
    response = payload.get("result", payload)
    if not isinstance(response, dict) or "value" not in response:
        raise LayoutError("Moonraker database response has no value")
    return response["value"]


def _request_json(url, method="GET", body=None, allow_missing=False):
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if allow_missing and method == "GET" and exc.code == 404:
            return None
        raise LayoutError(str(exc))
    except (urllib.error.URLError, ValueError) as exc:
        raise LayoutError(str(exc))


def configure(api_url, show_plate_selectors=False):
    api_url = api_url.rstrip("/")
    query = urllib.parse.urlencode({"namespace": "fluidd"})
    payload = _request_json(
        "{}/server/database/item?{}".format(api_url, query), allow_missing=True
    )
    # A wiped printer may not have launched Fluidd far enough to create its
    # database namespace. Moonraker creates a missing client namespace when
    # the first keyed item is posted, so seed the layout from an empty object.
    namespace = {} if payload is None else _result_value(payload)
    updated = merge_layout(namespace, show_plate_selectors=show_plate_selectors)

    if updated == namespace:
        return False

    payload = _request_json(
        "{}/server/database/item".format(api_url),
        method="POST",
        body={"namespace": "fluidd", "key": "macros", "value": updated["macros"]},
    )
    _result_value(payload)
    return True


def main():
    show_plate_selectors = False
    args = sys.argv[1:]
    if args == ["--show-plate-selectors"]:
        show_plate_selectors = True
    elif args:
        print("E: usage: configure_fluidd_layout.py [--show-plate-selectors]")
        return 2

    api_url = os.environ.get("MOONRAKER_URL", "http://127.0.0.1:7125")
    try:
        changed = configure(api_url, show_plate_selectors=show_plate_selectors)
    except LayoutError as exc:
        print("E: could not configure Fluidd Cartographer macro layout: {}".format(exc))
        return 1

    if changed:
        print(
            "I: configured 11 Fluidd macros in the '{}' category".format(CATEGORY_NAME)
        )
        if show_plate_selectors:
            print("I: named plate selectors are visible")
        else:
            print(
                "I: named plate selectors are hidden until the optional "
                "plate workflow is installed"
            )
        print("I: refresh Fluidd to load the aliases, category, and colors")
    else:
        print("I: Fluidd Cartographer macro layout is already configured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
