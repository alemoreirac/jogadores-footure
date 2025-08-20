import streamlit as st
import requests
import base64
import os

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

if "token" not in st.session_state:
    st.session_state.token = None

def headers():
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}

def login(email, password):
    r = requests.post(f"{API_BASE}/api/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json().get("token")

def list_docs():
    r = requests.get(f"{API_BASE}/api/documents", headers=headers())
    r.raise_for_status()
    return r.json()

def upload_document(file_bytes, filename):
    b64 = base64.b64encode(file_bytes).decode()
    data = {"file_base64": b64, "filename": filename}
    r = requests.post(f"{API_BASE}/api/documents", data=data, headers=headers())
    r.raise_for_status()
    return r.json()

def delete_document(doc_id):
    r = requests.delete(f"{API_BASE}/api/documents/{doc_id}", headers=headers())
    r.raise_for_status()
    return r.json()

def ai_retrieval(query):
    try:
        url = f"{API_BASE}/api/ai/retrieval"

        r = requests.get(url+'/'+query, headers=headers(), timeout=30)

        if r.status_code == 422:
            error_detail = r.json().get("detail", "Dados inválidos")
            raise ValueError(f"Dados inválidos: {error_detail}")

        r.raise_for_status()
        return r.json().get("result")

    except requests.exceptions.Timeout:
        raise ValueError("Timeout na requisição. Tente novamente.")
    except requests.exceptions.ConnectionError:
        raise ValueError("Erro de conexão com a API")
    except Exception as e:
        if hasattr(e, 'response') and e.response is not None and e.response.status_code == 401:
            raise ValueError("Token inválido. Faça login novamente.")
        raise ValueError(f"Erro na requisição: {str(e)}")
st.set_page_config(page_title="AI & Docs", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
:root{--accent:#6C5CE7;}
body{font-family:Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial}
.main > div.block-container{padding-left:12px;padding-right:12px}
.header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.brand{font-weight:700;font-size:20px;color:var(--accent)}
.nav{display:flex;gap:8px}
.button{background:var(--accent);color:#fff;padding:8px 12px;border-radius:10px;text-decoration:none}
.grid{display:grid;grid-template-columns:repeat(1,1fr);gap:12px}
.card{border-radius:12px;padding:12px;background:#fff;box-shadow:0 6px 18px rgba(16,24,40,0.06)}
@media(min-width:700px){.grid{grid-template-columns:repeat(2,1fr)}}
@media(min-width:1000px){.grid{grid-template-columns:repeat(3,1fr)}}
</style>
""", unsafe_allow_html=True)

with st.container():
    st.markdown("<div class='header'><div class='brand'>AI • Documents</div><div class='nav'></div></div>", unsafe_allow_html=True)

if not st.session_state.token:
    with st.form("login_form"):
        st.subheader("Entrar")
        email = st.text_input("E-mail")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")
        if submitted:
            try:
                token = login(email, password)
                st.session_state.token = token
                st.rerun()
            except Exception as e:
                st.error(str(e))

else:
    menu = st.radio("", ["Dashboard", "Documentos", "AI Chat", "Sair"], index=0, horizontal=True)

    if menu == "Sair":
        st.session_state.token = None
        st.rerun()

    if menu == "Dashboard":
        st.subheader("Visão Geral")
        try:
            docs = list_docs()
            total = len(docs) if isinstance(docs, list) else 0
        except Exception:
            total = 0
        cols = st.columns(3)
        cols[0].metric("Documentos", total)
        cols[1].metric("Usuário", "Autenticado")
        cols[2].metric("API", API_BASE)

    if menu == "Documentos":
        st.subheader("Meus documentos")
        col1, col2 = st.columns([2,1])
        with col1:
            uploaded = st.file_uploader("Enviar arquivo", type=None)
            if uploaded:
                if st.button("Enviar"):
                    try:
                        resp = upload_document(uploaded.read(), uploaded.name)
                        st.success("Enviado")
                    except Exception as e:
                        st.error(str(e))
        with col2:
            st.write("Formato: qualquer. Será enviado como Base64")
        try:
            docs = list_docs()
        except Exception as e:
            st.error(str(e))
            docs = []
        st.markdown("<div class='grid'>", unsafe_allow_html=True)
        for d in docs:
            doc_id = d.get("id") or d.get("_id") or d.get("document_id") or d.get("doc_id") or ""
            title = d.get("filename") or d.get("name") or "Documento"
            content = d.get("snippet") or d.get("summary") or ""
            st.markdown(f"<div class='card'><b>{title}</b><p style='color:#475569'>{content}</p><div style='display:flex;gap:8px;margin-top:8px'><a class='button' href='#' onclick=\"window.open('{API_BASE}/api/documents/{doc_id}')\">Abrir</a> <button onclick=\"\"> </button></div></div>", unsafe_allow_html=True)
            key = f"del_{doc_id}"
            if st.button("Excluir", key=key):
                try:
                    delete_document(doc_id)
                    st.success("Excluído")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        st.markdown("</div>", unsafe_allow_html=True)

    if menu == "AI Chat":
        st.subheader("Consulta rápida")
        q = st.text_area("Pergunta")
        if st.button("Enviar pergunta"):
            try:
                with st.spinner("Processando..."):
                    result = ai_retrieval(q)
                st.success("Pronto")
                st.text_area("Resposta", value=result, height=240)
            except Exception as e:
                st.error(str(e))