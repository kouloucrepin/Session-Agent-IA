"""Tests du moteur : aucun appel réseau, l'agent est remplacé par un faux."""
import datetime
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import moteur  # noqa: E402
from moteur import A_VALIDER, ENVOYE, REFUSE, SANS_MESSAGE, Contact  # noqa: E402

COMMERCES = [
    {"nom": "Boulangerie Teranga", "categorie": "Boulangerie", "telephone": "+221 33 000 00 01"},
    {"nom": "Le Pain Doré", "categorie": "Boulangerie", "telephone": "+221 33 000 00 02"},
]


def faux_prospection(commerces=COMMERCES, plante=False):
    """Imite prospection.py : l'agent appelle les deux outils comme le ferait Claude."""
    compteur = SimpleNamespace(fcfa=10.0)

    def chercher_commerces(activite, zone, nombre=5):
        if plante:
            raise RuntimeError("Apify indisponible")
        return commerces[:nombre]

    def rediger_message(nom_commerce, activite="", ton="chaleureux"):
        return {"commerce": nom_commerce, "message": f"Bonjour {nom_commerce} !"}

    def agent(demande, fonctions, budget_fcfa, bavard):
        try:
            trouves = fonctions["rechercher_commerces"](activite="boulangerie", zone="Plateau")
        except RuntimeError:
            return "Recherche impossible."
        fonctions["rediger_message"](nom_commerce=trouves[0]["nom"])
        compteur.fcfa += 4.5
        return "Terminé."

    return SimpleNamespace(chercher_commerces=chercher_commerces, rediger_message=rediger_message,
                           agent=agent, COMPTEUR=compteur)


def contact(**champs):
    base = dict(id=0, nom="Boulangerie Teranga", telephone="+221 33 000 00 01",
                message="Bonjour !", statut=A_VALIDER)
    return Contact(**{**base, **champs})


# --- construire_contacts --------------------------------------------------
def test_associe_message_au_commerce_sans_tenir_compte_de_la_casse():
    contacts = moteur.construire_contacts(
        COMMERCES, [{"commerce": "boulangerie  TERANGA", "message": "Salut"}])
    assert contacts[0].message == "Salut" and contacts[0].statut == A_VALIDER
    assert contacts[1].message == "" and contacts[1].statut == SANS_MESSAGE


def test_ignore_les_doublons_et_les_commerces_sans_nom():
    contacts = moteur.construire_contacts(COMMERCES + [COMMERCES[0], {"nom": None}], [])
    assert [c.nom for c in contacts] == ["Boulangerie Teranga", "Le Pain Doré"]
    assert [c.id for c in contacts] == [0, 1]


# --- lancer_agent ---------------------------------------------------------
def test_lancer_agent_recupere_contacts_etapes_et_cout():
    vues = []
    resultat = moteur.lancer_agent("boulangeries au Plateau", 500, sur_etape=vues.append,
                                   prospection=faux_prospection())
    assert resultat.reponse == "Terminé."
    assert len(resultat.contacts) == 2
    assert resultat.contacts[0].message == "Bonjour Boulangerie Teranga !"
    assert [e.outil for e in resultat.etapes] == ["rechercher_commerces", "rediger_message"]
    assert vues == list(resultat.etapes)
    assert resultat.cout_fcfa == pytest.approx(4.5)


def test_lancer_agent_note_l_erreur_d_un_outil():
    resultat = moteur.lancer_agent("x", 500, prospection=faux_prospection(plante=True))
    assert resultat.contacts == ()
    assert "Apify indisponible" in resultat.etapes[0].erreur


# --- verifier_envoi / envoyer / refuser -----------------------------------
@pytest.mark.parametrize("champs, texte, attendu", [
    ({"statut": ENVOYE}, "ok", "déjà été envoyé"),
    ({"telephone": ""}, "ok", "pas de numéro"),
    ({"telephone": "77 123 45 67"}, "ok", "mauvais format"),
    ({}, "   ", "vide"),
    ({}, "x" * 601, "trop long"),
])
def test_verifier_envoi_refuse_les_cas_dangereux(champs, texte, attendu):
    assert attendu in moteur.verifier_envoi(contact(**champs), texte)


def test_envoyer_ecrit_le_journal_et_passe_au_vert(tmp_path):
    fichier = tmp_path / "envois.log"
    original = contact()
    envoye = moteur.envoyer(original, "Bonjour\nà vous", fichier,
                            maintenant=datetime.datetime(2026, 10, 30, 9, 15))
    assert envoye.statut == ENVOYE and envoye.envoye_le == "09:15"
    assert envoye.message == "Bonjour\nà vous"
    assert original.statut == A_VALIDER  # l'original n'est pas modifié
    assert fichier.read_text(encoding="utf-8") == \
        "2026-10-30 09:15 | +221 33 000 00 01 | Bonjour à vous\n"


def test_envoyer_leve_une_erreur_si_invalide(tmp_path):
    with pytest.raises(ValueError, match="pas de numéro"):
        moteur.envoyer(contact(telephone=""), "Bonjour", tmp_path / "envois.log")
    assert not (tmp_path / "envois.log").exists()


def test_refuser():
    assert moteur.refuser(contact()).statut == REFUSE
    with pytest.raises(ValueError):
        moteur.refuser(contact(statut=ENVOYE))


def test_nouveau_message_remet_a_valider():
    assert moteur.nouveau_message(contact(statut=REFUSE), " Salut ").message == "Salut"
    assert moteur.nouveau_message(contact(statut=SANS_MESSAGE), "Salut").statut == A_VALIDER
    with pytest.raises(ValueError):
        moteur.nouveau_message(contact(statut=ENVOYE), "Salut")


def test_remplacer_renvoie_une_nouvelle_liste():
    contacts = (contact(id=0), contact(id=1, nom="Autre"))
    nouveaux = moteur.remplacer(contacts, contact(id=1, nom="Changé"))
    assert [c.nom for c in nouveaux] == ["Boulangerie Teranga", "Changé"]
    assert contacts[1].nom == "Autre"


def test_variables_depuis_secrets_garde_les_textes_simples():
    secrets = {"ANTHROPIC_API_KEY": "cle", "BUDGET_MAX_FCFA": 300, "section": {"a": 1}}
    assert moteur.variables_depuis_secrets(secrets, {}) == {"ANTHROPIC_API_KEY": "cle",
                                                             "BUDGET_MAX_FCFA": "300"}


def test_variables_depuis_secrets_ne_remplace_pas_l_environnement():
    secrets = {"MODELE": "secret", "APIFY_TOKEN": "jeton"}
    assert moteur.variables_depuis_secrets(secrets, {"MODELE": "local"}) == {"APIFY_TOKEN": "jeton"}


def test_mot_de_passe_correct():
    assert moteur.mot_de_passe_correct("atelier", "atelier")
    assert not moteur.mot_de_passe_correct("mauvais", "atelier")
    assert not moteur.mot_de_passe_correct("", "atelier")
