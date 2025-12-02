"""
Utilities for normalizing module names and fixing module assignments in
custom JSON files and fixtures of a Frappe application. This script
builds a module map from modules.txt, applies optional user overrides,
updates custom JSON metadata, and ensures fixtures have correct module
values based on discovered mappings.
"""

import re
import json
from pathlib import Path

import frappe
from frappe import scrub


def build_module_map(app: str) -> dict[str, str]:
    """
    Build a mapping of module names from modules.txt to normalized names.

    Reads modules.txt inside the given app, extracts non-empty lines, and
    applies normalization to build a mapping of original → normalized
    module names.

    Args:
        app: The Frappe app name.

    Returns:
        A dictionary mapping original module names to normalized names.

    Raises:
        FileNotFoundError: If modules.txt is missing.
    """
    modules_path = Path(frappe.get_app_path(app)) / "modules.txt"

    if not modules_path.exists():
        raise FileNotFoundError(f"modules.txt not found at {modules_path}")

    module_names = [
        line.strip()
        for line in modules_path.read_text().splitlines()
        if line.strip()
    ]

    return {name: scrub(name) for name in module_names}


def merge_maps(map_build: dict, map_user: dict) -> dict:
    """
    Merge the auto-generated module map with the user-defined override map.

    Any user-provided values override the automatically generated ones.
    If multiple auto-map entries point to the same normalized value but
    the user overrides only one key, the unused conflicting keys are
    removed.

    Args:
        map_build: Automatically generated module map.
        map_user: User override map.

    Returns:
        A merged and conflict-resolved module map.
    """
    final = map_build.copy()
    user_values = set(map_user.values())

    keys_to_remove = [
        key for key, value in final.items()
        if value in user_values and key not in map_user
    ]

    for key in keys_to_remove:
        del final[key]

    final.update(map_user)
    return final


def replace_module_in_json_in_customs(data, module_name, mapping_custom_to_module):
    """
    Recursively update custom JSON data, setting missing module fields.

    If a JSON object contains `"module": null`, this function replaces it
    with the provided module name and stores the mapping of docname →
    module for use during fixture updates.

    Args:
        data: JSON data loaded into Python objects (dict/list).
        module_name: The module name to assign when missing.
        mapping_custom_to_module: Dict to store docname → module mapping.

    Returns:
        The updated JSON structure.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "module" and value is None:
                try:
                    docname = data["name"]
                except Exception:
                    print("  ⚠️  WARNING: Found module=None but JSON object has no 'name'. Skipping...")
                    continue

                data[key] = module_name
                mapping_custom_to_module[docname] = module_name
            else:
                replace_module_in_json_in_customs(value, module_name, mapping_custom_to_module)

    elif isinstance(data, list):
        for item in data:
            replace_module_in_json_in_customs(item, module_name, mapping_custom_to_module)

    return data


def fix_custom_json_modules(app: str, final_map: dict, mapping_custom_to_module: dict):
    """
    Update module values inside all custom JSON files in the app.

    Iterates through each module’s `custom` folder and ensures that JSON
    metadata has correct module names. Updates the mapping of custom
    documents to module names for later use in fixture processing.

    Args:
        app: The Frappe app name.
        final_map: The merged module map.
        mapping_custom_to_module: A dictionary that will be populated
            with docname → module name mappings.
    """
    app_path = Path(frappe.get_app_path(app))

    for original_module_name, normalized_name in final_map.items():
        module_folder = app_path / normalized_name / "custom"
        if not module_folder.exists():
            continue

        for json_file in module_folder.glob("*.json"):
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            updated_data = replace_module_in_json_in_customs(
                data,
                original_module_name,
                mapping_custom_to_module
            )

            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(updated_data, f, indent=4, ensure_ascii=False)


def replace_module_in_json_in_fixture(data, mapping_custom_to_module, app_name):
    """
    Recursively update fixture JSON data to have correct module names.

    If a fixture item has `"module": null`, it is replaced by:
        - the module name associated with the corresponding docname,
          if known from custom JSON;
        - otherwise a fallback module name for the entire app.

    Args:
        data: JSON structure loaded into Python objects.
        mapping_custom_to_module: Mapping of docname → module.
        app_name: Fallback module name.

    Returns:
        The updated JSON data.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "module" and value is None:
                try:
                    docname = data["name"]
                except Exception:
                    print("  ⚠️  Fixture item missing 'name' key. Skipping item...")
                    continue

                if docname in mapping_custom_to_module:
                    data[key] = mapping_custom_to_module[docname]
                else:
                    data[key] = app_name

            else:
                replace_module_in_json_in_fixture(value, mapping_custom_to_module, app_name)

    elif isinstance(data, list):
        for item in data:
            replace_module_in_json_in_fixture(item, mapping_custom_to_module, app_name)

    return data


def get_app_module_name(final_map: dict, app: str) -> str:
    """
    Determine the fallback module name for fixtures.

    The fallback is the original module name whose normalized version
    equals the application name. If none match, the app name is returned.

    Args:
        final_map: Mapping of original → normalized module names.
        app: The Frappe app name.

    Returns:
        The best fallback module name.
    """
    for original, normalized in final_map.items():
        if normalized == app:
            return original
    return app


def fix_fixture_modules(app: str, mapping_custom_to_module: dict, final_map: dict):
    """
    Update all JSON fixture files in the app to ensure correct module
    assignments.

    Loads each fixture JSON file, applies module corrections based on
    custom document mappings, and writes the changes back to disk.

    Args:
        app: The Frappe app name.
        mapping_custom_to_module: Mapping of docname → module name.
        final_map: Final merged module map.
    """
    app_path = Path(frappe.get_app_path(app))
    fixtures_path = app_path / "fixtures"

    if not fixtures_path.exists():
        print("⚠️  No fixtures directory found — skipping.")
        return

    app_name = get_app_module_name(final_map, app)

    for json_file in fixtures_path.glob("*.json"):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        updated_data = replace_module_in_json_in_fixture(
            data,
            mapping_custom_to_module,
            app_name
        )

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(updated_data, f, indent=4, ensure_ascii=False)


def run(app: str, custom_override_map: dict | None = None):
    """
    Entry point for bench execute.

    Args:
        app: The Frappe app name to process.
        custom_override_map: Optional dict of user overrides where
            keys are original module names and values are normalized names.

    Example bench usage:
        bench execute path.to.module.run --kwargs '{"app": "myapp", "custom_override_map": {"HR": "human_resources"}}'
    """
    if custom_override_map is None:
        custom_override_map = {}

    mapping_custom_to_module = {}

    auto_map = build_module_map(app)
    final_map = merge_maps(auto_map, custom_override_map)

    fix_custom_json_modules(app, final_map, mapping_custom_to_module)
    fix_fixture_modules(app, mapping_custom_to_module, final_map)

    return {
        "final_map": final_map,
        "custom_mappings": mapping_custom_to_module,
    }
