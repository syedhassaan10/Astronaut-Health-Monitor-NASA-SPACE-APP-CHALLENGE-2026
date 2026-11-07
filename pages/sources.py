"""Sources: NASA references, other references, credits, and how NASA data was used."""

import streamlit as st

from ui import state, theme

from guidance.sources import CREDITS, NASA_SOURCES, OTHER_SOURCES

state.page_start()

theme.page_header("Sources", "NASA references, other references and credits. Every link was checked.")

st.subheader("How OrbitFit uses NASA resources")
st.write(
    "OrbitFit's choice of health indicators, the reasons shown with every alert and every guide, and the exercise "
    "model come from NASA's Human Research Program risk pages and NASA technical reports listed below. Each alert "
    "and guide links to the page it is based on. The challenge also points to NASA's Open Science Data Repository "
    "(OSDR) for real spaceflight biology data; OrbitFit does not load an OSDR dataset at run time. Its demo crew "
    "data is synthetic and generated on the device."
)


def show(sources):
    for s in sources:
        with st.container(border=True):
            st.markdown(f"**[{s.title}]({s.url})**  \n{s.organization}")
            st.caption(s.used_for)


state.demo_evidence_section()

st.subheader("NASA references")
show(NASA_SOURCES)
st.subheader("Other references")
show(OTHER_SOURCES)
st.subheader("Credits")
show(CREDITS)
st.caption("All links were checked on 6 November 2026. Links open in your browser and need internet; the app does not.")

state.footer()
