 Folder Structure

Place the script in your Frappe app's directory structure:
text

your_app/
├── your_app/
│   ├── utils/
│   │   └── fix_null_modules.py
│   └── __init__.py
└── README.md



🛠 Usage
Basic Usage

Run the script via bench command to fix NULL modules for all doctypes in your app:
bash

bench --site <your-site> execute "your_app.utils.fix_null_modules.run" --kwargs '{"app": "your_app"}'

Example:
bash

bench --site aljar.localhost execute "aljar_system.utils.fix_null_modules.run" --kwargs '{"app": "aljar_system"}'

Advanced Usage with Custom Overrides

If you want to override module names manually for specific doctypes, pass a custom_override_map:
bash

bench --site aljar.localhost execute "aljar_system.utils.fix_null_modules.run" \
  --kwargs '{"app": "aljar_system", "custom_override_map": {"HR": "human_resources"}}'
