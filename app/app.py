"""
Application Streamlit de l'atelier Agents IA.

Lancement (depuis la racine du dépôt) :
    streamlit run app/app.py

Onglet 1 « Agent »      : on écrit une demande, l'agent cherche et rédige.
Onglet 2 « Validation » : l'humain relit chaque message et décide de l'envoyer.
"""
import html
import os
from pathlib import Path

import streamlit as st

import moteur
import validation

EXEMPLES = [
    "Trouve 5 boulangeries à Dakar Plateau et rédige un message chaleureux pour chacune.",
    "Je cherche 3 pharmacies aux Almadies, prépare un message formel pour chacune.",
    "Trouve 4 quincailleries à Pikine et écris-leur un message direct.",
]

st.set_page_config(page_title="Agent de prospection", page_icon="🤖", layout="wide")


@st.cache_resource(show_spinner=False)
def charger_prospection():
    """Importe la boîte à outils une seule fois (elle crée le client Anthropic)."""
    import prospection
    return prospection


def lire_secrets() -> dict:
    """Secrets Streamlit Cloud (ou .streamlit/secrets.toml) ; vide s'il n'y en a pas."""
    try:
        return dict(st.secrets)
    except Exception:  # aucun fichier de secrets : on se contente du .env
        return {}


def exiger_mot_de_passe(attendu: str):
    """Si APP_MOT_DE_PASSE est défini, bloque la page tant qu'il n'est pas saisi."""
    if not attendu or st.session_state.get("acces_ok"):
        return
    saisi = st.text_input("Mot de passe de l'atelier", type="password")
    if moteur.mot_de_passe_correct(saisi, attendu):
        st.session_state.acces_ok = True
        st.rerun()
    if saisi:
        st.error("Mot de passe incorrect.")
    st.stop()


def injecter_style():
    css = (Path(__file__).parent / "style.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def initialiser_etat():
    st.session_state.setdefault("contacts", ())
    st.session_state.setdefault("resultat", None)
    st.session_state.setdefault("choisi", None)
    st.session_state.setdefault("vient_envoye", None)
    st.session_state.setdefault("demande", EXEMPLES[0])
    st.session_state.setdefault("version_demande", 0)
    st.session_state.setdefault("erreur_agent", "")


def choisir_exemple():
    if st.session_state.exemple:
        st.session_state.demande = st.session_state.exemple
        st.session_state.version_demande += 1  # nouvelle clé = la zone de texte se remet à jour


def barre_laterale(prospection) -> float:
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        apify = bool(os.getenv("APIFY_TOKEN", "").strip())
        st.markdown(f"**Anthropic** : {'✅' if os.getenv('ANTHROPIC_API_KEY') else '❌'}  \n"
                    f"**Apify** : {'✅ Google Maps' if apify else '🧪 mode démo (commerces fictifs)'}")
        st.caption(f"Modèle principal : `{prospection.MODELE}`  \nModèle rapide : `{prospection.MODELE_RAPIDE}`")
        budget = st.slider("Budget maximal par demande (FCFA)", 50, 2000,
                           int(prospection.BUDGET_MAX_FCFA), step=50)
        st.divider()
        st.metric("Dépensé depuis le lancement",f"{prospection.COMPTEUR.fcfa:.1f} FCFA")
        st.caption("🔒 Les envois sont **simulés** : rien n'est réellement envoyé. "
                   "Ils sont écrits dans `donnees/envois_simules.log`.")
    return budget


def afficher_etape(conteneur, etape: moteur.Etape):
    icone = "⚠️" if etape.erreur else ("🔎" if etape.outil == "rechercher_commerces" else "✍️")
    args = ", ".join(f"{k}={v!r}" for k, v in etape.arguments.items())
    texte = f"{icone} <span class='etape'>{html.escape(etape.outil)}({html.escape(args)})</span>"
    if etape.erreur:
        texte += f"<br><small>↳ {html.escape(etape.erreur)}</small>"
    conteneur.markdown(texte, unsafe_allow_html=True)


def executer_agent(prospection, demande: str, budget: float):
    with st.status("L'agent travaille…", expanded=True) as statut:
        try:
            resultat = moteur.lancer_agent(demande, budget,
                                           sur_etape=lambda e: afficher_etape(statut, e),
                                           prospection=prospection)
        except Exception as e:
            statut.update(label="L'agent a rencontré une erreur", state="error")
            st.session_state.erreur_agent = f"{type(e).__name__} : {e}"
            return
        statut.update(label="Terminé", state="complete", expanded=False)
    st.session_state.erreur_agent = ""
    st.session_state.resultat = resultat
    st.session_state.contacts = resultat.contacts
    st.session_state.choisi = resultat.contacts[0].id if resultat.contacts else None
    st.session_state.vient_envoye = None


def onglet_agent(prospection, budget: float):
    st.markdown("#### Que doit faire l'agent ?")
    st.selectbox("Exemples de demandes", EXEMPLES, index=None, key="exemple",
                 placeholder="Choisir un exemple…", label_visibility="collapsed",
                 on_change=choisir_exemple)
    # value= explicite : un widget pré-rempli seulement par session_state s'affiche vide
    demande = st.text_area("Votre demande", value=st.session_state.demande, height=110,
                           key=f"demande_{st.session_state.version_demande}",
                           label_visibility="collapsed")
    st.session_state.demande = demande
    if st.button("🚀 Lancer l'agent", type="primary", disabled=not demande.strip()):
        executer_agent(prospection, demande.strip(), budget)
        st.rerun()  # pour mettre à jour la dépense dans la barre latérale

    if st.session_state.erreur_agent:
        st.error(f"L'agent a rencontré une erreur : {st.session_state.erreur_agent}")
    resultat = st.session_state.resultat
    if resultat is None:
        return
    st.markdown("#### Réponse de l'agent")
    st.caption(f"{len(resultat.etapes)} appel(s) d'outil · {resultat.cout_fcfa:.1f} FCFA")
    st.info(resultat.reponse or "(pas de réponse texte)")
    n = len(resultat.contacts)
    if n:
        st.success(f"**{n} contact(s)** trouvé(s). Ouvrez l'onglet **✅ Validation** "
                   "pour relire et envoyer les messages.")
        with st.expander("Voir les appels d'outils"):
            for etape in resultat.etapes:
                afficher_etape(st, etape)
    else:
        st.warning("Aucun commerce trouvé. Essayez une autre activité ou une autre zone.")


def main():
    injecter_style()
    initialiser_etat()
    st.markdown("<div class='bandeau'><h1>Agent de prospection</h1>"
                "<p>L'agent cherche des commerces et rédige les messages. "
                "<b>Vous</b> décidez de ce qui part.</p></div>", unsafe_allow_html=True)
    secrets = lire_secrets()
    os.environ.update(moteur.variables_depuis_secrets(secrets, os.environ))
    exiger_mot_de_passe(os.getenv("APP_MOT_DE_PASSE", ""))
    try:
        prospection = charger_prospection()
    except Exception as e:
        st.error(f"Impossible de charger l'agent : {e}\n\n"
                 "Vérifiez que `ANTHROPIC_API_KEY` est défini dans le fichier `.env` "
                 "(ou dans les *Secrets* de Streamlit Cloud), puis relancez l'application.")
        st.stop()

    budget = barre_laterale(prospection)
    # Titres fixes : si un titre change, Streamlit recrée les onglets et revient au premier.
    onglet1, onglet2 = st.tabs(["🤖 Agent", "✅ Validation"])
    with onglet1:
        onglet_agent(prospection, budget)
    with onglet2:
        validation.onglet_validation(prospection)


main()
