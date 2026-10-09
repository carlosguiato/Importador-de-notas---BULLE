import io
import re
import numpy as np
import pandas as pd
from pypdf import PdfReader
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Conversores Domínio", page_icon="⚙️", layout="centered"
)

# Seletor na Barra Lateral para escolher a ferramenta
st.sidebar.title("🎛️ Menu de Conversão")
ferramenta_selecionada = st.sidebar.selectbox(
    "Escolha a ferramenta:",
    [
        "📄 Conversor de Notas de Entrada",
        "📤 Conversor de Notas de Saída",
        "🏦 Conversor de Extrato Bancário",
    ],
)

st.markdown("---")

# ==========================================
# FERRAMENTA 1: CONVERSOR DE NOTAS DE ENTRADA
# ==========================================
if ferramenta_selecionada == "📄 Conversor de Notas de Entrada":
  st.title("📄 Conversor de Notas de Entrada para o Domínio Web")
  st.write(
      "Faça o upload do relatório de notas de entrada (.xlsx) para gerar o"
      " arquivo TXT formatado."
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
        if idx >= 7 and row.iloc[0] is not None and pd.notna(row.iloc[0]):
          data_rows.append({
              "Nota": row.iloc[0],
              "Data": row.iloc[6],
              "Fornecedor": row.iloc[17],
              "Total": row.iloc[32],
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
# FERRAMENTA 2: CONVERSOR DE NOTAS DE SAÍDA (PDF) - CORRIGIDO
# ==========================================
elif ferramenta_selecionada == "📤 Conversor de Notas de Saída":
  st.title("📤 Conversor de Notas de Saída para o Domínio Web")
  st.write(
      "Faça o upload do relatório de notas de saída em **PDF** para gerar os"
      " arquivos TXT intermediário e final."
  )

  uploaded_file_saidas = st.file_uploader(
      "Selecione o arquivo de notas de saída (.pdf)",
      type=["pdf"],
      key="upload_saidas",
  )

  if uploaded_file_saidas is not None:
    try:
      reader = PdfReader(uploaded_file_saidas)
      layout_text = ""
      for page in reader.pages:
        layout_text += page.extract_text(extraction_mode="layout") + "\n"

      lines = layout_text.split("\n")
      inv_indices = []
      for idx, l in enumerate(lines):
        if re.search(r"\b(NFe|NFE|NF)\s+\d+", l):
          inv_indices.append(idx)

      parsed_sales = []
      for i in range(len(inv_indices)):
        start = inv_indices[i]
        end = inv_indices[i + 1] if i + 1 < len(inv_indices) else len(lines)
        block = lines[start:end]

        header_line = block[0]
        match_h = re.search(
            r"(?:NFe|NFE|NF)\s*([0-9A-Z]+)\s+(\d{2}/\d{2}/\d{4})\s+([A-Z\s]+?)(?:\s{2,}|PR)",
            header_line,
        )
        if match_h:
          nota = match_h.group(1).strip()
          data = match_h.group(2).strip()
          cliente = match_h.group(3).strip()
        else:
          nota = ""
          data = ""
          cliente = "CLIENTE"

        # Captura precisa de todos os valores monetários na linha do cabeçalho da NF (incluindo 5+ dígitos)
        vals = re.findall(r"\b\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}\b", header_line)
        total_str = vals[-1] if vals else "0,00"

        produtos_texto = " ".join(block).upper()
        if "TRIGO" in produtos_texto or "TRIGUILHO" in produtos_texto:
          commodity = "TRIGO"
        elif "MILHO" in produtos_texto or "QUIRERA" in produtos_texto:
          commodity = "MILHO"
        elif "SOJA" in produtos_texto:
          commodity = "SOJA"
        else:
          commodity = "MILHO"

        parsed_sales.append({
            "nota": nota,
            "data": data,
            "cliente_commodity": f"{cliente} - {commodity}",
            "total_str": total_str,
        })

      df_saidas = pd.DataFrame(parsed_sales)

      if df_saidas.empty:
        st.warning(
            "Não foi possível extrair as notas de saída do PDF. Verifique o"
            " layout."
        )
      else:
        with st.expander("🔍 Ver prévia das notas de saída extraídas"):
          st.dataframe(df_saidas.head(10))

        st.markdown("---")
        st.subheader("⚙️ Configuração das Contas de Crédito por Cultura")

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
          conta_cred_trigo = st.text_input(
              "**Conta Crédito (Trigo/Triguilho)**:", value="", key="cred_trigo"
          )
        with sc2:
          conta_cred_milho = st.text_input(
              "**Conta Crédito (Milho/Quirera)**:", value="", key="cred_milho"
          )
        with sc3:
          conta_cred_soja = st.text_input(
              "**Conta Crédito (Soja)**:", value="", key="cred_soja"
          )

        st.markdown("---")

        if st.button(
            "🚀 Processar e Gerar TXT de Saídas",
            type="primary",
            key="btn_proc_saida",
        ):
          if not conta_cred_trigo or not conta_cred_milho or not conta_cred_soja:
            st.error("Por favor, preencha todas as contas de crédito.")
          else:
            linhas_interm = []
            linhas_dominio = []

            for _, row in df_saidas.iterrows():
              data = row["data"]
              hist = row["cliente_commodity"]
              val_clean = row["total_str"].replace(".", "").replace(",", ".")
              try:
                val_num = float(val_clean)
              except:
                val_num = 0.0

              # TXT intermediário: Data ; Valor ; Histórico
              val_interm_fmt = f"{val_num:.2f}".replace(".", ",")
              linhas_interm.append(f"{data};{val_interm_fmt};{hist}")

              # Determina conta crédito
              hist_upper = hist.upper()
              if "TRIGO" in hist_upper or "TRIGUILHO" in hist_upper:
                c_cred = conta_cred_trigo
              elif "SOJA" in hist_upper:
                c_cred = conta_cred_soja
              else:
                c_cred = conta_cred_milho

              # TXT Domínio: data;contadebito;contacredito;valor;historico (débito fixo 14)
              val_dom_fmt = f"{val_num:.2f}".replace(".", ",")
              linhas_dominio.append(f"{data};14;{c_cred};{val_dom_fmt};{hist}")

            txt_interm = "\n".join(linhas_interm)
            txt_dominio = "\n".join(linhas_dominio)

            st.success(
                f"✨ Notas de saída processadas com sucesso! ({len(df_saidas)}"
                " notas)"
            )

            col_down1, col_down2 = st.columns(2)
            with col_down1:
              st.download_button(
                  label="📥 Baixar TXT Intermediário (Data;Valor;Histórico)",
                  data=txt_interm.encode("cp1252", errors="replace"),
                  file_name="saidas_intermediario.txt",
                  mime="text/plain",
              )
            with col_down2:
              st.download_button(
                  label="📥 Baixar TXT para o Domínio Web",
                  data=txt_dominio.encode("cp1252", errors="replace"),
                  file_name="notas_saida_dominio.txt",
                  mime="text/plain",
              )
    except Exception as e:
      st.error(f"Ocorreu um erro ao processar o PDF de saídas: {e}")


# ==========================================
# FERRAMENTA 3: CONVERSOR DE EXTRATO BANCÁRIO
# ==========================================
elif ferramenta_selecionada == "🏦 Conversor de Extrato Bancário":
  st.title("🏦 Conversor de Extrato Bancário em PDF para o Domínio Web")
  st.write(
      "Faça o upload do extrato bancário em **PDF** para gerar o arquivo TXT"
      " formatado."
  )

  uploaded_file_ext = st.file_uploader(
      "Selecione o arquivo de extrato (.pdf)", type=["pdf"], key="upload_extrato"
  )

  if uploaded_file_ext is not None:
    try:
      reader = PdfReader(uploaded_file_ext)
      layout_text = ""
      for page in reader.pages:
        layout_text += page.extract_text(extraction_mode="layout") + "\n"

      lines = layout_text.split("\n")
      valid_rows = []

      for line in lines:
        if "898996-4" in line:
          dates = re.findall(r"\d{2}/\d{2}/\d{4}", line)
          vals = re.findall(r"\d+[\.,]\d{2}", line)

          if not dates or not vals:
            continue

          data_trans = dates[0]
          val_str = vals[-1].replace(".", "").replace(",", ".")
          try:
            val_num = float(val_str)
          except:
            continue

          cleaned = line.replace("898996-4", "")
          for d in dates:
            cleaned = cleaned.replace(d, "")
          for v in vals:
            cleaned = cleaned.replace(v, "")

          cleaned = re.sub(r"\s+\d{2,4}\s*$", "", cleaned)
          cleaned = re.sub(
              r"\s+Débito:\s*\d+.*$", "", cleaned, flags=re.IGNORECASE
          )
          hist_clean = re.sub(r"\s+", " ", cleaned).strip(" |-/")

          if not hist_clean:
            hist_clean = "LANÇAMENTO BANCÁRIO"

          if (
              "Pagar:" in line
              or "Débito:" in line
              or "CUSTO PIX" in line
              or "MANUTENÇÃO" in line
              or "ARRENDAMENTO" in line
              or "HONORARIOS" in line
              or "FGTS" in line
              or "MAXNET" in line
              or "ACORDO" in line
          ):
            valid_rows.append({
                "Data": data_trans,
                "Historico": hist_clean,
                "Credito": 0.0,
                "Debito": val_num,
            })
          else:
            valid_rows.append({
                "Data": data_trans,
                "Historico": hist_clean,
                "Credito": val_num,
                "Debito": 0.0,
            })

      df_ext = pd.DataFrame(valid_rows)

      if df_ext.empty:
        st.warning(
            "Não foi possível extrair os lançamentos. Verifique se o PDF"
            " corresponde ao modelo esperado."
        )
      else:
        st.success(
            f"✨ PDF lido com sucesso! Total de lançamentos extraídos:"
            f" {len(df_ext)}"
        )
        with st.expander("🔍 Ver prévia dos dados extraídos do PDF"):
          st.dataframe(df_ext.head(15))

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
            linhas_processadas = []
            for _, row in df_ext.iterrows():
              cred = row["Credito"]
              deb = row["Debito"]

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

              hist_final = str(row["Historico"]).strip()
              hist_lower = hist_final.lower()

              for r in regras_ext:
                if r["termo"] in hist_lower:
                  if tipo_movimento == "saida":
                    conta_cred = r["conta"]
                  else:
                    conta_deb = r["conta"]

              data_trans = row["Data"]
              v_fmt = f"{valor:.2f}".replace(".", ",")

              linha = f"{data_trans};{conta_deb};{conta_cred};{v_fmt};{hist_final}"
              linhas_processadas.append(linha)

            txt_data_e = "\n".join(linhas_processadas)

            st.success(
                f"✨ Extrato convertido com sucesso! ({len(linhas_processadas)}"
                " lançamentos processados)"
            )

            df_preview_e = pd.DataFrame(
                [l.split(";") for l in linhas_processadas],
                columns=[
                    "Data",
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
      st.error(f"Ocorreu um erro ao processar o arquivo PDF: {e}")