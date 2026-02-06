import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Classificador Fiscal (Rápido)", page_icon="⚡", layout="wide")

st.title("⚡ Classificador de Parcelamentos (RFB/PGFN)")
st.markdown("### Versão Digital: Lê extratos do e-CAC e SIEFPAR automaticamente.")

# --- FUNÇÃO DE EXTRAÇÃO (TEXTO DIGITAL) ---
def extrair_dados_rapido(file):
    texto_completo = ""
    # Abre o PDF na memória
    with pdfplumber.open(file) as pdf:
        # Lê até as 5 primeiras páginas (suficiente para achar o cabeçalho e resumo)
        for page in pdf.pages[:5]:
            texto_completo += page.extract_text() or ""
    
    # --- 1. Extração do Número do Processo ---
    # Tenta vários padrões: "Parcelamento:", "Processo:", "Nº"
    match_proc = re.search(r'(?:Parcelamento|Processo|N[ºo°] do Parcelamento)[:\s\.]+([\d\.\/-]+)', texto_completo, re.IGNORECASE)
    processo = match_proc.group(1).strip() if match_proc else "Não identificado"
    
    # --- 2. Extração da Modalidade ---
    modalidade = "Outros"
    if "Simplificado" in texto_completo or "OPP" in texto_completo:
        modalidade = "Simplificado (OPP)"
    elif "13.485" in texto_completo:
        modalidade = "Lei 13.485/17"
    elif "SIPADE" in texto_completo or "Ordinário" in texto_completo:
        modalidade = "Ordinário/Especial"
    elif "PGFN" in texto_completo:
        modalidade = "PGFN (Dívida Ativa)"
    
    # --- 3. Extração do Valor (Saldo Devedor) ---
    saldo = 0.0
    # Procura "Saldo Devedor" ou "Dívida Consolidada" seguido de valor monetário
    # O Regex pega formatos como "1.234,56" ou "234,56"
    padrao_valor = r'R\$\s?([\d\.]+,\d{2})'
    
    # Prioridade 1: Saldo Devedor explícito (comum em extratos novos)
    match_saldo = re.search(r'(?:Saldo devedor|Saldo Devedor Total|Saldo da dívida).*?' + padrao_valor, texto_completo, re.IGNORECASE | re.DOTALL)
    
    # Prioridade 2: Dívida Consolidada (caso seja adesão recente)
    if not match_saldo:
        match_saldo = re.search(r'(?:Dívida consolidada).*?' + padrao_valor, texto_completo, re.IGNORECASE | re.DOTALL)
        
    if match_saldo:
        # Limpa o valor (tira pontos de milhar e troca vírgula por ponto decimal)
        valor_str = match_saldo.group(1).replace('.', '').replace(',', '.')
        try:
            saldo = float(valor_str)
        except:
            saldo = 0.0

    # --- 4. Classificação Inteligente ---
    classificacao = "A Verificar"
    
    # Regra 1: PASEP (Código 3703 ou menção explícita)
    if "3703" in texto_completo or "PASEP" in texto_completo:
        classificacao = "PASEP"
    
    # Regra 2: Previdenciário (Códigos INSS Patronal/Segurado)
    elif any(cod in texto_completo for cod in ["1082", "1138", "1646", "CPSS"]):
        classificacao = "Previdenciário"
    
    # Regra 3: Se diz previdenciário e é a Lei 13.485
    elif "Previdenciário" in texto_completo and modalidade == "Lei 13.485/17":
        classificacao = "Previdenciário Especial"
        
    # Regra 4: Fallback se tiver a palavra "Previdenciário" mas sem códigos
    elif "Previdenciário" in texto_completo:
        classificacao = "Previdenciário"

    return {
        "Nome Arquivo": file.name,
        "Processo": processo,
        "Modalidade": modalidade,
        "Classificação": classificacao,
        "Saldo Devedor (R$)": saldo
    }

# --- INTERFACE DE UPLOAD ---
uploaded_files = st.file_uploader(
    "Arraste seus PDFs aqui (Pode selecionar vários de uma vez)", 
    type="pdf", 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("🚀 Processar Arquivos"):
        with st.spinner('Lendo documentos...'):
            dados = []
            progresso = st.progress(0)
            
            for i, file in enumerate(uploaded_files):
                try:
                    # Processa cada arquivo
                    info = extrair_dados_rapido(file)
                    dados.append(info)
                except Exception as e:
                    dados.append({"Nome Arquivo": file.name, "Processo": "Erro leitura", "Saldo Devedor (R$)": 0.0})
                
                # Atualiza barra
                progresso.progress((i + 1) / len(uploaded_files))
            
            # Gera Tabela
            df = pd.DataFrame(dados)
            
            # --- MOSTRAR RESULTADOS ---
            st.success("✅ Processamento concluído!")
            
            # Métricas no Topo
            total = df["Saldo Devedor (R$)"].sum()
            col1, col2, col3 = st.columns(3)
            col1.metric("Arquivos", len(df))
            col2.metric("Total Dívida", f"R$ {total:,.2f}")
            col3.metric("Maior Débito", f"R$ {df['Saldo Devedor (R$)'].max():,.2f}")
            
            # Tabela Detalhada
            st.dataframe(
                df.style.format({"Saldo Devedor (R$)": "R$ {:,.2f}"}),
                use_container_width=True
            )
            
            # Botão Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Extratos')
            
            st.download_button(
                label="📥 Baixar Planilha Excel",
                data=buffer.getvalue(),
                file_name="Relatorio_Parcelamentos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
