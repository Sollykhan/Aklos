"""
paths.py — Détermine le dossier de base d'Aklos (là où se trouvent data/,
chroma_db/ et backups/), que le programme tourne depuis les sources Python
ou depuis un .exe empaqueté (PyInstaller).

En mode normal, ce dossier est celui où se trouve ce fichier .py (le
dossier du projet). Une fois empaqueté en .exe (PyInstaller --onefile), le
code s'exécute depuis un dossier temporaire qui est supprimé à la
fermeture : il faut alors utiliser le dossier où se trouve l'exécutable
lui-même, sinon data/ et chroma_db/ seraient recréés vides à chaque lancement.
"""
import os
import sys


def base_dir() -> str:
    """Dossier où doivent vivre data/, chroma_db/ et backups/."""
    if getattr(sys, "frozen", False):
        # Application empaquetée (PyInstaller) : dossier de l'exécutable.
        return os.path.dirname(sys.executable)
    # Exécution normale depuis les sources : dossier du projet.
    return os.path.dirname(os.path.abspath(__file__))