import re
import json
from pathlib import Path
import frappe


# ---------------------------------------------------------
# NORMALIZE MODULE NAME
# ---------------------------------------------------------

def normalize_module_name(module_name: str) -> str:
    return re.sub(r"[\s-]+", "_", module_name.strip().lower())


# ---------------------------------------------------------
# BUILD MODULE MAP FROM modules.txt
# ---------------------------------------------------------

def build_module_map(app: str) -> dict[str, str]:
    modules_path = Path(frappe.get_app_path(app)) / "modules.txt"

    if not modules_path.exists():
        raise FileNotFoundError(f"modules.txt not found at {modules_path}")

    module_names = [
        line.strip()
        for line in modules_path.read_text().splitlines()
        if line.strip()
    ]

    return {name: normalize_module_name(name) for name in module_names}


# ---------------------------------------------------------
# MERGE AUTO MAP + OVERRIDE MAP
# ---------------------------------------------------------

def merge_maps(map_build: dict, map_user: dict) -> dict:
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


# ---------------------------------------------------------
# FIX CUSTOM JSON
# ---------------------------------------------------------

def replace_module_in_json_in_customs(data, module_name, mapping_custom_to_module):
    if isinstance(data, dict):

        for key, value in data.items():

            if key == "module" and value is None:

                try:
                    docname = data["name"]
                except Exception:
                    print("  ⚠️  WARNING: Found module=None but JSON object has no 'name'. Skipping...")
                    continue

                data[key] = module_name
                print(f"  ✔ Custom: Set module for '{docname}' → {module_name}")
                mapping_custom_to_module[docname] = module_name

            else:
                replace_module_in_json_in_customs(value, module_name, mapping_custom_to_module)

    elif isinstance(data, list):
        for item in data:
            replace_module_in_json_in_customs(item, module_name, mapping_custom_to_module)

    return data


def fix_custom_json_modules(app: str, final_map: dict, mapping_custom_to_module: dict):
    app_path = Path(frappe.get_app_path(app))

    print("\n=== MODULE MAP (FINAL) ===")
    for original, normalized in final_map.items():
        print(f" {original}  →  {normalized}")
    print("==========================\n")

    for original_module_name, normalized_name in final_map.items():

        module_folder = app_path / normalized_name / "custom"

        if not module_folder.exists():
            continue

        for json_file in module_folder.glob("*.json"):
            print(f"→ Processing custom JSON: {json_file.name}")

            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            updated_data = replace_module_in_json_in_customs(
                data,
                original_module_name,
                mapping_custom_to_module
            )

            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(updated_data, f, indent=4, ensure_ascii=False)

            print(f"  ✔ Saved {json_file.name} with module={original_module_name}\n")

    print("✔ All custom JSON files processed.\n")


# ---------------------------------------------------------
# FIX FIXTURES
# ---------------------------------------------------------

def replace_module_in_json_in_fixture(data, mapping_custom_to_module, app_name):
    if isinstance(data, dict):

        for key, value in data.items():

            if key == "module" and value is None:

                try:
                    docname = data["name"]
                except Exception:
                    print("  ⚠️  Fixture item missing 'name' key. Skipping item...")
                    continue

                if docname in mapping_custom_to_module:
                    new_module = mapping_custom_to_module[docname]
                    data[key] = new_module
                    print(f"  ✔ Fixture: Set module for '{docname}' → {new_module}")
                else:
                    print(f"  ⚠️  No mapping for '{docname}', using app name '{app_name}'")
                    data[key] = app_name

            else:
                replace_module_in_json_in_fixture(value, mapping_custom_to_module, app_name)

    elif isinstance(data, list):
        for item in data:
            replace_module_in_json_in_fixture(item, mapping_custom_to_module, app_name)

    return data


def get_app_module_name(final_map: dict, app: str) -> str:
    # Look for normalized == app
    for original, normalized in final_map.items():
        if normalized == app:
            return original
    return app  # fallback


def fix_fixture_modules(app: str, mapping_custom_to_module: dict, final_map: dict):
    app_path = Path(frappe.get_app_path(app))
    fixtures_path = app_path / "fixtures"

    if not fixtures_path.exists():
        print("⚠️  No fixtures directory found — skipping.")
        return

    print("\n=== PROCESSING FIXTURES ===\n")

    # Correct logic here
    app_name = get_app_module_name(final_map, app)
    print(f"Using fixture fallback module name: {app_name}")

    for json_file in fixtures_path.glob("*.json"):
        print(f"→ Processing fixture: {json_file.name}")

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        updated_data = replace_module_in_json_in_fixture(
            data,
            mapping_custom_to_module,
            app_name
        )

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(updated_data, f, indent=4, ensure_ascii=False)

        print(f"  ✔ Saved fixture {json_file.name}\n")

    print("✔ All fixtures updated.\n")

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

if __name__ == "__main__":

    custom_override_map = {
        "Al-Jar HR tawfik": "al_jar_hr",
    }

    app = "fabrica_construction"

    mapping_custom_to_module = {}

    auto_map = build_module_map(app)
    final_map = merge_maps(auto_map, custom_override_map)

    fix_custom_json_modules(app, final_map, mapping_custom_to_module)

    print("\n=== CUSTOM → MODULE MAPPING (RESULT) ===")
    for k, v in mapping_custom_to_module.items():
        print(f" {k}  →  {v}")
    print("========================================\n")

    fix_fixture_modules(app, mapping_custom_to_module, final_map)
