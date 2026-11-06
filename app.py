"""OrbitFit: health self-monitoring for astronauts. Start with:  streamlit run app.py"""

import streamlit as st

st.set_page_config(page_title="OrbitFit", page_icon="🛰️", layout="wide")

pages = [
    st.Page("pages/today.py", title="Today (astronaut)", icon="🧑‍🚀", default=True),
    st.Page("pages/emergency.py", title="Emergency", icon="🚨"),
    st.Page("pages/guides.py", title="Health guides", icon="📖"),
    st.Page("pages/cmo.py", title="Crew Medical Officer", icon="🩺"),
    st.Page("pages/downlink.py", title="Downlink to Earth", icon="📡"),
    st.Page("pages/earth.py", title="Earth receiver", icon="🌍"),
    st.Page("pages/about.py", title="About", icon="ℹ️"),
    st.Page("pages/sources.py", title="Sources", icon="📚"),
]
st.navigation(pages).run()
