# Jarvis RAG — assistant personnel local

Petit projet RAG (Retrieval-Augmented Generation) 100% local, pensé pour
tourner sur un PC sans GPU dédié (16 Go de RAM, CPU seul). Objectif :
construire un assistant qui te connaît, sans dépendre d'un cloud tiers ni
d'un fine-tuning lourd.

## Comment ça marche

1. Tu mets tes fichiers texte (notes, journal, exports de conversations...)
   dans le dossier `data/`.
2. `ingest.py` découpe ces fichiers en petits morceaux, calcule leurs
   embeddings avec Ollama, et les stocke dans une base vectorielle locale
   (ChromaDB, dossier `chroma_db/`).
3. `chat.py` prend ta question, retrouve les passages les plus pertinents
   dans cette base, et les donne comme contexte au modèle de chat
   (llama3.2:3b) pour qu'il réponde en connaissance de cause.

Rien ne sort de ta machine : modèle, embeddings et base de données tournent
tous en local.

## Installation (Windows)

### 1. Installer Ollama

Télécharge et installe Ollama pour Windows :
https://ollama.com/download/windows

Une fois installé, Ollama tourne en tâche de fond (icône dans la barre des
tâches) et expose une API locale sur `http://localhost:11434`.

### 2. Télécharger les modèles

Ouvre un terminal (PowerShell ou l'invite de commandes) et lance :

```
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

Le premier est le modèle de chat (~2 Go), le second sert à générer les
embeddings (~275 Mo). Les deux tournent bien en CPU only sur ton Core 7 150U
avec 16 Go de RAM.

### 3. Installer les dépendances Python

D'abord, il faut se placer dans le dossier du projet (celui qui contient
`ingest.py`, `chat.py`, `requirements.txt`...).

- Si tu as reçu ce dossier via Claude/Cowork, regarde dans le panneau des
  fichiers de l'application (ou dans ton dossier de téléchargements) : le
  dossier s'appelle `jarvis-rag`. Fais un clic droit dessus → "Copier
  l'emplacement" pour récupérer son chemin complet, ou note simplement où
  il se trouve.
- Comme tu travailles déjà dans `C:\Users\solka\dev`, le plus simple est de
  déplacer (ou copier-coller) tout le dossier `jarvis-rag` à cet endroit,
  pour l'avoir directement sous la main.

Une fois le dossier repéré, ouvre PowerShell et déplace-toi dedans avec
`cd`, par exemple :

```
cd C:\Users\solka\dev\jarvis-rag
```

Puis installe les dépendances :

```
pip install -r requirements.txt
```

(Python 3.9+ recommandé. Si `pip` n'est pas reconnu, utilise `py -m pip
install -r requirements.txt`.)

Astuce : `ingest.py` et `chat.py` doivent être lancés depuis ce même
dossier (ou en connaissant leur chemin complet), sinon Python ne les
trouvera pas.

## Utilisation

1. Ajoute tes documents dans `data/` (fichiers `.md` ou `.txt`). Un fichier
   `data/moi.md` est déjà présent pour amorcer la base.
2. Indexe les documents :

   ```
   python ingest.py
   ```

3. Lance le chat :

   ```
   python chat.py
   ```

4. Pose tes questions. Tape `exit` pour quitter.

Chaque fois que tu ajoutes ou modifies des fichiers dans `data/`, relance
`ingest.py` pour mettre la base à jour.

## Faire grandir la base de connaissances

Quelques pistes pour enrichir `data/` avec de vraies infos sur toi :

- Exporter tes conversations Claude : Paramètres du compte → Confidentialité
  → Exporter les données. Une fois reçu, dépose les fichiers texte extraits
  dans `data/`.
- Ajouter tes notes personnelles, journal, listes de préférences, projets
  en cours, etc. — un fichier par thème est plus facile à gérer qu'un
  énorme fichier unique.

## Limites à avoir en tête

- Pas de GPU dédié : la génération sera plus lente qu'avec une carte
  graphique, mais un modèle 3B reste tout à fait utilisable en usage
  interactif sur ce PC.
- Ce projet fait du RAG, pas du fine-tuning : la "personnalité" vient du
  contexte injecté (prompt système + documents récupérés), pas des poids du
  modèle. C'est délibéré — c'est l'approche la plus efficace et la plus
  réaliste sur ce matériel.
- `ingest.py` réindexe toute la base à chaque exécution (simple mais pas
  incrémental). Suffisant pour un usage perso avec quelques dizaines de
  fichiers.

## Pour aller plus loin

- Essayer un autre modèle de chat (`qwen2.5:3b`, `phi4-mini` selon
  disponibilité dans `ollama pull`) en changeant `CHAT_MODEL` dans
  `chat.py`.
- Ajouter une interface web légère (ex. Streamlit) par-dessus `chat.py`.
- Explorer le fine-tuning LoRA en complément, une fois le RAG bien en main,
  pour ajuster le ton/style du modèle plutôt que ses connaissances.
