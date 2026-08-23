"""
normalize_data.py — Passe une fois sur tous les fichiers data/*.md pour :
- uniformiser les dates existantes au format JJ/MM/AAAA (voir dates.py)
- convertir mon/ma/mes en ton/ta/tes (voir person.py)
Fait une sauvegarde .bak avant d'écraser chaque fichier modifié.

À lancer une seule fois pour nettoyer les données déjà présentes (les
nouvelles infos apprises via 'apprend >' sont normalisées automatiquement).

Usage :
    python normalize_data.py
    python ingest.py     (pour réindexer après)
"""
import os
import glob
import shutil

from dates import normalize_dates
from person import normalize_person

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def main():
    files = glob.glob(os.path.join(DATA_DIR, "**", "*.md"), recursive=True)
    if not files:
        print("Aucun fichier .md trouvé dans data/.")
        return

    changed = 0
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            original = f.read()

        normalized = normalize_dates(original)
        normalized = normalize_person(normalized)

        rel = os.path.relpath(filepath, DATA_DIR)
        if normalized != original:
            backup = filepath + ".bak"
            shutil.copy2(filepath, backup)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(normalized)
            print(f"✅ {rel} mis à jour (sauvegarde : {os.path.basename(backup)})")
            changed += 1
        else:
            print(f"—  {rel} : rien à changer")

    print(f"\nTerminé : {changed} fichier(s) modifié(s).")
    if changed:
        print("Pense à relancer : python ingest.py")


if __name__ == "__main__":
    main()