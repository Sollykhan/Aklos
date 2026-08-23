Aklos — build macOS (test)
===========================

Salut Florian,

Ceci est le code source d'Aklos, un assistant local (RAG) qui tourne
entièrement sur ta machine, sans connexion internet ni cloud (Ollama +
ChromaDB). Je te demande de tester le build sur Mac.

Contenu de ce zip :
- Les fichiers source Python (chat.py, Aklos_app.py, ingest.py, backup.py,
  dates.py, person.py, paths.py, db.py, normalize_data.py)
- requirements.txt
- PACKAGING_MACOS.md — le guide de build complet, étape par étape
- data/Cybfs-ft-17/ — des notes de cours (cybersécurité) fournies comme
  contenu de test, pour avoir immédiatement de la matière à interroger
  une fois l'appli lancée. Usage strictement personnel/test, merci de ne
  pas les redistribuer plus loin.

Pour builder :
1. Ouvre PACKAGING_MACOS.md et suis les étapes 1 à 4 (installer Python,
   Ollama + modèles, dépendances + PyInstaller, puis la commande de build).
2. Le résultat est Aklos.app dans dist/.
3. Premier lancement : clic droit → Ouvrir (Gatekeeper bloque les apps
   non signées au premier lancement).
4. Dans l'appli, clique "Réindexer" une première fois pour indexer
   data/Cybfs-ft-17.

Aucune modification de code n'est nécessaire : le projet est déjà écrit de
façon portable (aucun chemin Windows en dur, à part une option de
sauvegarde secondaire ignorée automatiquement sur Mac).

Dis moi si quelque chose bloque pendant le build — c'est justement
ce que je veux vérifier avant de préparer une vraie version pour ma fille.

Merci !
