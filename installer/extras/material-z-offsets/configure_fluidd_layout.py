#!/usr/bin/env python3
"""Seed Fluidd metadata for the optional material Z-offset editor."""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


CATEGORY_NAME = "Z Offsets"
CATEGORY_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/Rcpilot33/k2-improvements/fluidd/z-offsets"))
MACRO_NAME = "MATERIAL_Z_OFFSETS"
MACRO_ALIAS = "Material_Z_Offsets"
MACRO_COLOR = "#FF9800"


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
    if not isinstance(categories, list) or not isinstance(stored, list) or any(
        not isinstance(item, dict) for item in categories + stored
    ):
        raise LayoutError("Fluidd macro metadata is invalid")
    categories = [dict(item) for item in categories]
    stored = [dict(item) for item in stored]

    category = next((item for item in categories if str(item.get("name", "")).casefold() == CATEGORY_NAME.casefold() and item.get("id")), None)
    if category is None:
        category_id = CATEGORY_ID
        if category_id in {str(item.get("id")) for item in categories}:
            category_id = str(uuid.uuid4())
        categories.append({"id": category_id, "name": CATEGORY_NAME})
    else:
        category_id = str(category["id"])

    item = next((value for value in stored if str(value.get("name", "")).casefold() == MACRO_NAME.casefold()), None)
    if item is None:
        stored.append({
            "name": MACRO_NAME,
            "alias": MACRO_ALIAS,
            "visible": True,
            "disabledWhilePrinting": True,
            "color": MACRO_COLOR,
            "categoryId": category_id,
        })
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
        current_category = str(item.get("categoryId", ""))
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
    if not isinstance(payload, dict) or "error" in payload:
        raise LayoutError("Moonraker database request failed")
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
        "%s/server/database/item?%s" % (api_url, query), allow_missing=True
    )
    namespace = {} if payload is None else _result_value(payload)
    updated = merge_layout(namespace)
    if updated == namespace:
        return False
    _result_value(_request_json(
        "%s/server/database/item" % api_url,
        method="POST",
        body={"namespace": "fluidd", "key": "macros", "value": updated["macros"]},
    ))
    return True


def main():
    try:
        changed = configure(os.environ.get("MOONRAKER_URL", "http://127.0.0.1:7125"))
    except LayoutError as exc:
        print("E: could not configure Fluidd Z Offsets category: %s" % exc)
        return 1
    print("I: %s" % ("configured Material_Z_Offsets in 'Z Offsets'" if changed else "Fluidd Material_Z_Offsets metadata is already configured"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
