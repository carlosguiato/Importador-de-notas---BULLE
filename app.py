import io
import numpy as np
import pandas as pd
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Conversores Domínio", page_icon="⚙️", layout="centered"
)

# Seletor na Barra Lateral para escolher a ferramenta
st.sidebar.title("🎛️ Menu de Conversão")
ferramenta_selecionada = st.sidebar.selectbox(
    "Escolha a ferramenta:",
    ["📄 Conversor de Notas de Entrada", "🏦 Conversor de Extrato Bancário"],
)

st.markdown("---")

# ==========================================
# FERRAMENTA 1: CONVERSOR DE NOTAS DE ENTRADA
# ==========================================
if ferramenta_selecionada == "📄 Conversor de Notas de Entrada":
  st.title("📄 Conversor de Notas de Entrada para o Domínio Web")
  st.write(
      "Faça o upload do relatório de notas de entrada para gerar o arquivo TXT"
      " formatado corretamente."
  )

  uploaded_file_notas = st.file_uploader(
      "Selecione a planilha de notas (.xlsx, .xls)",
      type=["xlsx", "xls"],
      key="upload_notas",
  )

  if uploaded_file_notas is not None:
    try:
      df_raw = pd.read_excel(uploaded_file_notas, header=None)

      data_rows = []
      for idx, row in df_raw.iterrows():
        if idx >= 7 and row[0] is not None and pd.notna(row[0]):
          data_rows.append({
              "Nota": row[0],
              "Data": row[6],
              "Fornecedor": row[17],
              "Total": row[32],
          })

      df_notas = pd.DataFrame(data_rows)

      if df_notas.empty:
        st.error(
            "Não foi possível identificar os lançamentos de notas na"
            " planilha."
        )
      else:
        with st.expander("🔍 Ver prévia das notas extraídas"):
          st.dataframe(df_notas.head(10))

        st.markdown("---")
        st.subheader("⚙️ Configuração das Contas no Domínio")

        col1, col2 = st.columns(2)
        with col1:
          conta_debito_padrao = st.text_input(
              "**Código da transitória**:", value="", key="deb_nota"
          )
        with col2:
          conta_credito_padrao = st.text_input(
              "**Código da conta de fornecedores**:", value="", key="cred_nota"
          )

        # Regras De-Para Notas
        st.markdown("---")
        regras_notas = []
        with st.expander(
            "➕ Adicionar Regras Personalizadas (De-Para) [Opcional]"
        ):
          if "num_regras_notas" not in st.session_state:
            st.session_state.num_regras_notas = 1

          cb1, cb2 = st.columns([1, 1])
          with cb1:
            if st.button("➕ Adicionar nova regra", key="btn_add_nota"):
              st.session_state.num_regras_notas += 1
          with cb2:
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
                  "Se o fornecedor/histórico contiver:",
                  key=f"termo_n_{i}",
                  placeholder="Ex: Auto Posto",
              )
            with rc2:
              qual_conta = st.selectbox(
                  "Substituir qual conta?",
                  ["Débito", "Crédito", "Ambos"],
                  key=f"alvo_n_{i}",
              )
            with rc3:
              nova_conta = st.text_input(
                  "Usar a conta:", key=f"conta_n_{i}", placeholder="Ex: 120"
              )

            if termo and nova_conta:
              regras_notas.append({
                  "termo": termo.strip().lower(),
                  "alvo": qual_conta,
                  "conta": nova_conta.strip(),
              })
            st.markdown("")

        st.markdown("---")

        if st.button(
            "🚀 Processar e Gerar TXT de Notas",
            type="primary",
            key="btn_proc_nota",
        ):
          if not conta_debito_padrao or not conta_credito_padrao:
            st.error("Por favor, preencha os códigos padrão antes de continuar.")
          else:

            def limpar_valor_n(val):
              if pd.isna(val):
                return 0.0
              if isinstance(val, (int, float)):
                return float(val)
              try:
                return float(
                    str(val).strip().replace(".", "").replace(",", ".")
                )
              except:
                return 0.0

            df_notas["VALOR_NUM"] = df_notas["Total"].apply(limpar_valor_n).abs()

            def limpar_texto_n(val):
              if pd.isna(val) or str(val).strip().lower() in [
                  "nan",
                  "none",
                  "nat",
                  "",
              ]:
                return ""
              return str(val).strip()

            df_notas["Historico"] = (
                "NF "
                + df_notas["Nota"].apply(limpar_texto_n)
                + " - "
                + df_notas["Fornecedor"].apply(limpar_texto_n)
            )

            def def_deb(row):
              h_low = str(row["Historico"]).lower()
              c = conta_debito_padrao
              for r in regras_notas:
                if r["termo"] in h_low and r["alvo"] in ["Débito", "Ambos"]:
                  c = r["conta"]
              return c

            def def_cred(row):
              h_low = str(row["Historico"]).lower()
              c = conta_credito_padrao
              for r in regras_notas:
                if r["termo"] in h_low and r["alvo"] in ["Crédito", "Ambos"]:
                  c = r["conta"]
              return c

            df_notas["Conta Debito"] = df_notas.apply(def_deb, axis=1)
            df_notas["Conta Credito"] = df_notas.apply(def_cred, axis=1)

            df_final_n = pd.DataFrame({
                "Data": pd.to_datetime(
                    df_notas["Data"], dayfirst=True, errors="coerce"
                )
                .dt.strftime("%d/%m/%Y"),
                "Conta Debito": df_notas["Conta Debito"],
                "Conta Credito": df_notas["Conta Credito"],
                "Valor": df_notas["VALOR_NUM"],
                "Historico": df_notas["Historico"],
            }).dropna(subset=["Data"])

            linhas_txt_n = []
            for _, row in df_final_n.iterrows():
              v_fmt = f"{row['Valor']:.2f}".replace(".", ",")
              linhas_txt_n.append(
                  f"{row['Data']};{row['Conta Debito']};{row['Conta Credito']};{v_fmt};{row['Historico']}"
              )

            txt_data_n = "\n".join(linhas_txt_n)

            st.success(
                f"✨ Arquivo convertido com sucesso! ({len(df_final_n)} notas"
                " processadas)"
            )

            with st.expander("👀 Visualizar prévia dos lançamentos gerados"):
              st.dataframe(df_final_n.head(15))

            st.download_button(
                label="📥 Baixar Arquivo TXT de Notas para o Domínio",
                data=txt_data_n.encode("cp1252", errors="replace"),
                file_name="notas_entrada_dominio.txt",
                mime="text/plain",
            )
    except Exception as e:
      st.error(f"Ocorreu um erro ao processar o arquivo de notas: {e}")


# ==========================================
# FERRAMENTA 2: CONVERSOR DE EXTRATO BANCÁRIO
# ==========================================
elif ferramenta_selecionada == "🏦 Conversor de Extrato Bancário":
  st.title("🏦 Conversor de Extrato Bancário para o Domínio Web")
  st.write(
      "Faça o upload do relatório de extrato bancário para gerar o arquivo TXT"
      " formatado corretamente."
  )

  uploaded_file_ext = st.file_uploader(
      "Selecione a planilha de extrato (.xlsx, .xls)",
      type=["xlsx", "xls"],
      key="upload_extrato",
  )

  if uploaded_file_ext is not None:
    try:
      df_raw_ext = pd.read_excel(uploaded_file_ext, header=None)

      data_rows_ext = []
      for idx, row in df_raw_ext.iterrows():
        # Verifica se a linha tem dados válidos (ignorando cabeçalhos e linhas vazias)
        if idx >= 2 and row.shape[0] > 12:
          comp_val = row[0]
          if pd.notna(comp_val):
            data_rows_ext.append({
                "Compensado": comp_val,
                "Documento": row[1] if row.shape[1] > 1 else "",
                "Historico": row[4] if row.shape[1] > 4 else "",
                "Credito": row[9] if row.shape[1] > 9 else 0,
                "Debito": row[12] if row.shape[1] > 12 else 0,
            })

      df_ext = pd.DataFrame(data_rows_ext)

      if df_ext.empty:
        st.error(
            "Não foi possível identificar os lançamentos no extrato. Verifique"
            " o formato."
        )
      else:
        with st.expander("🔍 Ver prévia dos dados extraídos"):
          st.dataframe(df_ext.head(10))

        st.markdown("---")
        st.subheader("⚙️ Configuração das Contas no Domínio")

        ce1, ce2, ce3 = st.columns(3)
        with ce1:
          conta_banco = st.text_input(
              "**Código da Conta do Banco**:", value="", key="banco_ext"
          )
        with ce2:
          transitoria_fornecedores = st.text_input(
              "**Transitória Fornecedores (Saídas)**:",
              value="",
              key="forn_ext",
          )
        with ce3:
          transitoria_clientes = st.text_input(
              "**Transitória Clientes (Entradas)**:", value="", key="cli_ext"
          )

        # Regras De-Para Extrato
        st.markdown("---")
        regras_ext = []
        with st.expander(
            "➕ Adicionar Regras Personalizadas (De-Para) [Opcional]"
        ):
          if "num_regras_ext" not in st.session_state:
            st.session_state.num_regras_ext = 1

          cx1, cx2 = st.columns([1, 1])
          with cx1:
            if st.button("➕ Adicionar nova regra", key="btn_add_ext"):
              st.session_state.num_regras_ext += 1
          with cx2:
            if (
                st.button("🗑️ Limpar regras", key="btn_clr_ext")
                and st.session_state.num_regras_ext > 1
            ):
              st.session_state.num_regras_ext = 1

          for i in range(st.session_state.num_regras_ext):
            st.markdown(f"**Regra {i+1}**")
            rx1, rx2 = st.columns([2, 1])
            with rx1:
              termo_e = st.text_input(
                  "Se o histórico contiver:",
                  key=f"termo_e_{i}",
                  placeholder="Ex: Tarifas",
              )
            with rx2:
              nova_conta_e = st.text_input(
                  "Usar a conta:", key=f"conta_e_{i}", placeholder="Ex: 250"
              )

            if termo_e and nova_conta_e:
              regras_ext.append({
                  "termo": termo_e.strip().lower(),
                  "conta": nova_conta_e.strip(),
              })
            st.markdown("")

        st.markdown("---")

        if st.button(
            "🚀 Processar e Gerar TXT do Extrato",
            type="primary",
            key="btn_proc_ext",
        ):
          if (
              not conta_banco
              or not transitoria_fornecedores
              or not transitoria_clientes
          ):
            st.error("Por favor, preencha todos os códigos de contas padrão.")
          else:

            def limpar_valor_e(val):
              if pd.isna(val):
                return 0.0
              if isinstance(val, (int, float)):
                return float(val)
              try:
                return float(
                    str(val).strip().replace(".", "").replace(",", ".")
                )
              except:
                return 0.0

            df_ext["VALOR_CREDITO"] = df_ext["Credito"].apply(limpar_valor_e)
            df_ext["VALOR_DEBITO"] = df_ext["Debito"].apply(limpar_valor_e)

            def limpar_texto_e(val):
              if pd.isna(val) or str(val).strip().lower() in [
                  "nan",
                  "none",
                  "nat",
                  "",
              ]:
                return ""
              return str(val).strip().replace("\n", " ").replace("\r", " ")

            df_ext["Hist_Limpo"] = df_ext["Historico"].apply(limpar_texto_e)
            df_ext["Doc_Limpo"] = df_ext["Documento"].apply(limpar_texto_e)

            def montar_historico(row):
              h = row["Hist_Limpo"]
              d = row["Doc_Limpo"]
              if h and d:
                return f"{h} - {d}"
              elif h:
                return h
              elif d:
                return d
              return "LANCAMENTO BANCARIO"

            df_ext["Historico_Final"] = df_ext.apply(montar_historico, axis=1)

            linhas_processadas = []
            for _, row in df_ext.iterrows():
              cred = row["VALOR_CREDITO"]
              deb = row["VALOR_DEBITO"]

              if cred > 0 and deb == 0:
                valor = cred
                conta_cred = conta_banco
                conta_deb = transitoria_clientes
                tipo_movimento = "entrada"
              elif deb > 0 and cred == 0:
                valor = deb
                conta_deb = conta_banco
                conta_cred = transitoria_fornecedores
                tipo_movimento = "saida"
              else:
                continue

              hist_lower = row["Historico_Final"].lower()
              for r in regras_ext:
                if r["termo"] in hist_lower:
                  if tipo_movimento == "saida":
                    conta_cred = r["conta"]
                  else:
                    conta_deb = r["conta"]

              data_comp = (
                  pd.to_datetime(row["Compensado"], errors="coerce")
                  .strftime("%d/%m/%Y")
                  if pd.notna(row["Compensado"])
                  else ""
              )

              if not data_comp:
                continue

              v_fmt = f"{valor:.2f}".replace(".", ",")
              linhas_processadas.append(
                  f"{data_comp};{conta_deb};{conta_cred};{v_fmt};{row['Historico_Final']}"
              )

            txt_data_e = "\n".join(linhas_processadas)

            st.success(
                f"✨ Extrato convertido com sucesso! ({len(linhas_processadas)}"
                " lançamentos processados)"
            )

            df_preview_e = pd.DataFrame(
                [l.split(";") for l in linhas_processadas],
                columns=[
                    "Compensado",
                    "Conta Débito",
                    "Conta Crédito",
                    "Valor",
                    "Histórico",
                ],
            )
            with st.expander("👀 Visualizar prévia dos lançamentos gerados"):
              st.dataframe(df_preview_e.head(15))

            st.download_button(
                label="📥 Baixar Arquivo TXT de Extrato para o Domínio",
                data=txt_data_e.encode("cp1252", errors="replace"),
                file_name="extrato_bancario_dominio.txt",
                mime="text/plain",
            )
    except Exception as e:
      st.error(f"Ocorreu um erro ao processar o arquivo de extrato: {e}")