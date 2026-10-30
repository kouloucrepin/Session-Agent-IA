"""
validation.py : l'onglet où l'humain relit, corrige et envoie les messages.

Couleurs : orange = à valider, vert = envoyé, rouge = refusé, gris = sans message.
"""
import html
import time

import streamlit as st

import moteur

LIBELLES = {
    moteur.A_VALIDER: "À valider",
    moteur.ENVOYE: "Envoyé",
    moteur.REFUSE: "Refusé",
    moteur.SANS_MESSAGE: "Sans message",
}
COULEURS = {
    moteur.A_VALIDER: "var(--a-valider)",
    moteur.ENVOYE: "var(--envoye)",
    moteur.REFUSE: "var(--refuse)",
    moteur.SANS_MESSAGE: "var(--sans)",
}
PAUSE_ENVOI_S = 0.8  # petit délai pour « voir » l'envoi se faire


def _e(texte) -> str:
    """Échappe les données externes (Google Maps) avant de les mettre en HTML."""
    return html.escape(str(texte or ""))


def _remplacer(nouveau: moteur.Contact):
    st.session_state.contacts = moteur.remplacer(st.session_state.contacts, nouveau)


def _compteurs(contacts):
    pastilles = "".join(
        f"<span style='--couleur:{COULEURS[s]}'>{LIBELLES[s]} · "
        f"{sum(c.statut == s for c in contacts)}</span>"
        for s in LIBELLES)
    st.markdown(f"<div class='compteurs'>{pastilles}</div>", unsafe_allow_html=True)


def _carte(contact: moteur.Contact):
    classes = [contact.statut]
    if contact.id == st.session_state.choisi:
        classes.append("choisie")
    if contact.id == st.session_state.vient_envoye:
        classes.append("flash")
    note = f"⭐ {contact.note}" if contact.note else ""
    st.markdown(
        f"<div class='carte {' '.join(classes)}'>"
        f"<span class='pastille'>{LIBELLES[contact.statut]}</span>"
        f"<div class='nom'>{_e(contact.nom)}</div>"
        f"<div class='meta'>{_e(contact.telephone) or 'pas de téléphone'} {note}</div></div>",
        unsafe_allow_html=True)
    if st.button("Ouvrir", key=f"ouvrir_{contact.id}", use_container_width=True,
                 type="primary" if contact.id == st.session_state.choisi else "secondary"):
        st.session_state.choisi = contact.id
        st.session_state.vient_envoye = None
        st.rerun()


def _fiche(contact: moteur.Contact):
    lien = (f"<p class='ligne'>🗺️ <a href='{_e(contact.lien_maps)}' target='_blank' "
            f"rel='noopener'>Voir sur Google Maps</a></p>") if contact.lien_maps.startswith("https://") else ""
    avis = f" · {contact.nb_avis} avis" if contact.nb_avis else ""
    st.markdown(
        f"<div class='fiche'><h3>{_e(contact.nom)}</h3>"
        f"<p class='ligne'>🏷️ {_e(contact.categorie)} · ⭐ {_e(contact.note) or '–'}{avis}</p>"
        f"<p class='ligne'>📍 {_e(contact.adresse) or 'adresse inconnue'}</p>"
        f"<p class='ligne'>📞 {_e(contact.telephone) or 'pas de téléphone'}</p>{lien}"
        f"<p class='ligne'>Source : {_e(contact.source)}</p></div>",
        unsafe_allow_html=True)


def _bulle(contact: moteur.Contact):
    heure = {
        moteur.ENVOYE: f"✓✓ Envoyé à {contact.envoye_le}",
        moteur.REFUSE: "✗ Refusé",
    }.get(contact.statut, "Brouillon · en attente de votre accord")
    st.markdown(
        f"<div class='telephone'><div class='bulle {contact.statut}'>{_e(contact.message)}"
        f"<span class='heure'>{heure}</span></div></div>", unsafe_allow_html=True)


def _regenerer(prospection, contact: moteur.Contact, ton: str):
    with st.spinner("Rédaction d'un nouveau message…"):
        try:
            sortie = prospection.rediger_message(contact.nom, contact.categorie, ton)
        except Exception as e:
            st.error(f"Rédaction impossible : {e}")
            return
    _remplacer(moteur.nouveau_message(contact, sortie["message"]))
    st.rerun()


def _envoyer(contact: moteur.Contact, texte: str, prospection):
    fichier = prospection.DOSSIER_DONNEES / "envois_simules.log"
    with st.spinner(f"Envoi à {contact.telephone}…"):
        time.sleep(PAUSE_ENVOI_S)
        try:
            envoye = moteur.envoyer(contact, texte, fichier)
        except (ValueError, OSError) as e:
            st.error(str(e))
            return
    _remplacer(envoye)
    st.session_state.vient_envoye = contact.id
    st.toast(f"Message envoyé à {contact.nom}", icon="✅")
    st.rerun()


def _actions(prospection, contact: moteur.Contact):
    if contact.statut == moteur.ENVOYE:
        st.success(f"Message envoyé à {contact.envoye_le} (simulation).")
        return
    texte = st.text_area("Message (modifiable avant envoi)", value=contact.message, height=150,
                         key=f"texte_{contact.id}_{hash(contact.message)}")
    st.caption(f"{len(texte)} / {moteur.LONGUEUR_MAX_MESSAGE} caractères")
    erreur = moteur.verifier_envoi(contact, texte)
    if erreur and texte.strip():
        st.warning(erreur)

    col1, col2, col3 = st.columns([1.3, 1, 1.4])
    if col1.button("📤 Envoyer", type="primary", use_container_width=True, disabled=bool(erreur)):
        _envoyer(contact, texte, prospection)
    if col2.button("✗ Refuser", use_container_width=True, disabled=contact.statut == moteur.REFUSE):
        _remplacer(moteur.refuser(contact))
        st.rerun()
    with col3.popover("🔄 Régénérer", use_container_width=True):
        ton = st.radio("Ton", ["chaleureux", "formel", "direct"], horizontal=True,
                       key=f"ton_{contact.id}")
        if st.button("Rédiger à nouveau", key=f"regen_{contact.id}"):
            _regenerer(prospection, contact, ton)


def onglet_validation(prospection):
    contacts = st.session_state.contacts
    if not contacts:
        st.markdown("<div class='vide'>Aucun contact pour l'instant.<br>"
                    "Lancez l'agent dans l'onglet <b>🤖 Agent</b>.</div>", unsafe_allow_html=True)
        return

    _compteurs(contacts)
    gauche, droite = st.columns([1, 1.6], gap="large")
    with gauche:
        st.markdown("##### Contacts trouvés")
        for contact in contacts:
            _carte(contact)
    with droite:
        contact = next((c for c in contacts if c.id == st.session_state.choisi), contacts[0])
        _fiche(contact)
        if contact.message:
            _bulle(contact)
        else:
            st.info("L'agent n'a pas rédigé de message pour ce commerce : utilisez **🔄 Régénérer**.")
        _actions(prospection, contact)
