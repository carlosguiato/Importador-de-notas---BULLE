import re
import io
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
      " formatado."
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
# FERRAMENTA 2: CONVERSOR DE EXTRATO BANCÁRIO (PDF)
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
      full_text = ""
      for page in reader.pages:
        full_text += page.extract_text() + "\n"

      # Extração inteligente das linhas do extrato em PDF
      # Lógica: Identifica linhas que possuem data no formato DD/MM/YYYY
      lines = full_text.split("\n")
      parsed_data = []

      # Expressão regular para encontrar datas
      date_pattern = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")

      # Vamos agrupar o texto por blocos ou varrer procurando padrões de lançamento
      # No formato do PDF do Fazenda Bulle, cada transação possui data, histórico e valores.
      # Vamos usar uma heurística robusta baseada em linhas de texto extraídas.

      # Como o extrato em PDF do seu banco tem uma estrutura específica, vamos processar as linhas válidas:
      # Uma linha de lançamento costuma conter uma data e valores numéricos com vírgula.

      # Uma abordagem limpa para este PDF específico:
      # Vamos iterar pelas linhas procurando datas e montando os registros.
      current_date = None
      current_hist = None
      current_cred = 0.0
      current_deb = 0.0

      # Alternativamente, podemos usar extração baseada em blocos de linhas consecutivas.
      # Vamos estruturar um parser adaptado para o PDF enviado:
      valid_rows = []

      # Limpeza prévia de linhas de cabeçalho/rodapé indesejadas
      cleaned_lines = []
      for line in lines:
        line_str = line.strip()
        if (
            not line_str
            or "Lançamentos bancários" in line_str
            or "Página" in line_str
            or "FAZENDA BULLE" in line_str
            or "sexta-feira" in line_str
            or "Conta" in line_str
            or "Documento" in line_str
            or "Histórico" in line_str
            or "Total" in line_str
        ):
          continue
        cleaned_lines.append(line_str)

      # Processamento das transações
      i = 0
      while i < len(cleaned_lines):
        line = cleaned_lines[i]
        # Procura por uma data (ex: 01/09/2026)
        if date_pattern.match(line):
          data_trans = line
          # As próximas linhas geralmente contêm o histórico e os valores de crédito/débito
          hist_parts = []
          valores = []

          i += 1
          while i < len(cleaned_lines) and not date_pattern.match(
              cleaned_lines[i]
          ):
            nxt = cleaned_lines[i]
            # Verifica se a linha é um valor numérico (contém vírgula e dígitos)
            if re.match(r"^\d{1,3}(\.\d{3})*,\d{2}$|^\d+,\d{2}$", nxt.replace(" ", "")):
              valores.append(nxt)
            elif (
                not nxt.startswith("898996")
                and not nxt.isdigit()
                and len(nxt) > 2
            ):
              hist_parts.append(nxt)
            i += 1

          if hist_parts and valores:
            historico = " ".join(hist_parts)
            # O último valor ou o único valor geralmente define se é crédito ou débito conforme o layout
            # No extrato fornecido, os valores aparecem nas colunas de Crédito ou Débito.
            # Vamos tratar o valor numérico encontrado:
            val_str = valores[0].replace(".", "").replace(",", ".")
            try:
              val_num = float(val_str)
              # Determinamos se foi crédito ou débito com base na posição ou sinal/texto
              # Na dúvida, se contém "Pagar:" ou "Débito", é saída (Débito no banco)
              if (
                  "Pagar:" in historico
                  or "Débito:" in historico
                  or "CUSTO PIX" in historico
                  or "MANUTENÇÃO" in historico
              ):
                valid_rows.append({
                    "Data": data_trans,
                    "Historico": historico,
                    "Credito": 0.0,
                    "Debito": val_num,
                })
              else:
                valid_rows.append({
                    "Data": data_trans,
                    "Historico": historico,
                    "Credito": val_num,
                    "Debito": 0.0,
                })
            except:
              pass
          else:
            continue
        else:
          i += 1

      df_ext = pd.DataFrame(valid_rows)

      if df_ext.empty:
        st.warning(
            "Não foi possível extrair automaticamente pelo padrão estrito."
            " Verifique o formato do PDF."
        )
      else:
        with st.expander("🔍 Ver prévia dos dados extraídos do PDF"):
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
            linhas_processadas = []
            for _, row in df_ext.iterrows():
              cred = row["Credito"]
              deb = row["Debito"]

              # Lógica de Débito e Crédito conforme solicitado:
              # Crédito no banco = Entrada -> Conta Crédito = Banco, Conta Débito = Clientes
              # Débito no banco = Saída -> Conta Débito = Banco, Conta Crédito = Fornecedores
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

              # Regras De-Para
              for r in regras_ext:
                if r["termo"] in hist_lower:
                  if tipo_movimento == "saida":
                    conta_cred = r["conta"]
                  else:
                    conta_deb = r["conta"]

              data_trans = row["Data"]
              v_fmt = f"{valor:.2f}".replace(".", ",")

              # Ordem exigida: data;contadebito;contacredito;valor;historico
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