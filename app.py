"""OrbitFit: health self-monitoring for astronauts. Start with:  streamlit run app.py"""

from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent / "assets"

st.set_page_config(page_title="OrbitFit", page_icon=str(ASSETS / "icon.svg"), layout="wide")
st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "logo.svg"))

pages = [
    st.Page("pages/today.py", title="Crew", default=True),
    st.Page("pages/emergency.py", title="Emergency"),
    st.Page("pages/guides.py", title="Guides"),
    st.Page("pages/cmo.py", title="CMO"),
    st.Page("pages/forecast.py", title="Forecast"),
    st.Page("pages/downlink.py", title="Downlink"),
    st.Page("pages/earth.py", title="Earth"),
    st.Page("pages/mission.py", title="Mission"),
    st.Page("pages/about.py", title="About"),
    st.Page("pages/sources.py", title="Sources"),
]
st.navigation(pages, position="top").run()
