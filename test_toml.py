import tomllib

try:
    with open("config/config.toml", "rb") as f:
        tomllib.load(f)
    print("TOML loaded successfully")
except Exception as e:
    print(f"Error loading TOML: {e}")
