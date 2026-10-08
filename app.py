import io
import numpy as np
import pandas as pd
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Conversor de Notas - Domínio", page_icon="📄", layout="centered"
)

st.title("📄 Conversor de Notas de Entrada para o Domínio Web")
st.write(
    "Faça o upload do relatório de notas de entrada para gerar o arquivo TXT"
    " formatado corretamente."
)

# 1. Upload do arquivo na interface web
uploaded_file = st.file_uploader(
    "Selecione a planilha de notas (.xlsx, .xls)", type=["xlsx", "xls"]
)

if uploaded_file is not None:
  try:
    # Leitura crua do Excel para tratar a estrutura de relatório da planilha de notas
    df_raw = pd.read_excel(uploaded_file, header=None)

    # Varredura para extração das linhas de dados válidas
    data_rows = []
    for idx, row in df_raw.iterrows():
      if idx >= 7 and row[0] is not None and pd.notna(row[0]):
        data_rows.append({
            "Nota": row[0],
            "Data": row[6],
            "Fornecedor": row[17],
            "Total": row[32],
        })

    df = pd.DataFrame(data_rows)

    if df.empty:
      st.error(
          "Não foi possível identificar os lançamentos de notas na planilha."
          " Verifique o formato do arquivo."
      )
    else:
      with st.expander("🔍 Ver prévia das notas extraídas"):
        st.dataframe(df.head(10))

      st.markdown("---")
      st.subheader("⚙️ Configuração das Contas no Domínio")

      # Configuração das contas com os rótulos solicitados
      col1, col2 = st.columns(2)
      with col1:
        conta_debito_padrao = st.text_input(
            "**Código da transitória**:", value=""
        )
      with col2:
        conta_credito_padrao = st.text_input(
            "**Código da conta de fornecedores**:", value=""
        )

      # --- REGRAS PERSONALIZADAS (DE-PARA) ---
      st.markdown("---")
      regras_personalizadas = []
      with st.expander(
          "➕ Adicionar Regras Personalizadas (De-Para) [Opcional]"
      ):
        st.write(
            "Crie regras baseadas no nome do fornecedor ou número da nota."
            " Se o histórico corresponder, a conta padrão será substituída."
        )

        if "num_regras_notas" not in st.session_state:
          st.session_state.num_regras_notas = 1

        col_b1, col_b2 = st.columns([1, 1])
        with col_b1:
          if st.button("➕ Adicionar nova regra", key="btn_add_nota"):
            st.session_state.num_regras_notas += 1
        with col_b2:
          if (
              st.button("🗑️ Limpar regras", key="btn_clr_nota")
              and st.session_state.num_regras_notas > 1
          ):
            st.session_state.num_regras_notas = 1

        for i in range(st.session_state.num_regras_notas):
          st.markdown(f"**Regra {i+1}**")
          rc1, rc2, rc3 = st.columns([2, 1, 1])
          with rc1:
            termo = st.text_input(
                f"Se o fornecedor/histórico contiver:",
                key=f"termo_nota_{i}",
                placeholder="Ex: Auto Posto, Luan",
            )
          with rc2:
            qual_conta = st.selectbox(
                "Substituir qual conta?",
                ["Débito", "Crédito", "Ambos"],
                key=f"qual_conta_nota_{i}",
            )
          with rc3:
            nova_conta = st.text_input(
                f"Usar a conta:",
                key=f"conta_regra_nota_{i}",
                placeholder="Ex: 120",
            )

          if termo and nova_conta:
            regras_personalizadas.append({
                "termo": termo.strip().lower(),
                "alvo": qual_conta,
                "conta": nova_conta.strip(),
            })
          st.markdown("")

      st.markdown("---")

      # Botão para processar
      if st.button("🚀 Processar e Gerar TXT de Notas", type="primary"):
        if not conta_debito_padrao or not conta_credito_padrao:
          st.error(
              "Por favor, preencha os códigos padrão antes de continuar."
          )
        else:
          # Tratamento correto do Valor Total para garantir 2 casas decimais
          def limpar_valor(val):
            if pd.isna(val):
              return 0.0
            val_str = str(val).strip()
            # Se já for float/int do python
            if isinstance(val, (int, float)):
              return float(val)
            # Se vier como string formatada em pt-BR (ex: "3.500,00" ou "350,0")
            val_str = val_str.replace(".", "").replace(",", ".")
            try:
              return float(val_str)
            except:
              return 0.0

          df["VALOR_NUM"] = df["Total"].apply(limpar_valor).abs()

          # Formatação do Histórico: "NF (nota) - (fornecedor)"
          def limpar_texto(val):
            if pd.isna(val) or str(val).strip().lower() in [
                "nan",
                "none",
                "nat",
                "",
            ]:
              return ""
            return str(val).strip()

          df["Historico"] = (
              "NF "
              + df["Nota"].apply(limpar_texto)
              + " - "
              + df["Fornecedor"].apply(limpar_texto)
          )

          # Aplicação das contas padrão e regras De-Para
          def define_debito(row):
            hist_lower = str(row["Historico"]).lower()
            conta = conta_debito_padrao
            for regra in regras_personalizadas:
              if regra["termo"] in hist_lower and regra["alvo"] in [
                  "Débito",
                  "Ambos",
              ]:
                conta = regra["conta"]
            return conta

          def define_credito(row):
            hist_lower = str(row["Historico"]).lower()
            conta = conta_credito_padrao
            for regra in regras_personalizadas:
              if regra["termo"] in hist_lower and regra["alvo"] in [
                  "Crédito",
                  "Ambos",
              ]:
                conta = regra["conta"]
            return conta

          df["Conta Debito"] = df.apply(define_debito, axis=1)
          df["Conta Credito"] = df.apply(define_credito, axis=1)

          # Montagem do layout final
          df_final = pd.DataFrame({
              "Data": pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
              .dt.strftime("%d/%m/%Y"),
              "Conta Debito": df["Conta Debito"],
              "Conta Credito": df["Conta Credito"],
              "Valor": df["VALOR_NUM"],
              "Historico": df["Historico"],
          }).dropna(subset=["Data"])

          # Geração manual do texto para garantir separador ';' e vírgula com 2 casas decimais exatas
          linhas_txt = []
          for _, row in df_final.iterrows():
            valor_formatado = f"{row['Valor']:.2f}".replace(".", ",")
            linha = f"{row['Data']};{row['Conta Debito']};{row['Conta Credito']};{valor_formatado};{row['Historico']}"
            linhas_txt.append(linha)

          txt_data = "\n".join(linhas_txt)

          st.success(
              f"✨ Arquivo convertido com sucesso! ({len(df_final)} notas"
              " processadas)"
          )

          # Visualizar prévia
          with st.expander("👀 Visualizar prévia dos lançamentos gerados"):
            st.dataframe(df_final.head(15))

          # Botão de Download para formato .txt
          st.download_button(
              label="📥 Baixar Arquivo TXT de Notas para o Domínio",
              data=txt_data.encode("cp1252", errors="replace"),
              file_name="notas_entrada_dominio.txt",
              mime="text/plain",
          )

  except Exception as e:
    st.error(f"Ocorreu um erro ao processar o arquivo de notas: {e}")