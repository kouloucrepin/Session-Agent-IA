"""Tests de l'interface avec AppTest : aucun appel à Claude ni à Apify."""
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

DOSSIER_APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DOSSIER_APP))
import moteur  # noqa: E402
import validation  # noqa: E402

CONTACTS = (
    moteur.Contact(id=0, nom="Boulangerie <b>Teranga</b>", telephone="+221 33 000 00 01",
                   message="Bonjour Teranga !", statut=moteur.A_VALIDER),
    moteur.Contact(id=1, nom="Le Pain Doré", telephone="+221 33 000 00 02",
                   message="Bonjour Pain Doré !", statut=moteur.A_VALIDER),
    moteur.Contact(id=2, nom="Sans Téléphone", message="Bonjour", statut=moteur.A_VALIDER),
)


@pytest.fixture
def app(tmp_path, monkeypatch):
    import prospection
    monkeypatch.setattr(prospection, "DOSSIER_DONNEES", tmp_path)
    monkeypatch.setattr(validation, "PAUSE_ENVOI_S", 0)
    at = AppTest.from_file(str(DOSSIER_APP / "app.py"), default_timeout=30)
    at.session_state["contacts"] = CONTACTS
    at.session_state["choisi"] = 0
    return at.run()


def html_page(at) -> str:
    return "".join(m.value for m in at.markdown)


def test_deux_onglets_et_compteur(app):
    assert not app.exception
    assert [t.label for t in app.tabs] == ["🤖 Agent", "✅ Validation"]
    assert "À valider · 3" in html_page(app)


def test_les_noms_externes_sont_echappes(app):
    assert "Boulangerie &lt;b&gt;Teranga&lt;/b&gt;" in html_page(app)
    assert "<b>Teranga</b>" not in html_page(app)


def test_ouvrir_un_contact_affiche_son_message(app):
    app.button(key="ouvrir_1").click().run()
    assert app.session_state["choisi"] == 1
    assert "Bonjour Pain Doré !" in html_page(app)


def test_envoyer_passe_le_contact_au_vert(app, tmp_path):
    app.button(key="ouvrir_1").click().run()
    next(b for b in app.button if b.label == "📤 Envoyer").click().run()

    contact = app.session_state["contacts"][1]
    assert contact.statut == moteur.ENVOYE
    assert app.session_state["vient_envoye"] == 1
    page = html_page(app)
    assert "carte envoye choisie flash" in page
    assert "bulle envoye" in page and "✓✓ Envoyé à" in page
    assert "À valider · 2" in page and "Envoyé · 1" in page
    assert "+221 33 000 00 02 | Bonjour Pain Doré !" in (tmp_path / "envois_simules.log").read_text("utf-8")


def test_refuser_passe_le_contact_au_rouge(app):
    next(b for b in app.button if b.label == "✗ Refuser").click().run()
    assert app.session_state["contacts"][0].statut == moteur.REFUSE
    assert "carte refuse choisie" in html_page(app)


def test_envoi_bloque_sans_telephone(app):
    app.button(key="ouvrir_2").click().run()
    envoyer = next(b for b in app.button if b.label == "📤 Envoyer")
    assert envoyer.disabled
    assert any("pas de numéro" in w.value for w in app.warning)


# --- Onglet Agent (l'agent est remplacé par un faux) ----------------------
@pytest.fixture
def app_vide(monkeypatch):
    appels = []

    def faux_lancer(demande, budget, sur_etape=None, prospection=None):
        appels.append(demande)
        return moteur.Resultat("C'est fait.", CONTACTS[:2], (), 12.5)

    monkeypatch.setattr(moteur, "lancer_agent", faux_lancer)
    at = AppTest.from_file(str(DOSSIER_APP / "app.py"), default_timeout=30).run()
    return at, appels


def test_lancer_l_agent_remplit_la_validation(app_vide):
    at, appels = app_vide
    assert at.text_area[0].value.startswith("Trouve 5 boulangeries")
    next(b for b in at.button if b.label == "🚀 Lancer l'agent").click().run()
    assert appels == [at.text_area[0].value]
    assert len(at.session_state["contacts"]) == 2 and at.session_state["choisi"] == 0
    assert any("C'est fait." in i.value for i in at.info)
    assert any("12.5 FCFA" in c.value for c in at.caption)


def test_choisir_un_exemple_remplace_la_demande(app_vide):
    at, _ = app_vide
    at.selectbox(key="exemple").select_index(1).run()
    assert at.text_area[0].value.startswith("Je cherche 3 pharmacies")


def test_erreur_de_l_agent_est_affichee(app_vide, monkeypatch):
    at, _ = app_vide

    def plante(*a, **k):
        raise RuntimeError("clé invalide")

    monkeypatch.setattr(moteur, "lancer_agent", plante)
    next(b for b in at.button if b.label == "🚀 Lancer l'agent").click().run()
    assert any("clé invalide" in e.value for e in at.error)
