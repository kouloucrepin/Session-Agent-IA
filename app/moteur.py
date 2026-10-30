"""
moteur.py : la logique de l'application, sans aucune interface.

On réutilise la boucle agentique de notebooks/prospection.py et on
« espionne » ses outils pour récupérer les commerces trouvés et les
messages rédigés, afin de les présenter à l'humain pour validation.
"""
import datetime
import hmac
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "notebooks"))

# Statuts possibles d'un contact
A_VALIDER = "a_valider"
ENVOYE = "envoye"
REFUSE = "refuse"
SANS_MESSAGE = "sans_message"

FORMAT_TELEPHONE = re.compile(r"\+221[\d ]{9,13}")
LONGUEUR_MAX_MESSAGE = 600


@dataclass(frozen=True)
class Contact:
    """Un commerce trouvé par l'agent, et le message qui lui est destiné."""
    id: int
    nom: str
    categorie: str = ""
    adresse: str = ""
    telephone: str = ""
    note: float | None = None
    nb_avis: int | None = None
    lien_maps: str = ""
    source: str = ""
    message: str = ""
    statut: str = SANS_MESSAGE
    envoye_le: str = ""


@dataclass(frozen=True)
class Etape:
    """Un appel d'outil fait par l'agent, pour l'afficher en direct."""
    outil: str
    arguments: dict
    erreur: str = ""


@dataclass(frozen=True)
class Resultat:
    reponse: str
    contacts: tuple[Contact, ...]
    etapes: tuple[Etape, ...]
    cout_fcfa: float


# ------------------------------------------------------------------
# Construction des contacts à partir de ce que l'agent a produit
# ------------------------------------------------------------------
def _cle(nom: str) -> str:
    return " ".join((nom or "").lower().split())


def construire_contacts(commerces: list[dict], messages: list[dict]) -> tuple[Contact, ...]:
    """Associe chaque commerce trouvé au message rédigé pour lui (par le nom)."""
    par_nom = {_cle(m.get("commerce", "")): m.get("message", "") for m in messages}
    contacts, deja_vus = [], set()
    for c in commerces:
        cle = _cle(c.get("nom", ""))
        if not cle or cle in deja_vus:
            continue
        deja_vus.add(cle)
        message = par_nom.get(cle, "")
        contacts.append(Contact(
            id=len(contacts),
            nom=c.get("nom") or "",
            categorie=c.get("categorie") or "",
            adresse=c.get("adresse") or "",
            telephone=c.get("telephone") or "",
            note=c.get("note"),
            nb_avis=c.get("nb_avis"),
            lien_maps=c.get("lien_maps") or "",
            source=c.get("source") or "",
            message=message,
            statut=A_VALIDER if message else SANS_MESSAGE,
        ))
    return tuple(contacts)


# ------------------------------------------------------------------
# Lancement de l'agent
# ------------------------------------------------------------------
def lancer_agent(demande: str, budget_fcfa: float,
                 sur_etape: Callable[[Etape], None] | None = None,
                 prospection=None) -> Resultat:
    """Fait tourner l'agent de prospection et récupère commerces et messages."""
    if prospection is None:
        import prospection
    commerces, messages, etapes = [], [], []

    def espionner(nom, fonction, collecte):
        def outil(**arguments):
            etape = Etape(outil=nom, arguments=dict(arguments))
            try:
                sortie = fonction(**arguments)
            except Exception as e:
                etape = replace(etape, erreur=f"{type(e).__name__} : {e}")
                raise
            finally:
                etapes.append(etape)
                if sur_etape:
                    sur_etape(etape)
            collecte(sortie)
            return sortie
        return outil

    fonctions = {
        "rechercher_commerces": espionner("rechercher_commerces", prospection.chercher_commerces,
                                          commerces.extend),
        "rediger_message": espionner("rediger_message", prospection.rediger_message,
                                     messages.append),
    }
    cout_avant = prospection.COMPTEUR.fcfa
    reponse = prospection.agent(demande, fonctions=fonctions,
                                budget_fcfa=budget_fcfa, bavard=False)
    return Resultat(
        reponse=reponse,
        contacts=construire_contacts(commerces, messages),
        etapes=tuple(etapes),
        cout_fcfa=prospection.COMPTEUR.fcfa - cout_avant,
    )


# ------------------------------------------------------------------
# Validation humaine et envoi simulé
# ------------------------------------------------------------------
def verifier_envoi(contact: Contact, texte: str) -> str:
    """Renvoie un message d'erreur, ou une chaîne vide si l'envoi est permis."""
    if contact.statut == ENVOYE:
        return "Ce message a déjà été envoyé."
    if not contact.telephone:
        return "Ce commerce n'a pas de numéro de téléphone."
    if not FORMAT_TELEPHONE.fullmatch(contact.telephone):
        return f"Numéro au mauvais format : {contact.telephone}"
    if not texte.strip():
        return "Le message est vide."
    if len(texte) > LONGUEUR_MAX_MESSAGE:
        return f"Message trop long ({len(texte)} caractères, {LONGUEUR_MAX_MESSAGE} maximum)."
    return ""


def envoyer(contact: Contact, texte: str, fichier_envois: Path,
            maintenant: datetime.datetime | None = None) -> Contact:
    """Envoi SIMULÉ : écrit dans le journal des envois et renvoie le contact mis à jour."""
    erreur = verifier_envoi(contact, texte)
    if erreur:
        raise ValueError(erreur)
    maintenant = maintenant or datetime.datetime.now()
    ligne = " ".join(texte.split())
    fichier_envois.parent.mkdir(parents=True, exist_ok=True)
    with open(fichier_envois, "a", encoding="utf-8") as f:
        f.write(f"{maintenant:%Y-%m-%d %H:%M} | {contact.telephone} | {ligne}\n")
    # Ici, en vrai : l'appel à l'API WhatsApp Business ou à un service SMS
    return replace(contact, message=texte, statut=ENVOYE, envoye_le=f"{maintenant:%H:%M}")


def nouveau_message(contact: Contact, texte: str) -> Contact:
    """Remplace le brouillon (après une nouvelle rédaction) et le remet à valider."""
    if contact.statut == ENVOYE:
        raise ValueError("Impossible de modifier un message déjà envoyé.")
    return replace(contact, message=texte.strip(), statut=A_VALIDER)


def refuser(contact: Contact) -> Contact:
    if contact.statut == ENVOYE:
        raise ValueError("Impossible de refuser un message déjà envoyé.")
    return replace(contact, statut=REFUSE)


def remplacer(contacts: tuple[Contact, ...], nouveau: Contact) -> tuple[Contact, ...]:
    """Renvoie une nouvelle liste où le contact de même id est remplacé."""
    return tuple(nouveau if c.id == nouveau.id else c for c in contacts)


def variables_depuis_secrets(secrets: Mapping, environ: Mapping) -> dict[str, str]:
    """Variables à ajouter à l'environnement depuis les secrets Streamlit Cloud.

    Seules les valeurs simples sont gardées (pas les sections), et une variable
    déjà définie (par exemple dans .env) n'est jamais écrasée.
    """
    return {nom: str(valeur) for nom, valeur in secrets.items()
            if isinstance(valeur, (str, int, float)) and nom not in environ}


def mot_de_passe_correct(saisi: str, attendu: str) -> bool:
    return bool(saisi) and hmac.compare_digest(saisi.encode(), attendu.encode())
