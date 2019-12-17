import yaml

CONFIG = {}

def load():
    global CONFIG
    with open("config.yaml", encoding="UTF8") as file:
        CONFIG = yaml.load(file, Loader=yaml.FullLoader)
    print(CONFIG)


def get_var(key):
    if key in CONFIG:
        return CONFIG.get(key)
    raise KeyError(f"Missing config key in the config file: {key}")