"""
ingest.py — Lit les fichiers texte/markdown du dossier data/, les découpe en
petits morceaux (chunks), génère leurs embeddings via Ollama (nomic-embed-text)
et les stocke dans une base vectorielle ChromaDB locale (./chroma_db).

Réindexation INCRÉMENTALE : seuls les fichiers nouveaux ou modifiés depuis la
dernière fois sont ré-embeddés (comparaison par hash du contenu, mémorisé
dans index_state.json). Les fichiers inchangés ne sont pas retouchés, et les
fichiers supprimés de data/ voient leurs chunks nettoyés de la base. Sur un
CPU sans GPU, chaque embedding coûte un appel Ollama : sans ça, plus data/
grossit, plus CHAQUE réindexation (même pour une seule ligne ajoutée) serait
aussi longue que la toute première.

Usage :
    python ingest.py
"""

import os
import glob
import hashlib
import json
import ollama

from paths import base_dir
from db import get_client, DB_DIR  # client ChromaDB partagé (voir db.py)

DATA_DIR = os.path.join(base_dir(), "data")
COLLECTION_NAME = "jarvis_memory"
INDEX_STATE_PATH = os.path.join(base_dir(), "index_state.json")

EMBED_MODEL = "nomic-embed-text"

CHUNK_SIZE = 800       # caractères par chunk
CHUNK_OVERLAP = 150    # chevauchement entre chunks consécutifs


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Découpe un texte en chunks de taille ~chunk_size avec un léger overlap,
    en essayant de couper sur des sauts de paragraphe quand c'est possible."""
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            # Si un paragraphe seul dépasse déjà chunk_size, on le découpe brut
            if len(para) > chunk_size:
                for i in range(0, len(para), chunk_size - overlap):
                    chunks.append(para[i:i + chunk_size])
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


def load_documents():
    patterns = ["*.md", "*.txt"]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(DATA_DIR, "**", pattern), recursive=True))
    return sorted(set(files))


def _file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load_state() -> dict:
    """Charge {chemin_relatif: hash} de la dernière indexation. Fichier
    absent ou corrompu -> tout est traité comme neuf (comportement sûr)."""
    if os.path.isfile(INDEX_STATE_PATH):
        try:
            with open(INDEX_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_state(state: dict):
    with open(INDEX_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def run_ingest(on_progress=None):
    """Réindexe data/ dans ChromaDB de façon incrémentale. Exposée comme
    fonction réutilisable (ex: chat.py l'appelle pour 'apprend >' / 'oublie >').

    Si on_progress est fourni, chaque ligne de statut lui est passée au lieu
    d'être imprimée (utilisé par l'appli graphique pour afficher la
    progression en direct dans la fenêtre plutôt qu'un silence jusqu'à la
    toute fin)."""
    def emit(msg):
        if on_progress:
            on_progress(msg)
        else:
            print(msg)

    if not os.path.isdir(DATA_DIR):
        emit(f"Dossier introuvable : {DATA_DIR}")
        emit("Crée un dossier 'data/' avec tes fichiers .md ou .txt dedans.")
        return

    files = load_documents()
    old_state = _load_state()

    client = get_client()
    # get_or_create : ne wipe plus la collection à chaque appel, indispensable
    # pour que le principe "on ne retouche que ce qui a changé" ait un sens.
    collection = client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    if not files:
        emit(f"Aucun fichier .md/.txt trouvé dans {DATA_DIR}.")
        # Si data/ a été entièrement vidé, on nettoie quand même les chunks
        # des anciens fichiers qui n'existent plus.
        for rel in old_state:
            collection.delete(where={"source": rel})
        _save_state({})
        return

    emit(f"{len(files)} fichier(s) trouvé(s). Vérification des changements...")

    new_state = {}
    current_rels = set()
    updated = 0
    unchanged = 0
    total_chunks = 0

    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        rel = os.path.relpath(filepath, DATA_DIR)
        current_rels.add(rel)
        file_hash = _file_hash(content)
        new_state[rel] = file_hash

        if old_state.get(rel) == file_hash:
            unchanged += 1
            continue  # contenu identique à la dernière indexation : on saute

        # Premier segment du chemin relatif = dossier de premier niveau dans
        # data/ (ex: "Cybfs-ft-17" pour data/Cybfs-ft-17/semaine 1/xxx.md),
        # ou "" si le fichier est directement à la racine de data/. Sert au
        # scope par dossier (voir FOLDER_SCOPES dans chat.py).
        parts = rel.split(os.sep)
        folder = parts[0] if len(parts) > 1 else ""

        # On retire les anciens chunks de CE fichier avant de le refaire
        # (no-op silencieux si c'est un nouveau fichier).
        collection.delete(where={"source": rel})

        chunks = chunk_text(content)
        for i, chunk in enumerate(chunks):
            embedding = ollama.embeddings(model=EMBED_MODEL, prompt=chunk)["embedding"]
            collection.add(
                ids=[f"{rel}::{i}"],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{"source": rel, "folder": folder}],
            )
            total_chunks += 1

        updated += 1
        emit(f"  - {rel} : {len(chunks)} chunk(s) (mis à jour)")

    # Fichiers supprimés de data/ depuis la dernière indexation : on retire
    # leurs chunks devenus orphelins de la base.
    removed_rels = set(old_state) - current_rels
    for rel in removed_rels:
        collection.delete(where={"source": rel})
    if removed_rels:
        emit(f"  - {len(removed_rels)} fichier(s) supprimé(s) nettoyé(s) de la base")

    _save_state(new_state)

    emit(
        f"\nTerminé : {updated} fichier(s) mis à jour ({total_chunks} chunks), "
        f"{unchanged} fichier(s) inchangé(s) ignoré(s), dans {DB_DIR}"
    )


def main():
    run_ingest()


if __name__ == "__main__":
    main()