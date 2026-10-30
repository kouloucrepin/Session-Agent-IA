# 🤖 Session Agent IA : construire un agent de prospection avec Claude

Atelier pratique en **4 notebooks Jupyter** pour apprendre à concevoir, sécuriser et orchestrer des **agents IA** avec l'API Anthropic (Claude), Apify, LangGraph et CrewAI.

> **Fil rouge** : un **agent de prospection** qui cherche des commerces sur Google Maps (via Apify), rédige des messages d'approche personnalisés et **demande votre accord avant tout envoi**.

---

## 📑 Sommaire

- [Objectifs pédagogiques](#-objectifs-pédagogiques)
- [Structure du dépôt](#-structure-du-dépôt)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Configuration (`.env`)](#-configuration-env)
- [Parcours de l'atelier](#-parcours-de-latelier)
- [Bonus : serveur MCP](#-bonus--serveur-mcp)
- [Dépannage](#-dépannage)
- [Sécurité](#-sécurité)

---

## 🎯 Objectifs pédagogiques

À la fin de l'atelier, vous saurez :

- appeler un LLM, mesurer les **tokens** et estimer le **coût en FCFA** ;
- obtenir des **sorties structurées** fiables (JSON validé par Pydantic) ;
- donner des **outils** à un modèle (function calling) et écrire une **boucle agentique** ;
- protéger un agent : **validation humaine**, défense contre l'**injection de prompt**, **budget**, **journalisation** et **évaluation** ;
- structurer des applications agentiques avec **LangGraph**, **CrewAI**, un **superviseur multi-agents**, ainsi que les protocoles **MCP** et **A2A**.

---

## 📁 Structure du dépôt

```
Session-Agent-IA/
├── Atelier_Agents_IA.pptx          ← support de présentation de l'atelier
├── .env.example                    ← modèle de configuration (à copier en .env)
├── requirements.txt                ← dépendances Python
├── README.md
└── notebooks/
    ├── 01_Fondations_LLM_et_JSON.ipynb
    ├── 02_Outils_et_boucle_agentique.ipynb
    ├── 03_Garde_fous_et_evaluation.ipynb
    ├── 04_LangGraph_CrewAI_multi_agents.ipynb
    ├── prospection.py              ← boîte à outils partagée (construite au notebook 02)
    └── serveur_mcp_prospection.py  ← serveur MCP exposant la recherche de commerces
```

Le dossier `donnees/` (cache Apify, journal des décisions, envois simulés) est **créé automatiquement** à l'exécution et n'est pas versionné.

---

## ✅ Prérequis

| Élément | Détail |
|---|---|
| Python | 3.10 ou plus récent ([télécharger](https://www.python.org/downloads/)) |
| Clé Anthropic | **Obligatoire** : [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) |
| Jeton Apify | **Recommandé** : [console.apify.com](https://console.apify.com) → *Settings → API & Integrations* |

> Sans jeton Apify, les notebooks fonctionnent avec des **commerces fictifs de démonstration**.

---

## ⚙️ Installation

```bash
# 1. Cloner le dépôt
git clone https://github.com/kouloucrepin/Session-Agent-IA.git
cd Session-Agent-IA

# 2. Créer et activer un environnement virtuel
python -m venv .venv
# Windows :        .venv\Scripts\activate
# macOS / Linux :  source .venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Créer votre fichier de configuration
cp .env.example .env        # Windows : copy .env.example .env

# 5. Lancer Jupyter
jupyter notebook
```

Ouvrez ensuite `notebooks/01_Fondations_LLM_et_JSON.ipynb`.

---

## 🔑 Configuration (`.env`)

| Variable | Rôle | Valeur par défaut |
|---|---|---|
| `ANTHROPIC_API_KEY` | Clé API Anthropic | *(obligatoire)* |
| `APIFY_TOKEN` | Jeton Apify pour Google Maps | *(vide = mode démo)* |
| `MODELE` | Modèle principal | `claude-sonnet-5-5` |
| `MODELE_RAPIDE` | Modèle rapide / économique | `claude-haiku-5-5` |
| `APIFY_ACTEUR` | Acteur Apify utilisé | `compass/crawler-google-places` |
| `PRIX_ENTREE_USD` / `PRIX_SORTIE_USD` | Prix par million de tokens (USD) | `3` / `15` |
| `TAUX_USD_FCFA` | Taux de conversion | `600` |
| `BUDGET_MAX_FCFA` | Plafond de dépense d'un agent | `500` |

---

## 🗺️ Parcours de l'atelier

Suivez les notebooks **dans l'ordre** : chacun s'appuie sur le précédent.

| # | Notebook | Durée | Contenu |
|---|---|---|---|
| 01 | **Fondations + JSON** | 40 min | Premier appel, tokens et coût en FCFA, température, absence de mémoire, chatbot vs workflow vs agent, sorties structurées avec Pydantic |
| 02 | **Outils et boucle agentique** | 1 h 10 | Recherche Google Maps via Apify, JSON Schema, function calling, boucle agentique complète, gestion des erreurs d'outils, RAG, MCP |
| 03 | **Garde-fous et évaluation** | 35 min | Validation humaine des actions sensibles, injection de prompt (attaque et défense), budget, journal des décisions, évaluation de l'agent |
| 04 | **Frameworks et architectures** | 40 min | LangGraph (workflow, pause/reprise, agent en graphe), CrewAI, superviseur multi-agents, protocole A2A |

**Durée totale : environ 3 h 05.**

---

## 🔌 Bonus : serveur MCP

`notebooks/serveur_mcp_prospection.py` expose l'outil `rechercher_commerces` via le **Model Context Protocol**, pour l'utiliser depuis un assistant compatible (Claude Desktop, Claude Code…) :

```bash
cd notebooks
python serveur_mcp_prospection.py
```

---

## 🛠️ Dépannage

| Symptôme | Solution |
|---|---|
| `AuthenticationError` | Clé Anthropic absente ou erronée dans `.env`. Corrigez puis *Kernel → Restart*. |
| `ModuleNotFoundError` | Relancez `pip install -r requirements.txt` dans le bon environnement. |
| Commerces marqués « (démo) » | `APIFY_TOKEN` est vide : ajoutez-le pour obtenir de vraies données. |
| Apify est lent | Normal : une recherche prend 20 à 60 s. Les résultats sont ensuite mis en cache. |
| `NotFoundError` sur le modèle | Vérifiez `MODELE` et `MODELE_RAPIDE` dans `.env`. |

---

## 🔒 Sécurité

- Ne publiez **jamais** votre fichier `.env` (il est exclu par `.gitignore`).
- Fixez un **plafond de dépense** sur vos comptes Anthropic et Apify.
- Les envois de messages sont **simulés** : rien n'est réellement envoyé.
- Les numéros de démonstration sont fictifs.
