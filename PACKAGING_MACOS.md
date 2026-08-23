# Empaqueter Aklos pour macOS (ex: pour le MacBook de Charlotte)

Ce guide adapte PACKAGING.md à macOS. Comme pour Windows, je ne peux
pas générer l'app moi-même : PyInstaller doit tourner SUR un Mac pour
produire un binaire macOS (pas de cross-compilation possible depuis
Windows). Il faudra suivre ces étapes directement sur un Mac.

## Ce qui change par rapport à la version Windows

Le cœur du projet (chat.py, ingest.py, Aklos_app.py, backup.py, dates.py,
person.py, paths.py, db.py) est déjà écrit de façon portable (chemins via
`os.path`, pas de code spécifique Windows) — aucune modification de code
n'est nécessaire pour que ça tourne sur macOS.

Trois différences pratiques :

1. **Icône** : macOS utilise le format `.icns`, pas `.ico`. Convertir
   `aklos.ico` en `.icns` (plusieurs convertisseurs en ligne, ou l'outil
   `iconutil` intégré à macOS), ou simplement omettre `--icon` pour ce
   premier build.
2. **Pas de script de raccourci** : sur macOS, l'app buildée EST déjà
   l'icône double-cliquable. Pas besoin d'équivalent du script PowerShell
   utilisé sur Windows — il suffit de glisser l'app dans le dossier
   Applications ou sur le Dock.
3. **`SECONDARY_BACKUP_DIR` dans `backup.py`** : pointe actuellement vers
   `C:\Users\solka\OneDrive\AklosBackups` (chemin Windows). Sur macOS, ce
   chemin est simplement ignoré sans planter (aucun risque), mais autant le
   changer pour l'installation de Charlotte — soit `None` pour désactiver,
   soit un dossier iCloud Drive du style
   `~/Library/Mobile Documents/com~apple~CloudDocs/AklosBackups`.

## 1. Prérequis sur le Mac

- Python 3 (`brew install python` si Homebrew est installé, ou depuis python.org)
- Ollama pour macOS : https://ollama.com (existe en version native Apple Silicon,
  performances correctes même sans configuration particulière)
- Dans un terminal :
  ```
  ollama pull llama3.2:3b
  ollama pull nomic-embed-text
  ```

## 2. Installer les dépendances + PyInstaller

Depuis le dossier du projet :
```
pip3 install -r requirements.txt
pip3 install pyinstaller
```

## 3. Construire l'application

```
pyinstaller --onefile --windowed --name Aklos --collect-all chromadb Aklos_app.py
```
(ajouter `--icon=aklos.icns` si l'icône a été convertie)

Résultat : `dist/Aklos.app`. Comme sous Windows, ça peut être volumineux
(chromadb embarque plusieurs bibliothèques).

## 4. Premier lancement (Gatekeeper)

macOS bloque par défaut les applications non signées/notariées (pas de
certificat développeur Apple ici, ce qui est normal pour un usage
personnel). Au premier lancement, macOS affichera "développeur non
identifié" :
- Clic droit sur Aklos.app → "Ouvrir" (au lieu d'un double-clic), puis
  confirmer — ne se demande qu'une seule fois.
- Ou : Réglages Système → Confidentialité et sécurité → autoriser
  l'application bloquée, tout en bas de la page.

## 5. Installer chez Charlotte

- Copier `Aklos.app` dans le dossier Applications (ou le Dock directement).
- Placer un dossier `data/` à côté du point de lancement, comme sous
  Windows (voir README pour la structure attendue) — SES vrais cours de
  P1/L1, une fois qu'elle les a, pas de contenu généré à l'avance.
- Premier lancement : clic sur "Réindexer".
