"""Every page renders without errors (Streamlit's headless app tester, on a temporary logbook)."""

import os

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

PAGES = ["pages/today.py", "pages/emergency.py", "pages/guides.py", "pages/cmo.py", "pages/about.py",
         "pages/sources.py", "pages/downlink.py", "pages/earth.py"]


@pytest.fixture(autouse=True)
def temp_logbook(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITFIT_DB", str(tmp_path / "orbitfit.db"))
    monkeypatch.setenv("ORBITFIT_LINK_DB", str(tmp_path / "link.db"))
    monkeypatch.setenv("ORBITFIT_EARTH_DB", str(tmp_path / "earth.db"))
    monkeypatch.chdir(os.path.dirname(os.path.dirname(__file__)))


def run_page(page):
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    if page != PAGES[0]:
        at.switch_page(page)
        at.run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_errors(page):
    at = run_page(page)
    assert not at.exception, [e.value for e in at.exception]
    footer = " ".join(c.value for c in at.caption)
    assert "Not a medical device" in footer


def test_today_shows_status_routine_and_tabs():
    at = run_page("pages/today.py")
    assert "Today" in at.title[0].value
    labels = [m.label for m in at.metric]
    assert "1 · Check-in" in labels and "Routine streak" in labels
    assert len(at.tabs) == 4


def test_saving_a_check_in_updates_the_routine():
    at = run_page("pages/today.py")
    at.slider[2].set_value(5)                 # pain 5
    at.selectbox[2].set_value("knee")         # where (sidebar has 2 selectboxes first)
    at.button[0].click()                      # Save check-in (first form button)
    at.run()
    assert not at.exception
    assert any("Check-in saved" in s.value for s in at.success)


def test_emergency_chest_pain_shows_the_chest_pain_guide():
    at = run_page("pages/emergency.py")
    at.radio(key="q_chest").set_value("Yes")
    at.run()
    text = " ".join(m.value for m in at.markdown)
    assert "EMERGENCY" in text
    assert "Chest pain" in text
    steps = [c.label for c in at.checkbox]
    assert any("heart rate, blood pressure and oxygen saturation" in s for s in steps)


def test_emergency_cpr_steps_follow_the_sidebar_location():
    at = run_page("pages/emergency.py")
    at.radio(key="q_responsive").set_value("No")
    at.radio(key="q_breathing").set_value("No")
    at.run()
    steps = " ".join(c.label for c in at.checkbox)
    assert "restraint" in steps  # default location is the ISS (microgravity)
    at.selectbox(key="location_id").set_value("moon")
    at.run()
    steps = " ".join(c.label for c in at.checkbox)
    assert "floor" in steps


def test_cmo_replay_slider_changes_the_status():
    at = run_page("pages/cmo.py")
    text_day30 = " ".join(m.value for m in at.markdown)
    assert "ACT" in text_day30
    at.slider[0].set_value(5)
    at.run()
    assert not at.exception
    statuses = " ".join(m.value for m in at.markdown)
    assert "■ ACT" not in statuses


def test_queueing_a_packet_shows_it_waiting_for_a_link():
    at = run_page("pages/downlink.py")
    at.button[1].click()  # sidebar has no buttons; [0] opens/closes the link, [1] queues a packet
    at.run()
    assert not at.exception
    assert any("Queued pkt-d30-" in s.value for s in at.success)
    text = " ".join(m.value for m in at.markdown)
    assert "Waiting for link" in text
