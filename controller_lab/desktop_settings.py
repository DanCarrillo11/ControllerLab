"""Desktop preferences and executable-specific rules, separate from device presets."""
from copy import deepcopy
import json
import ntpath
from pathlib import Path
import uuid

from .storage import atomic_write

DEFAULTS = dict(minimize_to_tray=False, close_to_tray=False,
                hotkey_enabled=True, stop_hotkey="Ctrl+Alt+F11",
                setup_completed=False, game_profiles_enabled=False, game_rules=[], reduce_motion=False)


def executable_key(path):
    if not isinstance(path, str) or not ntpath.isabs(path) or ntpath.splitext(path)[1].casefold() != ".exe":
        raise ValueError("Choose the game's full .exe path.")
    return ntpath.normcase(ntpath.normpath(path))


def clean_rules(rules):
    if not isinstance(rules, list) or len(rules) > 256:
        raise ValueError("Game profiles must contain at most 256 rules.")
    result, seen = [], set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("Invalid game profile.")
        name, guid, profile = rule.get("name"), rule.get("guid"), rule.get("profile_id", "")
        if not isinstance(name, str) or not name.strip() or not isinstance(guid, str) or not guid or not isinstance(profile, str):
            raise ValueError("Choose a game, controller and profile.")
        executable = executable_key(rule.get("executable"))
        identity = (guid, executable)
        if identity in seen:
            raise ValueError("This game already has a rule for that controller. Edit the existing rule.")
        seen.add(identity)
        result.append(dict(id=str(rule.get("id") or uuid.uuid4().hex)[:80], name=name.strip()[:120],
                           executable=executable, guid=guid[:256], profile_id=profile[:80],
                           enabled=rule.get("enabled", True) is True))
    return result


class DesktopSettings:
    def __init__(self, root):
        self.path = Path(root) / "desktop.json"
        self.data, self.warning = deepcopy(DEFAULTS), ""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Invalid desktop preferences")
            self.data = self.clean(raw)
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            self.warning = "Desktop preferences could not be read. Default desktop settings are in use."

    @staticmethod
    def clean(raw):
        result = deepcopy(DEFAULTS)
        for key, default in DEFAULTS.items():
            value = raw.get(key, default)
            if isinstance(default, bool):
                result[key] = value if isinstance(value, bool) else default
            elif key == "stop_hotkey":
                result[key] = value[:80] if isinstance(value, str) and value.strip() else default
            elif key == "game_rules":
                result[key] = clean_rules(value)
        return result

    def save(self, **changes):
        data = self.clean(dict(self.data, **changes))
        atomic_write(self.path, json.dumps(dict(schema=1, **data), indent=2))
        self.data = data


def choose_game_rule(rules, guid, running, foreground="", previous=""):
    """Full-path matching; keep the previous game when the user alt-tabs away."""
    candidates = [r for r in rules if r["enabled"] and r["guid"] == guid and r["executable"] in running]
    for path in (foreground, previous):
        match = next((r for r in candidates if r["executable"] == path), None)
        if match:
            return match, False
    return (candidates[0], False) if len(candidates) == 1 else (None, len(candidates) > 1)
