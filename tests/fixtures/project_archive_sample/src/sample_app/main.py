import yaml


class QueryService:
    def __init__(self, config_path: str):
        self.config_path = config_path

    def run(self) -> str:
        return load_config(self.config_path)["mode"]


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)
