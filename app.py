import streamlit as st
import pandas as pd
import time

# Change the whole code to work with FastAPI instead of Streamlit

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