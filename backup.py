"""
backup.py — Sauvegarde le dossier data/ (tes infos perso, ta famille, ton
livre) dans une archive zip horodatée, dans jarvis-rag/backups/.

- Garde les MAX_BACKUPS sauvegardes locales les plus récentes (les plus
  anciennes sont supprimées automatiquement).
- Copie aussi la sauvegarde vers SECONDARY_BACKUP_DIR si ce dossier est
  configuré et accessible (par défaut : ton OneDrive, pour une copie hors
  du disque local — vérifie/adapte le chemin si besoin). Mets la variable
  à None pour désactiver.

Pas besoin de sauvegarder chroma_db/ : il est entièrement régénéré par
ingest.py à partir de data/.

Pour restaurer une sauvegarde : dézippe le fichier voulu dans backups/ par
dessus le dossier data/, puis relance `python ingest.py`.

Usage :
    python backup.py
"""
import os
import glob
import shutil
import zipfile
import datetime

from paths import base_dir

BASE_DIR = base_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

MAX_BACKUPS = 10  # nombre de sauvegardes locales conservées

# Dossier secondaire optionnel (copie hors disque local). Mets None pour désactiver.
# Silencieusement ignoré si ce chemin n'existe pas sur la machine (ex: partagé
# avec quelqu'un qui n'a pas ce OneDrive) — voir copy_to_secondary() ci-dessous.
SECONDARY_BACKUP_DIR = r"C:\Users\solka\OneDrive\AklosBackups"


def create_backup() -> str:
    """Crée une archive zip horodatée de data/ et retourne son chemin."""
    if not os.path.isdir(DATA_DIR):
        raise FileNotFoundError(f"Dossier introuvable : {DATA_DIR}")

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    zip_path = os.path.join(BACKUP_DIR, f"aklos_data_{timestamp}.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filepath in glob.glob(os.path.join(DATA_DIR, "**", "*"), recursive=True):
            if os.path.isfile(filepath):
                arcname = os.path.relpath(filepath, DATA_DIR)
                zf.write(filepath, arcname)

    return zip_path


def cleanup_old_backups():
    """Ne garde que les MAX_BACKUPS sauvegardes locales les plus récentes."""
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "aklos_data_*.zip")))
    excess = len(backups) - MAX_BACKUPS
    for old in backups[:max(excess, 0)]:
        os.remove(old)


def copy_to_secondary(zip_path: str) -> bool:
    """Copie la sauvegarde vers SECONDARY_BACKUP_DIR si configuré et accessible."""
    if not SECONDARY_BACKUP_DIR:
        return False
    parent = os.path.dirname(SECONDARY_BACKUP_DIR.rstrip("\\/"))
    if not os.path.isdir(parent):
        return False  # ex: dossier OneDrive introuvable sur cette machine
    os.makedirs(SECONDARY_BACKUP_DIR, exist_ok=True)
    shutil.copy2(zip_path, SECONDARY_BACKUP_DIR)
    return True


def needs_backup(max_age_hours: int = 24) -> bool:
    """Indique si la dernière sauvegarde locale date de plus de max_age_hours
    (ou s'il n'y en a aucune). Utilisé pour la sauvegarde automatique."""
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "aklos_data_*.zip")))
    if not backups:
        return True
    age_hours = (datetime.datetime.now().timestamp() - os.path.getmtime(backups[-1])) / 3600
    return age_hours >= max_age_hours


def run_backup() -> str:
    """Sauvegarde complète : zip + nettoyage + copie secondaire. Retourne un message."""
    zip_path = create_backup()
    cleanup_old_backups()
    copied = copy_to_secondary(zip_path)

    msg = f"Sauvegarde créée : {os.path.basename(zip_path)}"
    if copied:
        msg += f" (copiée aussi dans {SECONDARY_BACKUP_DIR})"
    return msg


def main():
    print(run_backup())


if __name__ == "__main__":
    main()