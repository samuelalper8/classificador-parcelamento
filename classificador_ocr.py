import streamlit as st
import pandas as pd
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
import re
import io
import os

# --- CONFIGURAÇÃO DO TESSERACT E POPPLER (AJUSTE SEUS CAMINHOS AQUI) ---
# Se você adicionou ao PATH do Windows, pode não precisar destas linhas.
# Caso contrário, aponte para onde instalou:

# Caminho do executável do Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Caminho da pasta bin do Poppler (necessário para o pdf2image no Windows)
POPPLER_PATH = r'C:\poppler-24.02.0\Library\bin' # <--- AJUSTE ESSE CAMINHO CONFORME SUA INSTALAÇÃO

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Fiscal AI - OCR", page_icon="👁️", layout="wide")

st.title("👁️ Classificador Fiscal com OCR (Leitura de Scans)")
st.markdown("""
Este aplicativo lê PDFs de texto e **documentos escaneados**. 
Ele classifica automaticamente entre **PASEP**, **Previdenciário** ou **Outros**.
""")

# --- FUNÇÃO DE EXTRAÇÃO COM FALLBACK PARA OCR ---
def extrair_dados_hibrido(file_bytes, file_name):
    texto_completo = ""
    usou_ocr = False
    
    # 1. Tentativa Rápida (pdfplumber) - para PDFs digitais
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages[:3]: # Lê as 3 primeiras páginas
            extracted = page.extract_text()
            if extracted:
                texto_completo += extracted + "\n"
    
    # 2. Verificação: Se extraiu pouco texto, provavelmente é imagem/scan
    if len(texto_completo) < 50:
        usou_ocr = True
        try:
            # Converte PDF para imagens (apenas as 3 primeiras páginas para economizar tempo)
            images = convert_from_bytes(file_bytes, first_page=1, last_page=3, poppler_path=POPPLER_PATH)
            
            for img in images:
                # Aplica OCR na imagem (lang='por' para português)
                texto_ocr = pytesseract.image_to_string(img, lang='por')
                texto_completo += texto_ocr + "\n"
        except Exception as e:
            st.error(f"Erro no OCR para {file_name}. Verifique se o Poppler está instalado corretamente.\nErro: {e}")
            return None

    # --- LÓGICA DE CLASSIFICAÇÃO (A mesma do anterior) ---
    
    # Busca Processo
    match_proc = re.search(r'(?:Parcelamento|Processo|N[ºo°] do Parcelamento)[:\s\.]+([\d\.\/-]+)', texto_completo, re.IGNORECASE)
    processo = match_proc.group(1).strip() if match_proc else "Não identificado"
    
    # Busca Modalidade
    modalidade = "Desconhecida"
    if "Simplificado" in texto_completo or "OPP" in texto_completo:
        modalidade = "Simplificado (OPP)"
    elif "13.485" in texto_completo:
        modalidade = "Lei 13.485/17"
    elif "SIPADE" in texto_completo or "Ordinário" in texto_completo:
        modalidade = "Ordinário/Especial"
    
    # Busca Saldo (Regex aprimorado para OCR que pode confundir pontos/vírgulas)
    saldo = 0.0
    # Procura valores monetários permitindo erros comuns de OCR (espaços no meio do numero)
    padrao_valor = r'R\$\s?([\d\.\s]+,\d{2})'
    
    match_saldo = re.search(r'(?:Saldo devedor|Dívida consolidada|Valor Consolidado).*?'+padrao_valor, texto_completo, re.IGNORECASE | re.DOTALL)
    
    if match_saldo:
        valor_str = match_saldo.group(1).replace('.', '').replace(' ', '').replace(',', '.')
        try:
            saldo = float(valor_str)
        except:
            saldo = 0.0

    # Classificação
    classificacao = "A Verificar"
    
    # OCR as vezes lê "3703" como "37O3" ou "8703". Regex flexível ajuda.
    if re.search(r'3703|37O3|PASEP', texto_completo, re.IGNORECASE):
        classificacao = "PASEP"
    elif any(cod in texto_completo for cod in ["1082", "1138", "1646"]):
        classificacao = "Previdenciário (Patronal/Segurado)"
    elif "Previdenciário" in texto_completo and "13.485" in texto_completo:
        classificacao = "Previdenciário Especial"
    elif "Previdenciário" in texto_completo:
        classificacao = "Previdenciário"

    return {
        "Nome Arquivo": file_name,
        "Processo": processo,
        "Modalidade": modalidade,
        "Classificação": classificacao,
        "Saldo Devedor (R$)": saldo,
        "Método": "OCR (Scan)" if usou_ocr else "Texto Digital"
    }

# --- INTERFACE ---
uploaded_files = st.file_uploader(
    "Arraste PDFs (Digitais ou Scaneados)", 
    type="pdf", 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("🚀 Processar com IA/OCR"):
        dados_extraidos = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, file in enumerate(uploaded_files):
            status_text.text(f"Lendo arquivo {i+1}/{len(uploaded_files)}: {file.name}...")
            
            # Lê bytes para passar para as duas funções
            file_bytes = file.getvalue()
            
            try:
                info = extrair_dados_hibrido(file_bytes, file.name)
                if info:
                    dados_extraidos.append(info)
            except Exception as e:
                st.error(f"Falha crítica em {file.name}: {e}")
                
            progress_bar.progress((i + 1) / len(uploaded_files))
        
        status_text.text("Processamento concluído!")
        
        if dados_extraidos:
            df = pd.DataFrame(dados_extraidos)
            
            # Métricas
            total_divida = df["Saldo Devedor (R$)"].sum()
            col1, col2 = st.columns(2)
            col1.metric("Total Identificado", f"R$ {total_divida:,.2f}")
            col2.metric("Arquivos Lidos", len(df))
            
            # Tabela
            st.dataframe(
                df.style.format({"Saldo Devedor (R$)": "R$ {:,.2f}"}),
                use_container_width=True
            )
            
            # Download
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Consolidado')
            
            st.download_button(
                "📥 Baixar Excel",
                data=buffer.getvalue(),
                file_name="Relatorio_OCR_Fiscal.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
