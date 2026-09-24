#!/usr/bin/env python3
"""Verify that upgraded macros have persistent Fluidd category metadata."""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


CARTOGRAPHER_MACROS = (
    "A11_CARTO_SELECT_DEFAULT",
    "A12_CARTO_SELECT_TEXTURED_PEI",
    "A13_CARTO_SELECT_EPOXY",
    "A14_CARTO_SELECT_HIGH_TEMP",
    "A15_CARTO_SELECT_CUSTOM",
    "A21_CARTO_SCAN_SELECTED",
    "A22_CARTO_TOUCH_SELECTED",
    "A23_CARTO_LOAD_SELECTED",
    "A61_CARTO_TOUCH_HOME",
    "A62_CARTO_LIST_MODELS",
    "A63_CARTO_INFO",
)
PLATE_SELECTORS = {
    "A12_CARTO_SELECT_TEXTURED_PEI",
    "A13_CARTO_SELECT_EPOXY",
    "A14_CARTO_SELECT_HIGH_TEMP",
    "A15_CARTO_SELECT_CUSTOM",
}
COMPONENT_MACROS = {
    "cartographer": CARTOGRAPHER_MACROS,
    "cartographer-plate-workflow": CARTOGRAPHER_MACROS,
    "macros": ("BED_ASSIST",),
    "global-touch-offsets": ("GLOBAL_Z_OFFSETS_CARTO",),
    "material-z-offsets": ("MATERIAL_Z_OFFSETS",),
}


class VerificationError(RuntimeError):
    pass


def verify_layout(namespace, component):
    expected = COMPONENT_MACROS.get(component)
    if expected is None:
        raise VerificationError("unsupported component: {}".format(component))
    if not isinstance(namespace, dict):
        raise VerificationError("Fluidd database namespace is not an object")
    macros = namespace.get("macros", {})
    if not isinstance(macros, dict):
        raise VerificationError("Fluidd macros database item is not an object")
    categories = macros.get("categories", [])
    stored = macros.get("stored", [])
    if not isinstance(categories, list) or not isinstance(stored, list):
        raise VerificationError("Fluidd macro metadata is invalid")
    if any(not isinstance(item, dict) for item in categories + stored):
        raise VerificationError("Fluidd macro metadata contains an invalid entry")

    category_names = {
        str(item.get("id")): str(item.get("name", ""))
        for item in categories
        if item.get("id")
    }
    stored_by_name = {
        str(item.get("name", "")).casefold(): item
        for item in stored
        if item.get("name")
    }
    errors = []
    for name in expected:
        item = stored_by_name.get(name.casefold())
        if item is None:
            errors.append("{} has no stored Fluidd metadata".format(name))
            continue
        category_id = str(item.get("categoryId", ""))
        category_name = category_names.get(category_id, "")
        if not category_id or category_id == "0" or not category_name:
            errors.append("{} has no valid Fluidd category".format(name))
        elif category_name.casefold() == "uncategorized":
            errors.append("{} remains in Uncategorized".format(name))
        if (
            component == "cartographer-plate-workflow"
            and name in PLATE_SELECTORS
            and not item.get("visible", False)
        ):
            errors.append("{} is still hidden".format(name))
    if errors:
        raise VerificationError("; ".join(errors))


def _result_value(payload):
    if not isinstance(payload, dict):
        raise VerificationError("Moonraker returned a non-object response")
    if "error" in payload:
        raise VerificationError(
            "Moonraker database request failed: {}".format(payload["error"])
        )
    response = payload.get("result", payload)
    if not isinstance(response, dict) or "value" not in response:
        raise VerificationError("Moonraker database response has no value")
    return response["value"]


def fetch_namespace(api_url):
    query = urllib.parse.urlencode({"namespace": "fluidd"})
    request = urllib.request.Request(
        "{}/server/database/item?{}".format(api_url.rstrip("/"), query),
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return _result_value(json.loads(response.read().decode("utf-8")))
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        raise VerificationError(str(exc))


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in COMPONENT_MACROS:
        print(
            "E: usage: verify_fluidd_layout.py {}".format(
                "|".join(sorted(COMPONENT_MACROS))
            )
        )
        return 2
    component = sys.argv[1]
    try:
        verify_layout(
            fetch_namespace(os.environ.get("MOONRAKER_URL", "http://127.0.0.1:7125")),
            component,
        )
    except VerificationError as exc:
        print("E: Fluidd layout verification failed for {}: {}".format(component, exc))
        return 1
    print("I: verified persistent Fluidd macro grouping for {}".format(component))
    return 0


if __name__ == "__main__":
    sys.exit(main())
