import logging

import streamlit as st

import mods

logger = logging.getLogger("root")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


st.set_page_config(layout="wide")
st.title("Welcome to Weave Mods!")
st.write("This is a demo app to show examples of using the Weave Mods SDK.")

with st.sidebar:
    st.title("Example mod helpers")
    op = mods.st.selectbox("Ops", mods.st.OP)
    if op:
        v = mods.st.multiselect("Versions", op)
    ds = mods.st.multiselect("Datasets", mods.st.DATASET)
    if ds:
        st.write(f"Datasets: {[d.name for d in ds]}")

if op:
    st.write("Select a row to see the chat thread")
    calls, selected = mods.st.tracetable([v.ref().uri() for v in v])
    if selected:
        call = calls.df.iloc[selected]
        mods.st.chat_thread(call)
else:
    st.write("*Select an op to see traces*")
