import logging

import streamlit as st

import mods

logger = logging.getLogger("root")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


st.set_page_config(layout="wide")
st.title("Welcome to Weave Mods!")

with st.sidebar:
    st.title("Example mod helpers")
    op = mods.st.op_selectbox("Ops")
    if op:
        st.write(f"Op Name: {op.name}")
    ds = mods.st.dataset_selectbox("Datasets")
    if ds:
        st.write(f"Dataset: {ds.name}")

if op:
    st.write(f"Calls table for: {op.name}")
    calls, selected = mods.st.calls_table(op.ref().uri())
    if selected:
        call = calls.df.iloc[selected]
        mods.st.call_chat_thread(call)
