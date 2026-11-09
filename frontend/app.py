import base64
import hashlib
import os
import secrets
import time
from urllib.parse import urlencode

import jwt
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
KC_URL = os.getenv("KEYCLOAK_URL", "http://127.0.0.1:8080").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "demo-realm")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "streamlit-app")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8005").rstrip("/")
APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8501/")
OIDC = f"{KC_URL}/realms/{REALM}/protocol/openid-connect"

st.set_page_config(page_title="Secure Data Platform", layout="wide")


# ───────────────────────── Authentification OIDC (Code + PKCE) ─────────────────────────
@st.cache_resource
def pending_logins() -> dict:
    """state -> {code_verifier, ts}. Partagé entre sessions Streamlit (survit à la redirection)."""
    return {}


def build_login_url() -> str:
    state = secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    pending_logins()[state] = {"verifier": verifier, "ts": time.time()}
    return f"{OIDC}/auth?" + urlencode({
        "client_id": CLIENT_ID, "response_type": "code", "scope": "openid profile email",
        "redirect_uri": APP_URL, "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })


def handle_callback():
    qp = st.query_params
    if "error" in qp:
        st.error(f"Erreur Keycloak : {qp.get('error_description', qp['error'])}")
        st.query_params.clear()
        return
    if "code" not in qp:
        return

    code, state = qp["code"], qp.get("state", "")
    st.query_params.clear()
    entry = pending_logins().pop(state, None)
    if not entry or time.time() - entry["ts"] > 600:
        st.error("Tentative de connexion invalide ou expirée. Réessayez.")
        return

    r = requests.post(f"{OIDC}/token", timeout=10, data={
        "grant_type": "authorization_code", "client_id": CLIENT_ID, "code": code,
        "redirect_uri": APP_URL, "code_verifier": entry["verifier"],
    })
    if r.status_code != 200:
        st.error(f"Échange du code refusé ({r.status_code}) : {r.text}")
        return

    tokens = r.json()
    st.session_state["access_token"] = tokens["access_token"]
    st.session_state["id_token"] = tokens.get("id_token")
    st.rerun()


def claims_of(token: str) -> dict:
    # Lecture SANS vérification, uniquement pour l'affichage/UX.
    # La vraie sécurité (signature, rôles) est appliquée par l'API.
    return jwt.decode(token, options={"verify_signature": False})


def local_logout():
    id_token = st.session_state.get("id_token")
    for k in ("access_token", "id_token", "last_result", "login_url"):
        st.session_state.pop(k, None)
    if id_token:
        st.session_state["kc_logout_url"] = f"{OIDC}/logout?" + urlencode(
            {"id_token_hint": id_token, "post_logout_redirect_uri": APP_URL, "client_id": CLIENT_ID})


# ───────────────────────── Appels API ─────────────────────────
def call_api(path: str, params: dict | None = None) -> requests.Response:
    return requests.get(
        f"{API_URL}{path}", params=params, timeout=30,
        headers={
            "Authorization": f"Bearer {st.session_state['access_token']}",
            "User-Agent": "streamlit-frontend/1.0",
            "X-Client-App": "streamlit",
        },
    )


def explain_error(r: requests.Response):
    if r.status_code == 401:
        st.error("Session expirée ou jeton invalide : reconnectez-vous.")
    elif r.status_code == 403:
        st.error("⛔ 403 : l'API refuse l'accès (rôle insuffisant).")
    else:
        st.error(f"Erreur {r.status_code} : {r.text}")


# ───────────────────────── Flux principal ─────────────────────────
handle_callback()

token = st.session_state.get("access_token")
claims = claims_of(token) if token else None
if claims and claims.get("exp", 0) < time.time():
    local_logout()
    st.warning("Votre session a expiré.")
    token, claims = None, None

if not claims:
    st.title("Secure Data Platform")
    if "login_url" not in st.session_state:
        st.session_state["login_url"] = build_login_url()
    st.info("Authentification centralisée via Keycloak (SSO).")
    st.link_button("Se connecter avec Keycloak", st.session_state["login_url"], type="primary")
    if "kc_logout_url" in st.session_state:
        st.caption("Pour fermer aussi la session SSO Keycloak :")
        st.link_button("Terminer la session Keycloak", st.session_state["kc_logout_url"])
    st.stop()

username = claims.get("preferred_username", "?")
roles = claims.get("realm_access", {}).get("roles", [])
can_extract = bool({"Data-Analyst", "Admin"} & set(roles))
is_admin = "Admin" in roles

with st.sidebar:
    st.header(f"👤 {username}")
    st.caption(claims.get("email", ""))
    st.write("**Rôles :** " + (", ".join(r for r in roles if r in ("Data-Analyst", "Admin")) or "_aucun_"))
    st.write(f"**Expire dans :** {int(claims['exp'] - time.time())} s")
    if st.button("Se déconnecter"):
        local_logout()
        st.rerun()

tab_names = ["👤 Profil"]
if can_extract:
    tab_names.append("Extraction")
if is_admin:
    tab_names.append("🛡️ Audit")
tabs = dict(zip(tab_names, st.tabs(tab_names)))

# ── Profil ──
with tabs["👤 Profil"]:
    st.subheader("Informations du jeton")
    st.json({k: claims.get(k) for k in ("sub", "preferred_username", "email", "iat", "exp", "azp")})
    if not can_extract:
        st.warning("Votre compte n'a aucun rôle métier : aucune fonctionnalité d'extraction disponible.")
    st.divider()
    st.caption("Démonstration : le masquage de l'interface n'est PAS la sécurité. L'API refuse côté serveur.")
    if st.button("Tenter d'appeler /audit/logs (réservé Admin)"):
        r = call_api("/audit/logs")
        st.success("200 : accès autorisé") if r.ok else explain_error(r)

# ── Extraction ──
if can_extract:
    with tabs["Extraction"]:
        with st.form("extract_form"):
            c1, c2, c3 = st.columns(3)
            country = c1.selectbox("Pays", ["(tous)", "France", "Germany", "Spain", "Italy", "Belgium"])
            category = c2.selectbox("Catégorie", ["(toutes)", "Electronics", "Clothing", "Home", "Sports", "Books"])
            status = c3.selectbox("Statut", ["(tous)", "completed", "pending", "refunded", "cancelled"])
            c4, c5, c6, c7 = st.columns(4)
            date_from = c4.date_input("Du", value=None)
            date_to = c5.date_input("Au", value=None)
            min_amount = c6.number_input("Montant min", min_value=0.0, value=0.0, step=10.0)
            max_amount = c7.number_input("Montant max (0 = illimité)", min_value=0.0, value=0.0, step=10.0)
            limit = st.slider("Limite de lignes", 10, 10000, 1000)
            submitted = st.form_submit_button("Extraire", type="primary")

        if submitted:
            params = {
                "country": None if country == "(tous)" else country,
                "category": None if category == "(toutes)" else category,
                "status": None if status == "(tous)" else status,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "min_amount": min_amount or None,
                "max_amount": max_amount or None,
                "limit": limit,
            }
            r = call_api("/extract", {k: v for k, v in params.items() if v is not None})
            if r.ok:
                st.session_state["last_result"] = r.json()
            else:
                st.session_state.pop("last_result", None)
                explain_error(r)

        result = st.session_state.get("last_result")
        if result:
            a = result["audit"]
            m1, m2, m3 = st.columns(3)
            m1.metric("Lignes", a["row_count"])
            m2.metric("Poids (octets)", f"{a['size_bytes']:,}")
            m3.metric("Audit ID", a["audit_id"][:8] + "…")
            st.caption(f"SHA-256 : `{a['sha256']}` · UTC : {a['timestamp_utc']}")
            df = pd.DataFrame(result["data"])
            st.dataframe(df, use_container_width=True)
            st.download_button("Télécharger CSV", df.to_csv(index=False).encode("utf-8"),
                               "extraction.csv", "text/csv")

# ── Audit (Admin) ──
if is_admin:
    with tabs["Audit"]:
        n = st.slider("Nombre d'entrées", 10, 500, 50)
        if st.button("Charger le journal d'audit"):
            r = call_api("/audit/logs", {"limit": n})
            if r.ok:
                st.dataframe(pd.json_normalize(r.json()), use_container_width=True)
            else:
                explain_error(r)