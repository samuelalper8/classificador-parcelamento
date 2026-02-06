import streamlit as st
import pandas as pd
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
import re
import io
import os

# --- CONFIGURAÇÃO DE AMBIENTE (AJUSTE AUTOMÁTICO NUVEM vs WINDOWS) ---
# Se estiver rodando no Windows localmente, descomente e ajuste estas linhas:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# POPPLER_PATH = r'C:\poppler-24.02.0\Library\bin'

# No Streamlit Cloud (Linux), não precisamos definir caminhos, ele acha sozinho
# se instalarmos via packages.txt. Portanto, deixamos POPPLER_PATH como None
if os.name == 'nt': # Se for Windows
    POPPLER_PATH = r'C:\poppler-24.02.0\Library\bin' # Ajuste para seu caminho local se for testar no PC
else:
    POPPLER_PATH = None # No Linux/Cloud, o padrão funciona

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Fiscal AI - OCR", page_icon="👁️", layout="wide")
# ... (resto do código igual) ...
