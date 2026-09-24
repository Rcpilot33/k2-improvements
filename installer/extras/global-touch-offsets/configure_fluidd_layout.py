#!/usr/bin/env python3
"""Seed Fluidd metadata for the optional Cartographer Touch-offset editor."""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


CATEGORY_NAME = "Z Offsets"
LEGACY_CATEGORY_NAMES = {"Global Touch offsets", "Just Z Offsets"}
CATEGORY_NAMES_CASEFOLD = {
    CATEGORY_NAME.casefold(),
    *(name.casefold() for name in LEGACY_CATEGORY_NAMES),
}
CATEGORY_ID = str(
    uuid.uuid5(
        uuid.NAMESPACE_URL,
        "https://github.com/Rcpilot33/k2-improvements/fluidd/global-touch-offsets",
    )
)
MACRO_NAME = "GLOBAL_Z_OFFSETS_CARTO"
MACRO_ALIAS = "Global_Z_Offsets_Carto"
MACRO_COLOR = "#2196F3"


class LayoutError(RuntimeError):
    pass


def merge_layout(namespace):
    if not isinstance(namespace, dict):
        raise LayoutError("Fluidd database namespace is not an object")

    result = dict(namespace)
    macros = result.get("macros", {})
    if not isinstance(macros, dict):
        raise LayoutError("Fluidd macros database item is not an object")
    macros = dict(macros)

    categories = macros.get("categories", [])
    stored = macros.get("stored", [])
    if not isinstance(categories, list) or any(
        not isinstance(item, dict) for item in categories
    ):
        raise LayoutError("Fluidd macro categories are invalid")
    if not isinstance(stored, list) or any(not isinstance(item, dict) for item in stored):
        raise LayoutError("Fluidd stored macros are invalid")

    categories = [dict(item) for item in categories]
    stored = [dict(item) for item in stored]
    category = next(
        (
            item
            for item in categories
            if str(item.get("name", "")).casefold() in CATEGORY_NAMES_CASEFOLD
            and item.get("id")
        ),
        None,
    )
    if category is None:
        category_id = CATEGORY_ID
        if category_id in {str(item.get("id")) for item in categories}:
            category_id = str(uuid.uuid4())
        categories.append({"id": category_id, "name": CATEGORY_NAME})
    else:
        category_id = str(category["id"])
        category["name"] = CATEGORY_NAME

    item = next(
        (
            value
            for value in stored
            if str(value.get("name", "")).casefold() == MACRO_NAME.casefold()
        ),
        None,
    )
    if item is None:
        stored.append(
            {
                "name": MACRO_NAME,
                "alias": MACRO_ALIAS,
                "visible": True,
                "disabledWhilePrinting": True,
                "color": MACRO_COLOR,
                "categoryId": category_id,
            }
        )
    else:
        if not item.get("alias"):
            item["alias"] = MACRO_ALIAS
        item["disabledWhilePrinting"] = True
        item["color"] = MACRO_COLOR
        valid_ids = {str(value.get("id")) for value in categories if value.get("id")}
        category_names_by_id = {
            str(value.get("id")): str(value.get("name", "")).casefold()
            for value in categories
            if value.get("id")
        }
        current_category = str(item.get("categoryId", "0"))
        if (
            current_category not in valid_ids
            or category_names_by_id.get(current_category) == "uncategorized"
        ):
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


def configure(api_url):
    api_url = api_url.rstrip("/")
    query = urllib.parse.urlencode({"namespace": "fluidd"})
    payload = _request_json(
        "{}/server/database/item?{}".format(api_url, query), allow_missing=True
    )
    namespace = {} if payload is None else _result_value(payload)
    updated = merge_layout(namespace)
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
    api_url = os.environ.get("MOONRAKER_URL", "http://127.0.0.1:7125")
    try:
        changed = configure(api_url)
    except LayoutError as exc:
        print("E: could not configure Fluidd Z Offsets category: {}".format(exc))
        return 1

    if changed:
        print("I: configured Global_Z_Offsets_Carto in '{}'".format(CATEGORY_NAME))
        print("I: refresh Fluidd to load its alias, category, and color")
    else:
        print("I: Fluidd Z Offsets category is already configured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
