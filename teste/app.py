import io
import numpy as np
import pandas as pd
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Conversor de Extrato - Domínio",
    page_icon="📊",
    layout="centered",
)

st.title("📊 Conversor de Extratos para o Domínio Web")
st.write(
    "Faça o upload da sua planilha de extrato bancário para gerar o arquivo CSV"
    " formatado corretamente."
)

# 1. Upload do arquivo na interface web
uploaded_file = st.file_uploader(
    "Selecione o arquivo Excel do extrato (.xlsx, .xls)", type=["xlsx", "xls"]
)

if uploaded_file is not None:
  try:
    # Leitura inicial do arquivo Excel
    df = pd.read_excel(uploaded_file, header=0, skiprows=[1])

    with st.expander("🔍 Ver colunas identificadas na planilha"):
      st.write(df.columns.tolist())

    # Descobre quais contas bancárias existem na coluna 'Conta bancária'
    contas_encontradas = []
    if "Conta bancária" in df.columns:
      contas_encontradas = df["Conta bancária"].dropna().unique()

    st.markdown("---")
    st.subheader("⚙️ Configuração das Contas no Domínio")

    # Mapeamento dinâmico dos bancos encontrados
    mapeamento_contas = {}
    if len(contas_encontradas) > 0:
      for conta in contas_encontradas:
        mapeamento_contas[conta] = st.text_input(
            f"Código da conta do banco **'{conta}'** no Domínio:", value=""
        )
    else:
      st.warning(
          "A coluna 'Conta bancária' não foi encontrada. Será usada a conta"
          " padrão '9'."
      )

    # Configuração das contas transitórias padrão
    col1, col2 = st.columns(2)
    with col1:
      conta_fornecedor = st.text_input(
          "Contra conta padrão para **SAÍDAS** (Fornecedor / < 0):", value=""
      )
    with col2:
      conta_cliente = st.text_input(
          "Contra conta padrão para **ENTRADAS** (Clientes / > 0):", value=""
      )

    # --- ABA OPCIONAL: REGRAS PERSONALIZADAS (DE-PARA) ---
    st.markdown("---")
    regras_personalizadas = []
    with st.expander(
        "➕ Adicionar Regras Personalizadas (De-Para) [Opcional]"
    ):
      st.write(
          "Crie regras baseadas em termos contidos no histórico. Se o"
          " lançamento corresponder, a conta padrão será substituída pela"
          " informada."
      )

      # Usando st.session_state para manter as regras dinâmicas na tela
      if "num_regras" not in st.session_state:
        st.session_state.num_regras = 1

      col_b1, col_b2 = st.columns([1, 1])
      with col_b1:
        if st.button("➕ Adicionar nova regra"):
          st.session_state.num_regras += 1
      with col_b2:
        if st.button("🗑️ Limpar regras") and st.session_state.num_regras > 1:
          st.session_state.num_regras = 1

      for i in range(st.session_state.num_regras):
        st.markdown(f"**Regra {i+1}**")
        rc1, rc2, rc3 = st.columns([2, 1, 1])
        with rc1:
          termo = st.text_input(
              f"Se o histórico contiver:",
              key=f"termo_{i}",
              placeholder="Ex: Tarifas, Uber",
          )
        with rc2:
          tipo_mov = st.selectbox(
              "Tipo", ["Saída (< 0)", "Entrada (> 0)", "Ambos"], key=f"tipo_{i}"
          )
        with rc3:
          nova_conta = st.text_input(
              f"Usar a conta:", key=f"conta_regra_{i}", placeholder="Ex: 45"
          )

        if termo and nova_conta:
          regras_personalizadas.append({
              "termo": termo.strip().lower(),
              "tipo": tipo_mov,
              "conta": nova_conta.strip(),
          })
        st.markdown("")

    st.markdown("---")

    # Botão para processar
    if st.button("🚀 Processar e Gerar CSV", type="primary"):
      if not conta_fornecedor or not conta_cliente:
        st.error(
            "Por favor, preencha as contas transitórias padrão de Fornecedor e"
            " Cliente antes de continuar."
        )
      else:
        # 2. Tratamento da coluna VALOR
        if pd.api.types.is_numeric_dtype(df["Valor"]):
          df["VALOR_NUM"] = df["Valor"].fillna(0)
        else:
          df["VALOR_NUM"] = (
              df["Valor"]
              .astype(str)
              .str.replace(".", "", regex=False)
              .str.replace(",", ".", regex=False)
          )
          df["VALOR_NUM"] = pd.to_numeric(
              df["VALOR_NUM"], errors="coerce"
          ).fillna(0)

        # 4. Formatação prévia do Histórico (Necessário rodar antes para aplicar as regras de texto)
        def limpar_texto(valor):
          if (
              pd.isna(valor)
              or str(valor).strip().lower() in ["nan", "none", "nat", ""]
          ):
            return ""
          return str(valor).strip()

        df["Historico"] = (
            df["Descrição"].apply(limpar_texto)
            + " - "
            + df["Cliente"].apply(limpar_texto)
            + " - "
            + df["Nr. doc."].apply(limpar_texto)
            + " - "
            + df["Categoria"].apply(limpar_texto)
        )
        df["Historico"] = (
            df["Historico"]
            .str.replace(r"\s*-\s*-\s*", " - ", regex=True)
            .str.strip(" -")
        )

        # 3. Lógica Contábil Dinâmica com aplicação das Regras Personalizadas
        def define_debito(row):
          valor = row["VALOR_NUM"]
          hist_lower = str(row["Historico"]).lower()

          # Verifica se encaixa em alguma regra personalizada
          for regra in regras_personalizadas:
            if regra["termo"] in hist_lower:
              if regra["tipo"] == "Saída (< 0)" and valor < 0:
                return regra["conta"]
              elif regra["tipo"] == "Entrada (> 0)" and valor >= 0:
                return regra["conta"]
              elif regra["tipo"] == "Ambos":
                return regra["conta"]

          # Caso contrário, aplica a lógica padrão
          if valor < 0:
            return conta_fornecedor
          else:
            banco_linha = row.get("Conta bancária")
            return mapeamento_contas.get(banco_linha, "9")

        def define_credito(row):
          valor = row["VALOR_NUM"]
          hist_lower = str(row["Historico"]).lower()

          # Verifica se encaixa em alguma regra personalizada (para crédito)
          for regra in regras_personalizadas:
            if regra["termo"] in hist_lower:
              if regra["tipo"] == "Saída (< 0)" and valor < 0:
                return regra["conta"]
              elif regra["tipo"] == "Entrada (> 0)" and valor >= 0:
                return regra["conta"]
              elif regra["tipo"] == "Ambos":
                return regra["conta"]

          # Caso contrário, aplica a lógica padrão
          if valor < 0:
            banco_linha = row.get("Conta bancária")
            return mapeamento_contas.get(banco_linha, "9")
          else:
            return conta_cliente

        df["Conta Debito"] = df.apply(define_debito, axis=1)
        df["Conta Credito"] = df.apply(define_credito, axis=1)

        # 5. Montagem do layout final
        df_final = pd.DataFrame({
            "Data": pd.to_datetime(df["Data"], dayfirst=True)
            .dt.strftime("%d/%m/%Y"),
            "Conta Debito": df["Conta Debito"],
            "Conta Credito": df["Conta Credito"],
            "Valor": df["VALOR_NUM"].abs(),
            "Historico": df["Historico"],
        })

        # 6. Geração do CSV em memória com delimitador ponto e vírgula (sep=';')
        csv_buffer = io.StringIO()
        df_final.to_csv(
            csv_buffer, sep=";", index=False, decimal=",", encoding="cp1252"
        )
        csv_data = csv_buffer.getvalue()

        # Feedback visual aprimorado com métrica
        st.success(
            f"✨ Arquivo convertido com sucesso! ({len(df_final)} lançamentos"
            " gerados)"
        )

        # Mostra uma prévia na tela
        with st.expander("👀 Visualizar prévia dos primeiros lançamentos"):
          st.dataframe(df_final.head(15))

        # Botão de Download
        st.download_button(
            label="📥 Baixar Arquivo CSV para o Domínio",
            data=csv_data.encode("cp1252", errors="replace"),
            file_name="extrato_pronto_dominio.csv",
            mime="text/csv",
        )

  except Exception as e:
    st.error(f"Ocorreu um erro ao processar o arquivo: {e}")