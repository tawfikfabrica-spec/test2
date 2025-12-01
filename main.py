import re
import json
from pathlib import Path
import frappe


def normalize_module_name(module_name: str) -> str:
    return re.sub(r"[\s-]+", "_", module_name.strip().lower())


def build_module_map(app: str) -> dict[str, str]:
    modules_path = Path(frappe.get_app_path(app)) / "modules.txt"
    if not modules_path.exists():
        raise FileNotFoundError(f"modules.txt not found at {modules_path}")

    module_names = [
        line.strip() for line in modules_path.read_text().splitlines() if line.strip()
    ]

    return {name: normalize_module_name(name) for name in module_names}


def merge_maps(map_build: dict, map_user: dict) -> dict:
    """
    Merge maps with special priority rules:
    
    1. If both maps share the same key → use map_user value
    2. If map_user contains a value that also exists in map_build → delete it from map_build
    """

    # Start with a copy of the build map
    final = map_build.copy()

    # Rule 2 — Remove conflicting values in map_build
    user_values = set(map_user.values())

    keys_to_remove = [
        key for key, value in final.items()
        if value in user_values and key not in map_user
    ]

    for key in keys_to_remove:
        del final[key]

    # Rule 1 — Overwrite by key
    final.update(map_user)

    return final


def replace_module_in_json(data, module_name):
    """Recursively update any key 'module': None in the JSON structure."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "module" and value is None:
                data[key] = module_name
            else:
                replace_module_in_json(value, module_name)

    elif isinstance(data, list):
        for item in data:
            replace_module_in_json(item, module_name)

    return data


def fix_custom_json_modules(app: str, override_map: dict[str, str] = None):
    """Fix 'module' fields in custom JSON files with override support."""
    app_path = Path(frappe.get_app_path(app))

    auto_map = build_module_map(app)
    override_map = override_map or {}

    # combine → override wins
    final_map = merge_maps(auto_map, override_map)

    # Create reverse map (normalized → original_name)
    reverse_map = {v: k for k, v in final_map.items()}

    print("\n=== Final Module Map ===")
    for k, v in final_map.items():
        print(f"{k} → {v}")
    print("=======================\n")

    for original_module_name, normalized_name in final_map.items():

        module_folder = app_path / normalized_name / "custom"

        if not module_folder.exists():
            continue

        for json_file in module_folder.glob("*.json"):
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            updated_data = replace_module_in_json(data, original_module_name)

            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(updated_data, f, indent=4, ensure_ascii=False)

            print(f"✔ Updated {json_file} → module={original_module_name}")

    print("\n✔ All custom JSON files processed.\n")


# Example run
if __name__ == "__main__":

    custom_override_map = {
        "Al-Jar HR tawfik": "al_jar_hr",
    }

    fix_custom_json_modules("aljar_system", custom_override_map)
