# novo.py (Versão Corrigida e Melhorada)
import streamlit as st
import pandas as pd
from datetime import date
import os
from dotenv import load_dotenv
# CORREÇÃO: Corrigido o nome do arquivo de importação de 'db_adminasd' para 'db_admin'
from db_admin import (
    create_clube, read_clubes, update_clube, delete_clube,
    create_elenco, read_elencos_por_clube, update_elenco, delete_elenco,
    create_jogador, read_jogadores, update_jogador, delete_jogador, get_jogador
)
from models import Clube, Elenco, Jogador
from llm_admin import configure_llm, get_model, extract_players_from_file_llm

# Tenta importar bibliotecas de extração de texto de arquivos
try:
    import PyPDF2
    PDF_CAPABLE = True
except ImportError:
    PDF_CAPABLE = False

try:
    import docx2txt
    DOCX_CAPABLE = True
except ImportError:
    DOCX_CAPABLE = False


load_dotenv()

# Configuração da página
st.set_page_config(
    page_title="Gerenciador de Futebol",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS (mantido o original, pois é bom)
st.markdown("""
<style>
    .main-header {
        background-color: #004d40; /* Verde mais escuro */
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        text-align: center;
    }
    .main-header h1 {
        margin: 0;
        font-size: 2.2em;
    }
    .main-header p {
        margin: 5px 0 0 0;
        font-size: 1.1em;
    }
    .section-header {
        background-color: #00796b; /* Verde azulado */
        color: white;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 15px;
        font-size: 1.5em;
        font-weight: bold;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 8px 8px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #00796b; /* Cor da aba ativa */
        color: white;
        font-weight: bold;
    }
    div[role="tablist"] {
        justify-content: center;
    }
</style>
""", unsafe_allow_html=True)

# --- CORREÇÃO: Lógica da API Key na Sidebar simplificada e mais segura ---
st.sidebar.title("Configurações")
st.sidebar.header("API do Google AI")
api_key_env = os.getenv("GEMINI_API_KEY")
model = None
if api_key_env:
    if configure_llm(api_key_env):
        model = get_model()
        st.sidebar.success("✅ API do Google configurada com sucesso!")
    else:
        st.sidebar.error("❌ A chave de API fornecida é inválida.")
else:
    st.sidebar.warning("A inserção por arquivo está desabilitada. Configure a variável de ambiente 'GEMINI_API_KEY'.")


# --- Função Auxiliar para Extrair Texto de Arquivos ---
def get_text_from_file(uploaded_file):
    """Extrai texto de diferentes tipos de arquivos."""
    try:
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        
        if file_extension == ".pdf":
            if not PDF_CAPABLE:
                st.error("A biblioteca PyPDF2 não está instalada. A extração de PDF não está disponível.")
                return None
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
            return text
        
        elif file_extension == ".docx":
            if not DOCX_CAPABLE:
                st.error("A biblioteca docx2txt não está instalada. A extração de DOCX não está disponível.")
                return None
            return docx2txt.process(uploaded_file)

        elif file_extension == ".txt":
            return uploaded_file.getvalue().decode("utf-8", errors="ignore")
        
        else: # Para imagens (jpg, png) ou outros formatos
             st.warning(f"A extração de texto de arquivos '{file_extension}' não é suportada diretamente. A IA tentará analisar o nome do arquivo, mas os resultados podem ser imprecisos.")
             # A funcionalidade do Gemini 1.5 de analisar imagens diretamente não é usada aqui,
             # pois a função `extract_players_from_file_llm` espera apenas texto.
             return ""

    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
        return None


# --- Interface Principal ---
st.markdown("""
<div class="main-header">
    <h1>Gerenciador de Clubes de Futebol</h1>
    <p>Sistema completo para gestão de clubes, elencos e jogadores</p>
</div>
""", unsafe_allow_html=True)

# Métricas gerais
col_metrics1, col_metrics2, col_metrics3 = st.columns(3)
clubes_data = read_clubes()
jogadores_data = read_jogadores()
elencos_count = 0
if clubes_data:
    for clube in clubes_data:
        elencos_count += len(read_elencos_por_clube(clube.id or 0))
col_metrics1.metric("Clubes Cadastrados", len(clubes_data))
col_metrics2.metric("Elencos Ativos", elencos_count)
col_metrics3.metric("Jogadores Registrados", len(jogadores_data))

# Abas da aplicação
tab1, tab2, tab3 = st.tabs(["GESTÃO DE CLUBES", "GESTÃO DE ELENCOS", "GESTÃO DE JOGADORES"])

# --- ABA DE GESTÃO DE CLUBES ---
with tab1:
    st.markdown('<div class="section-header">Gerenciamento de Clubes</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Adicionar/Editar Clube")
        modo_clube = st.radio("Ação:", ["Adicionar Novo", "Editar Existente"], key="modo_clube", horizontal=True)
        clube_para_editar = None
        if modo_clube == "Editar Existente" and clubes_data:
            opcoes_clubes = {c.id: f"{c.nome} - {c.cidade}" for c in clubes_data if c.id is not None}
            clube_id_edit = st.selectbox(
                "Selecione o clube para editar:",
                options=[None] + list(opcoes_clubes.keys()),
                format_func=lambda x: opcoes_clubes.get(x, "Selecione..."),
                index=0,
                placeholder="Selecione um clube...",
                key="clube_edit_select"
            )
            if clube_id_edit:
                clube_para_editar = next((c for c in clubes_data if c.id == clube_id_edit), None)

        with st.form("form_clube", clear_on_submit=(modo_clube == "Adicionar Novo")):
            nome_inicial = clube_para_editar.nome if clube_para_editar else ""
            data_inicial = clube_para_editar.ano if clube_para_editar and isinstance(clube_para_editar.ano, date) else date.today()
            cidade_inicial = clube_para_editar.cidade if clube_para_editar else ""

            nome_clube = st.text_input("Nome do Clube", value=nome_inicial, max_chars=200)
            data_fundacao = st.date_input("Data de Fundação", value=data_inicial if data_inicial else date.today())
            cidade_clube = st.text_input("Cidade", value=cidade_inicial, max_chars=200)

            submit_button_label = 'Atualizar Clube' if modo_clube == 'Editar Existente' and clube_para_editar else 'Adicionar Clube'
            if st.form_submit_button(submit_button_label, type="primary", use_container_width=True):
                if nome_clube and data_fundacao:
                    clube_form = Clube(id=clube_para_editar.id if clube_para_editar else None, nome=nome_clube, ano=data_fundacao, cidade=cidade_clube)
                    if modo_clube == "Editar Existente" and clube_para_editar:
                        if update_clube(clube_form): st.success(f"Clube {nome_clube} atualizado com sucesso!")
                        else: st.error("Erro ao atualizar o clube.")
                    else:
                        if create_clube(clube_form): st.success(f"Clube {nome_clube} adicionado com sucesso!")
                        else: st.error("Erro ao adicionar o clube.")
                    st.rerun()
                else:
                    st.warning("O nome do clube é obrigatório.")

    with col2:
        st.subheader("Clubes Cadastrados")
        if clubes_data:
            df_clubes_data = [{'ID': c.id, 'Nome': c.nome, 'Fundação': c.ano.strftime('%d/%m/%Y') if c.ano else '', 'Cidade': c.cidade} for c in clubes_data]
            st.dataframe(pd.DataFrame(df_clubes_data), use_container_width=True, hide_index=True, column_config={"ID": st.column_config.NumberColumn(width="small")})
            
            st.subheader("Excluir Clube")
            st.warning("Atenção: Excluir um clube remove TODOS os elencos e jogadores associados permanentemente!")
            opcoes_exclusao = {c.id: c.nome for c in clubes_data if c.id is not None}
            clube_id_del = st.selectbox(
                "Selecione o clube para excluir:",
                options=[None] + list(opcoes_exclusao.keys()),
                format_func=lambda x: opcoes_exclusao.get(x, "Selecione..."),
                index=0, placeholder="Selecione um clube para excluir...", key="clube_delete_select"
            )
            if clube_id_del and st.button("Confirmar Exclusão", type="secondary", use_container_width=True):
                if delete_clube(clube_id_del): st.success("Clube e dados associados foram excluídos.")
                else: st.error("Erro ao excluir o clube.")
                st.rerun()
        else:
            st.info("Nenhum clube cadastrado ainda.")

# --- ABA DE GESTÃO DE ELENCOS ---
with tab2:
    st.markdown('<div class="section-header">Gerenciamento de Elencos</div>', unsafe_allow_html=True)
    if not clubes_data:
        st.warning("Nenhum clube cadastrado. Adicione um clube primeiro!")
    else:
        col1, col2 = st.columns([1, 2])
        todos_elencos = []
        for clube in clubes_data:
            elencos_clube = read_elencos_por_clube(clube.id or 0)
            for elenco in elencos_clube:
                todos_elencos.append((elenco, clube.nome))

        with col1:
            st.subheader("Adicionar/Editar Elenco")
            modo_elenco = st.radio("Ação:", ["Adicionar Novo", "Editar Existente"], key="modo_elenco", horizontal=True)
            elenco_para_editar = None
            if modo_elenco == "Editar Existente" and todos_elencos:
                opcoes_elencos = {e[0].id: f"{e[0].descricao} ({e[0].ano}) - {e[1]}" for e in todos_elencos if e[0].id is not None}
                elenco_id_edit = st.selectbox(
                    "Selecione o elenco para editar:",
                    options=[None] + list(opcoes_elencos.keys()), format_func=lambda x: opcoes_elencos.get(x, "Selecione..."),
                    index=0, placeholder="Selecione um elenco...", key="elenco_edit_select"
                )
                if elenco_id_edit:
                    elenco_para_editar = next((e[0] for e in todos_elencos if e[0].id == elenco_id_edit), None)

            with st.form("form_elenco", clear_on_submit=(modo_elenco == "Adicionar Novo")):
                clube_opts = {c.id: c.nome for c in clubes_data if c.id is not None}
                clube_ids_form = list(clube_opts.keys())
                clube_id_inicial = elenco_para_editar.fk_clube if elenco_para_editar else (clube_ids_form[0] if clube_ids_form else None)
                clube_id_form = st.selectbox("Clube", options=clube_ids_form, format_func=lambda x: clube_opts.get(x, "Desconhecido"), index=clube_ids_form.index(clube_id_inicial) if clube_id_inicial in clube_ids_form else 0)
                
                ano_inicial = elenco_para_editar.ano if elenco_para_editar else date.today().year
                desc_inicial = elenco_para_editar.descricao if elenco_para_editar else ""
                ano_elenco = st.number_input("Ano do Elenco", min_value=1900, max_value=2100, step=1, value=ano_inicial)
                desc_elenco = st.text_input("Descrição", value=desc_inicial, placeholder="Ex: Principal, Sub-20")

                submit_label = 'Atualizar Elenco' if modo_elenco == 'Editar Existente' and elenco_para_editar else 'Adicionar Elenco'
                if st.form_submit_button(submit_label, type="primary", use_container_width=True):
                    if clube_id_form and desc_elenco:
                        elenco_form = Elenco(id=elenco_para_editar.id if elenco_para_editar else None, fk_clube=clube_id_form, ano=ano_elenco, descricao=desc_elenco)
                        if modo_elenco == "Editar Existente" and elenco_para_editar:
                            if update_elenco(elenco_form): st.success(f"Elenco '{desc_elenco}' atualizado!")
                            else: st.error("Erro ao atualizar o elenco.")
                        else:
                            if create_elenco(elenco_form): st.success(f"Elenco '{desc_elenco}' adicionado!")
                            else: st.error("Erro ao adicionar o elenco.")
                        st.rerun()
                    else:
                        st.warning("Clube e descrição são obrigatórios.")
        with col2:
            st.subheader("Elencos por Clube")
            for clube in clubes_data:
                with st.expander(f"Clube: {clube.nome}", expanded=True):
                    elencos_clube = read_elencos_por_clube(clube.id or 0)
                    if elencos_clube:
                        df_elencos_data = [{'ID': e.id, 'Ano': e.ano, 'Descrição': e.descricao} for e in elencos_clube]
                        st.dataframe(pd.DataFrame(df_elencos_data), use_container_width=True, hide_index=True, column_config={"ID": st.column_config.NumberColumn(width="small")})
                        
                        opcoes_del = {e.id: f"{e.descricao} ({e.ano})" for e in elencos_clube if e.id is not None}
                        elenco_del = st.selectbox(f"Excluir elenco de {clube.nome}:", options=[None] + list(opcoes_del.keys()), format_func=lambda x: opcoes_del.get(x, "Selecione..."), index=0, placeholder="Selecione para excluir...", key=f"del_elenco_{clube.id}")
                        if elenco_del and st.button(f"Excluir Elenco Selecionado", key=f"btn_del_{elenco_del}", type="secondary"):
                            if delete_elenco(elenco_del): st.success("Elenco excluído!")
                            else: st.error("Erro ao excluir o elenco.")
                            st.rerun()
                    else:
                        st.info("Nenhum elenco cadastrado para este clube.")

# --- ABA DE GESTÃO DE JOGADORES ---
with tab3:
    st.markdown('<div class="section-header">Gerenciamento de Jogadores</div>', unsafe_allow_html=True)
    subtab1, subtab2 = st.tabs(["Gerenciamento Manual", "Inserção em Lote por Arquivo"])

    todos_elencos = []
    if clubes_data:
        for clube in clubes_data:
            elencos_clube = read_elencos_por_clube(clube.id or 0)
            for elenco in elencos_clube:
                todos_elencos.append((elenco, clube.nome))

    with subtab1:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("Adicionar/Editar Jogador")
            if not todos_elencos:
                st.warning("Nenhum elenco cadastrado. Adicione um elenco primeiro!")
            else:
                modo_jogador = st.radio("Ação:", ["Adicionar Novo", "Editar Existente"], key="modo_jogador", horizontal=True)
                jogador_para_editar = None
                
                # CORREÇÃO: Lógica para carregar o jogador para edição foi revisada e corrigida
                if modo_jogador == "Editar Existente" and jogadores_data:
                    opcoes_jogadores = {j[0]: f"{j[1]} - {j[4]}" for j in jogadores_data}
                    jogador_id_edit = st.selectbox(
                         "Selecione o jogador para editar:",
                         options=[None] + list(opcoes_jogadores.keys()), format_func=lambda x: opcoes_jogadores.get(x, "Selecione..."),
                         index=0, placeholder="Selecione um jogador...", key="jogador_edit_select"
                    )
                    if jogador_id_edit:
                        row = get_jogador(jogador_id_edit)
                        if row:
                            # Constrói o objeto Jogador a partir da tupla retornada pelo banco de dados
                            jogador_para_editar = Jogador(
                                id=row[0], elenco_id=row[1], nome=row[2], 
                                data_nascimento=row[3] if isinstance(row[3], date) else None,
                                posicao=row[4], nacionalidade=row[5], pe_dominante=row[6],
                                numero_partidas=row[7], total_minutos_jogados=row[8],
                                gols_marcados=row[9], assistencias=row[10]
                            )
                        else:
                            st.error("Não foi possível carregar os dados do jogador selecionado.")
                
                with st.form("form_jogador", clear_on_submit=(modo_jogador == "Adicionar Novo")):
                    elenco_opts = {e[0].id: f"{e[0].descricao} ({e[0].ano}) - {e[1]}" for e in todos_elencos if e[0].id is not None}
                    elenco_ids_form = list(elenco_opts.keys())
                    
                    # Define o valor inicial do selectbox de elenco
                    elenco_id_inicial_idx = 0
                    if jogador_para_editar and jogador_para_editar.elenco_id in elenco_ids_form:
                        elenco_id_inicial_idx = elenco_ids_form.index(jogador_para_editar.elenco_id)

                    elenco_id = st.selectbox("Elenco", options=elenco_ids_form, format_func=lambda x: elenco_opts.get(x, "Desconhecido"), index=elenco_id_inicial_idx)

                    nome_jogador = st.text_input("Nome do Jogador", value=jogador_para_editar.nome if jogador_para_editar else "")
                    data_nascimento = st.date_input("Data de Nascimento", value=jogador_para_editar.data_nascimento if jogador_para_editar else None)
                    
                    posicoes = ["", "Goleiro", "Zagueiro", "Lateral Direito", "Lateral Esquerdo", "Volante", "Meio-campo", "Atacante", "Ponta Direita", "Ponta Esquerda"]
                    posicao_init_idx = posicoes.index(jogador_para_editar.posicao) if jogador_para_editar and jogador_para_editar.posicao in posicoes else 0
                    posicao = st.selectbox("Posição", options=posicoes, index=posicao_init_idx)
                    
                    nacionalidade = st.text_input("Nacionalidade", value=jogador_para_editar.nacionalidade if jogador_para_editar else "", placeholder="Ex: Brasileiro")
                    
                    pe_dominante_opts = {"": "Não informado", "D": "Destro", "E": "Esquerdo"}
                    pe_dominante_keys = list(pe_dominante_opts.keys())
                    pe_init_idx = pe_dominante_keys.index(jogador_para_editar.pe_dominante) if jogador_para_editar and jogador_para_editar.pe_dominante in pe_dominante_keys else 0
                    pe_dominante = st.radio("Pé Dominante", options=pe_dominante_keys, format_func=lambda x: pe_dominante_opts[x], index=pe_init_idx, horizontal=True)

                    st.subheader("Estatísticas")
                    col_stat1, col_stat2 = st.columns(2)
                    partidas = col_stat1.number_input("Partidas", min_value=0, step=1, value=jogador_para_editar.numero_partidas if jogador_para_editar else 0)
                    gols = col_stat1.number_input("Gols", min_value=0, step=1, value=jogador_para_editar.gols_marcados if jogador_para_editar else 0)
                    minutos = col_stat2.number_input("Minutos Jogados", min_value=0, step=1, value=jogador_para_editar.total_minutos_jogados if jogador_para_editar else 0)
                    assistencias = col_stat2.number_input("Assistências", min_value=0, step=1, value=jogador_para_editar.assistencias if jogador_para_editar else 0)

                    submit_label = 'Atualizar Jogador' if modo_jogador == 'Editar Existente' and jogador_para_editar else 'Adicionar Jogador'
                    if st.form_submit_button(submit_label, type="primary", use_container_width=True):
                        if nome_jogador and elenco_id:
                            jogador_form = Jogador(
                                id=jogador_para_editar.id if jogador_para_editar else None, elenco_id=elenco_id, nome=nome_jogador,
                                data_nascimento=data_nascimento, posicao=posicao or None, nacionalidade=nacionalidade or None,
                                pe_dominante=pe_dominante or None, numero_partidas=partidas, total_minutos_jogados=minutos,
                                gols_marcados=gols, assistencias=assistencias
                            )
                            if modo_jogador == "Editar Existente" and jogador_para_editar:
                                if update_jogador(jogador_form): st.success(f"Jogador {nome_jogador} atualizado!")
                                else: st.error("Erro ao atualizar o jogador.")
                            else:
                                if create_jogador(jogador_form): st.success(f"Jogador {nome_jogador} adicionado!")
                                else: st.error("Erro ao adicionar o jogador.")
                            st.rerun()
                        else:
                            st.warning("Nome do jogador e elenco são obrigatórios.")
        with col2:
            st.subheader("Jogadores Cadastrados")
            if jogadores_data:
                df_jogadores = pd.DataFrame(jogadores_data, columns=['ID', 'Nome', 'Nascimento', 'Posição', 'Clube', 'Elenco'])
                st.dataframe(df_jogadores, use_container_width=True, hide_index=True, column_config={"ID": st.column_config.NumberColumn(width="small")})
                
                st.subheader("Excluir Jogador")
                opcoes_jogadores_del = {j[0]: f"{j[1]} - {j[4]}" for j in jogadores_data}
                jogador_id_del = st.selectbox(
                    "Selecione o jogador para excluir:",
                    options=[None] + list(opcoes_jogadores_del.keys()), format_func=lambda x: opcoes_jogadores_del.get(x, "Selecione..."),
                    index=0, placeholder="Selecione para excluir...", key="jogador_delete_select"
                )
                if jogador_id_del and st.button("Confirmar Exclusão de Jogador", type="secondary", use_container_width=True):
                    if delete_jogador(jogador_id_del): st.success("Jogador excluído!")
                    else: st.error("Erro ao excluir o jogador.")
                    st.rerun()
            else:
                st.info("Nenhum jogador cadastrado ainda.")

    with subtab2:
        st.subheader("Inserir Jogadores em Lote a partir de Arquivo")
        if not model:
            st.error("Funcionalidade desabilitada. Configure a variável de ambiente 'GEMINI_API_KEY' para usar a IA.")
        elif not todos_elencos:
            st.warning("Nenhum elenco disponível. Crie um elenco na aba 'Gerenciamento Manual' primeiro.")
        else:
            if 'player_list_df' not in st.session_state: 
                st.session_state.player_list_df = None
            
            elenco_opts_lote = {e[0].id: f"{e[0].descricao} ({e[0].ano}) - {e[1]}" for e in todos_elencos if e[0].id is not None}
            selected_elenco_id = st.selectbox(
                "Escolha o Elenco de Destino:",
                options=[None] + list(elenco_opts_lote.keys()), format_func=lambda x: elenco_opts_lote.get(x, "Selecione..."),
                index=0, placeholder="Selecione um elenco...", key="lote_elenco_select"
            )

            # CORREÇÃO: Adicionadas mais extensões e desabilitado o uploader se nenhum elenco for selecionado
            uploaded_file = st.file_uploader(
                "Faça upload de um arquivo contendo a lista de jogadores", 
                type=["txt", "pdf", "docx"], 
                disabled=not selected_elenco_id
            )
            
            if uploaded_file and selected_elenco_id:
                if st.button("Extrair Jogadores do Arquivo", type="primary", use_container_width=True):
                    with st.spinner("Analisando o arquivo com IA... Por favor, aguarde."):
                        # CORREÇÃO: O conteúdo do arquivo é lido e passado como texto para a função da IA
                        file_content = get_text_from_file(uploaded_file)
                        if file_content is not None:
                            extracted_df = extract_players_from_file_llm(file_content)
                            if extracted_df is not None and not extracted_df.empty:
                                extracted_df['✅ Inserir'] = True
                                cols = ['✅ Inserir', 'Nome'] + [col for col in extracted_df.columns if col not in ['✅ Inserir', 'Nome']]
                                st.session_state.player_list_df = extracted_df[cols]
                                st.success("Jogadores extraídos com sucesso! Revise e confirme abaixo.")
                            else:
                                st.error("Não foi possível extrair jogadores do arquivo. Verifique o formato ou conteúdo.")
                                st.session_state.player_list_df = None
                        else:
                            st.session_state.player_list_df = None


        if st.session_state.player_list_df is not None:
            st.markdown("### Revise, Edite e Confirme os Jogadores")
            st.info("Desmarque a caixa '✅ Inserir' para qualquer jogador que você não queira adicionar.")
            edited_df = st.data_editor(st.session_state.player_list_df, use_container_width=True, hide_index=True, num_rows="dynamic")
            
            if st.button("Confirmar e Inserir no Banco", type="primary", use_container_width=True):
                # Filtra o DataFrame para incluir apenas as linhas marcadas para inserção
                jogadores_para_inserir = edited_df[edited_df['✅ Inserir'] == True]
                total = len(jogadores_para_inserir)

                if total > 0 and selected_elenco_id:
                    progress_bar = st.progress(0, text=f"Inserindo {total} jogadores...")
                    sucessos, falhas = 0, 0
                    
                    for i, row in enumerate(jogadores_para_inserir.itertuples()):
                        try:
                            # Constrói o objeto Jogador a partir dos dados do DataFrame editado
                            jogador_lote = Jogador(
                                elenco_id=selected_elenco_id, 
                                nome=row.Nome,
                                data_nascimento=pd.to_datetime(row.Data_Nascimento, errors='coerce').date() if hasattr(row, 'Data_Nascimento') and pd.notna(row.Data_Nascimento) else None,
                                posicao=getattr(row, 'Posicao', None),
                                nacionalidade=getattr(row, 'Nacionalidade', None),
                                pe_dominante=getattr(row, 'Pe_Dominante', None),
                                numero_partidas=int(getattr(row, 'Numero_Partidas', 0) or 0),
                                total_minutos_jogados=int(getattr(row, 'Total_Minutos_Jogados', 0) or 0),
                                gols_marcados=int(getattr(row, 'Gols_Marcados', 0) or 0),
                                assistencias=int(getattr(row, 'Assistencias', 0) or 0)
                            )
                            if create_jogador(jogador_lote):
                                sucessos += 1
                            else:
                                falhas += 1
                                st.warning(f"Falha ao inserir {row.Nome}: a operação no banco de dados retornou 'False'. Verifique o console para detalhes.")
                        except Exception as e:
                            falhas += 1
                            st.warning(f"Falha ao processar {row.Nome}: {e}")
                        
                        progress_bar.progress((i + 1) / total, text=f"Progresso: {i+1}/{total}")
                    
                    st.success(f"Operação concluída! ✅ {sucessos} inseridos, ❌ {falhas} falhas.")
                    st.session_state.player_list_df = None
                    st.rerun()
                elif not selected_elenco_id:
                     st.error("O elenco de destino não está mais selecionado. Por favor, recomece o processo.")