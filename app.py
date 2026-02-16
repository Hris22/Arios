import streamlit as st
import pandas as pd
import time

st.title("Top 15 Cryptocurrencies at the moment")
st.subheader("Top curencys")

placeholder = st.empty()

while True:
    try:
        df = pd.read_csv("crypto_data.csv")
        placeholder.dataframe(df)
       
    except:
        pass
    time.sleep(1)