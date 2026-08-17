# Clone this linked subdirectory of decky-loader to the root of this plugin,
# so it's imports can be resolved: https://github.com/SteamDeckHomebrew/decky-loader/tree/main/backend/decky_loader
import decky
import pprint
import logging
from typing import Any


logger = logging.getLogger("tunneldeck")
if not logger.handlers:
    handler = logging.FileHandler(
        f"{decky.DECKY_PLUGIN_LOG_DIR}/tunneldeck.log", mode="w+"
    )
    handler.setFormatter(
        logging.Formatter("[TunnelDeck] %(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def log_pretty(obj: Any) -> str:
    pp = pprint.PrettyPrinter(indent=2, sort_dicts=False)
    return f"{pp.pformat(obj)}"
