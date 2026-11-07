"""Hard rules: wording (never a diagnosis), the footer, honest labels, and nothing fetched from the internet."""

import re
from pathlib import Path

from ui.state import FOOTER

ROOT = Path(__file__).resolve().parent.parent
CODE_DIRS = ["engine", "guidance", "pages", "ui", "pose", "db", "data", "config"]

# "diagnosis" may only appear when saying we do NOT give one.
ALLOWED_DIAGNOSIS = re.compile(
    r"(not a diagnosis|no diagnosis|never gives a diagnosis|never call anything a diagnosis|"
    r"never says a person has a condition)", re.IGNORECASE)


def code_files():
    for d in CODE_DIRS:
        for path in (ROOT / d).rglob("*.py"):
            yield path
    yield ROOT / "app.py"


def test_diagnosis_is_only_ever_negated():
    problems = []
    for path in code_files():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r"diagnos", line, re.IGNORECASE) and not ALLOWED_DIAGNOSIS.search(line):
                problems.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
    assert problems == []


def test_footer_wording_and_it_is_on_every_page():
    assert FOOTER == ("Prototype decision-support tool. Not a medical device. "
                      "Thresholds are demonstration values, not clinically validated.")
    for page in (ROOT / "pages").glob("*.py"):
        text = page.read_text(encoding="utf-8")
        assert "state.page_start()" in text, page.name
        assert text.rstrip().endswith("state.footer()"), page.name


def test_nothing_is_loaded_from_the_internet():
    banned = ["fonts.googleapis", "cdn.", "unpkg.com", "@import url(", "<script src=", "requests.get", "urllib.request"]
    for path in code_files():
        text = path.read_text(encoding="utf-8")
        for word in banned:
            assert word not in text, f"{path.name} contains {word}"


def test_usage_statistics_are_off():
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "gatherUsageStats = false" in config


def test_simulated_things_say_so():
    widgets = (ROOT / "ui" / "widgets.py").read_text(encoding="utf-8")
    assert "Simulated ARED target load" in widgets
    about = (ROOT / "pages" / "about.py").read_text(encoding="utf-8")
    assert "demo crew data is synthetic" in about.lower()
    assert "earth link is simulated" in about.lower()


def test_no_bone_density_or_muscle_mass_numbers_are_claimed():
    for path in code_files():
        for line in path.read_text(encoding="utf-8").splitlines():
            low = line.lower()
            if "bone density" in low and "measure" in low:
                assert "cannot" in low or "not" in low, line


def test_app_is_only_reachable_from_this_computer():
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'address = "localhost"' in config


def test_the_menu_is_never_hidden_on_phones_and_tablets():
    # On narrow screens Streamlit moves the top menu into the side panel; hiding it hides the menu.
    from ui.theme import CSS
    compact = CSS.replace(" ", "")
    assert '[data-testid="stSidebar"]{{display:none' not in compact
    assert '[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none' not in compact
    assert 'content: "Menu"' in CSS


def test_only_real_cards_get_the_card_style():
    # Plain blocks (like auto-refreshing sections) must not look like cards with no padding.
    from ui.theme import CSS
    assert '[class*="st-key-card_"]' in CSS
    assert '[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]' not in CSS
    for path in list((ROOT / "pages").glob("*.py")) + list((ROOT / "ui").glob("*.py")):
        if path.name == "theme.py":
            continue
        assert "container(border=True)" not in path.read_text(encoding="utf-8"), path.name
