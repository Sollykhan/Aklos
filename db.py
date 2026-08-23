"""
db.py — Fournit un client ChromaDB unique, partagé par tout le processus.

Pourquoi : chat.py et ingest.py créaient chacun leur propre
chromadb.PersistentClient(path=...) pointant sur le même dossier. Tant
qu'ils tournaient dans des processus séparés (CLI, ou 'python ingest.py'
lancé en sous-processus par l'appli graphique), ça ne posait pas de
problème. Mais depuis que l'appli graphique appelle ingest.run_ingest()
directement (nécessaire pour être compatible avec un .exe empaqueté), les
deux tournent dans le MÊME processus Python : créer un second client sur le
même dossier peut alors renvoyer un état interne périmé, qui ne "voit" pas
une collection tout juste créée par le premier client (symptôme observé :
la réindexation réussit, mais l'appli affiche quand même "Base introuvable"
juste après).

Solution : un seul PersistentClient par processus, réutilisé partout.
"""
import os

import chromadb

from paths import base_dir

DB_DIR = os.path.join(base_dir(), "chroma_db")

_client = None


def get_client():
    """Retourne le client ChromaDB du processus, en le créant une seule fois."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=DB_DIR)
    return _client