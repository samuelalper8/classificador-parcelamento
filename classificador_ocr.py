import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

st.set_page_config(page_title="Auditor Fiscal - Teste", layout="wide")

st.title("Teste de Conexão")
st.write("Se você está lendo isso, o Streamlit está funcionando!")

uploaded_files = st.file_uploader("Teste de Upload", type="pdf", accept_multiple_files=True)

if uploaded_files:
    if st.button("Processar"):
        st.success("Arquivos recebidos!")
