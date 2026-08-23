"""
aklos_app.py — Mini interface graphique pour Aklos (ingest + chat).

À placer dans le même dossier que ingest.py et chat.py (jarvis-rag/),
car ce fichier réutilise directement les fonctions de chat.py.

Usage :
    python aklos_app.py
"""
import contextlib
import io
import os
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext

# Une fois empaqueté en .exe avec --windowed (pas de console), sys.stdout/
# stderr sont soit absents, soit limités à un encodage qui ne sait pas
# afficher les emojis utilisés dans les print() de chat.py/ingest.py (ex:
# "❌ Base introuvable"). Ça plantait l'appli entière au lieu de rester
# invisible. On les remplace par un buffer texte neutre AVANT d'importer
# chat/ingest/backup : l'appli n'a de toute façon jamais utilisé de vraie
# console, tout ce qui doit s'afficher passe par la fenêtre (on_token/on_debug).
if getattr(sys, "frozen", False) or sys.stdout is None:
    sys.stdout = io.StringIO()
if getattr(sys, "frozen", False) or sys.stderr is None:
    sys.stderr = io.StringIO()

import chat  # réutilise get_collection / ask / rewrite_query de chat.py
import ingest  # réindexation directe (pas de subprocess : compatible .exe empaqueté)
import backup  # sauvegarde de data/ (bouton + auto au démarrage)

BG = "#1b1f2a"
PANEL = "#242938"
ACCENT = "#7c5cff"        # violet façon "magie elfique"
ACCENT_LIGHT = "#a893ff"
TEXT_COLOR = "#e8e6f0"
USER_COLOR = "#8ecbff"
DEBUG_COLOR = "#7a8299"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 11, "bold")

ENTRY_MAX_LINES = 4  # hauteur max de la barre de saisie avant qu'elle scrolle


class AklosApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Aklos")
        largeur, hauteur = 760, 620
        self.root.geometry(f"{largeur}x{hauteur}")
        self.root.minsize(560, 440)
        self.root.configure(bg=BG)

        # Sans position explicite, Windows place la fenêtre selon une logique
        # à lui (souvent décalée vers le bas, surtout avec un second écran
        # branché) — on centre nous-mêmes sur l'écran principal au lancement.
        self.root.update_idletasks()
        ecran_largeur = self.root.winfo_screenwidth()
        ecran_hauteur = self.root.winfo_screenheight()
        x = (ecran_largeur - largeur) // 2
        y = (ecran_hauteur - hauteur) // 2
        self.root.geometry(f"{largeur}x{hauteur}+{x}+{y}")

        self.collection = None
        self.history = []
        self.pending_fact = None  # texte en attente d'une destination (mode guidé)
        self.pending_forget = None  # {filepath: (new_content, removed)} en attente de confirmation oui/non
        self.busy = False  # True pendant qu'une requête (question/apprend/ingest) tourne

        self._build_ui()
        self._load_collection()
        self._maybe_auto_backup()

    # ---------- UI ----------
    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=16, pady=(16, 8))

        tk.Label(
            header, text="✦ Aklos", bg=BG, fg=ACCENT_LIGHT,
            font=("Segoe UI", 18, "bold"),
        ).pack(side="left")

        self.status_label = tk.Label(header, text="", bg=BG, fg=TEXT_COLOR, font=FONT)
        self.status_label.pack(side="right")

        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(fill="x", padx=16)

        self.ingest_btn = tk.Button(
            btn_frame, text="📥 Réindexer (ingest)", command=self.run_ingest,
            bg=PANEL, fg=TEXT_COLOR, activebackground=ACCENT,
            relief="flat", font=FONT, padx=10, pady=6, cursor="hand2",
        )
        self.ingest_btn.pack(side="left", pady=8)

        self.backup_btn = tk.Button(
            btn_frame, text="💾 Sauvegarder", command=self.run_backup,
            bg=PANEL, fg=TEXT_COLOR, activebackground=ACCENT,
            relief="flat", font=FONT, padx=10, pady=6, cursor="hand2",
        )
        self.backup_btn.pack(side="left", padx=(8, 0), pady=8)

        self.debug_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            btn_frame, text="Mode debug", variable=self.debug_var,
            bg=BG, fg=TEXT_COLOR, selectcolor=PANEL,
            activebackground=BG, font=FONT,
        ).pack(side="left", padx=12)

        # La barre de saisie est packée EN PREMIER avec side="bottom" pour
        # garantir qu'elle garde toujours sa place, quelle que soit la
        # taille du contenu de la zone de chat au-dessus.
        input_frame = tk.Frame(self.root, bg=BG)
        input_frame.pack(side="bottom", fill="x", padx=16, pady=(0, 16))
        # grid plutôt que pack pour cette ligne : plus prévisible pour garantir
        # que le bouton garde sa taille propre pendant que la zone de texte
        # prend tout le reste (pack ordonnait mal le partage d'espace avec un
        # Text, qui réclame une largeur par défaut bien plus grande qu'un Entry).
        input_frame.columnconfigure(0, weight=1)
        input_frame.columnconfigure(1, weight=0)

        # Text plutôt qu'Entry : la barre grandit avec le contenu (jusqu'à
        # ENTRY_MAX_LINES) au lieu de rester sur une seule ligne qui défile
        # horizontalement — plus lisible pour relire une commande apprend >
        # un peu longue avant de l'envoyer.
        self.entry = tk.Text(
            input_frame, bg=PANEL, fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
            font=FONT, relief="flat", height=1, width=1, wrap="word", padx=8, pady=8,
        )
        self.entry.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.entry.bind("<Return>", self._on_entry_return)
        self.entry.bind("<KeyRelease>", self._resize_entry)

        self.send_btn = tk.Button(
            input_frame, text="Envoyer", command=self.send_question,
            bg=ACCENT, fg="white", activebackground=ACCENT_LIGHT,
            relief="flat", font=FONT_BOLD, padx=16, cursor="hand2",
        )
        self.send_btn.grid(row=0, column=1, sticky="s")

        hint = tk.Label(
            self.root,
            text="Astuce : « apprend famille > texte » (apprendre) · « oublie > texte » (liste numérotée, tu choisis quoi supprimer).",
            bg=BG, fg=DEBUG_COLOR, font=("Segoe UI", 8),
        )
        hint.pack(side="bottom", pady=(0, 4))

        self.chat_area = scrolledtext.ScrolledText(
            self.root, wrap="word", bg=PANEL, fg=TEXT_COLOR,
            font=FONT, relief="flat", padx=10, pady=10, state="disabled",
            height=12,
        )
        self.chat_area.pack(side="top", fill="both", expand=True, padx=16, pady=8)
        self.chat_area.tag_config("user", foreground=USER_COLOR, font=FONT_BOLD)
        self.chat_area.tag_config("aklos", foreground=ACCENT_LIGHT, font=FONT_BOLD)
        self.chat_area.tag_config("debug", foreground=DEBUG_COLOR, font=("Consolas", 9))

    # ---------- Logique ----------
    def _load_collection(self):
        # get_collection() imprime le détail de l'erreur avant de sortir ;
        # on capture ce texte (plutôt que de le laisser filer dans le buffer
        # invisible global) pour l'afficher dans la fenêtre — utile pour
        # diagnostiquer un souci sans deviner à l'aveugle.
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                self.collection = chat.get_collection()
            self.status_label.config(text="● Base chargée", fg="#7ee787")
        except SystemExit:
            self.collection = None
            detail = buffer.getvalue().strip()
            if detail:
                self._append(detail + "\n", "debug")
            self.status_label.config(text="● Base introuvable — clique Ingest", fg="#ff7b72")

    def _on_entry_return(self, event):
        # Entrée seule envoie (comme avant, avec l'ancien Entry) ; Maj+Entrée
        # insère un saut de ligne pour un fait/une commande sur plusieurs lignes.
        if event.state & 0x0001:  # Shift enfoncé
            return None  # comportement par défaut du Text : insère un \n
        self.send_question()
        return "break"  # empêche le Text d'insérer aussi un \n

    def _resize_entry(self, event=None):
        lines = self.entry.count("1.0", "end-1c", "displaylines") or 1
        if isinstance(lines, tuple):
            lines = lines[0] if lines else 1
        self.entry.config(height=max(1, min(lines, ENTRY_MAX_LINES)))

    def _append(self, text, tag=None):
        self.chat_area.config(state="normal")
        self.chat_area.insert("end", text, tag)
        self.chat_area.see("end")
        self.chat_area.config(state="disabled")

    def run_ingest(self):
        if self.busy:
            return
        self.busy = True
        self.ingest_btn.config(state="disabled", text="Indexation en cours…")
        self._append("\n— Réindexation en cours… —\n", "debug")
        threading.Thread(target=self._run_ingest_thread, daemon=True).start()

    def _run_ingest_thread(self):
        # Appel direct à ingest.run_ingest() plutôt qu'un subprocess "python
        # ingest.py" : ça évite de dépendre d'un interpréteur Python externe,
        # ce qui casserait une fois l'appli empaquetée en .exe (sys.executable
        # pointerait alors vers l'exe lui-même, pas vers python.exe).
        #
        # on_progress affiche chaque fichier au fur et à mesure dans la
        # fenêtre, plutôt que de tout capturer en silence et ne l'afficher
        # qu'à la toute fin (ce qui donnait l'impression que l'appli était
        # figée pendant une longue réindexation).
        def on_progress(msg):
            self.root.after(0, self._append, msg + "\n", "debug")

        try:
            ingest.run_ingest(on_progress=on_progress)
            output = None  # déjà affiché au fil de l'eau via on_progress
        except Exception as e:
            output = f"Erreur : {e}"
        self.root.after(0, self._ingest_done, output)

    def _ingest_done(self, output):
        if output:
            self._append(output + "\n", "debug")
        self.ingest_btn.config(state="normal", text="📥 Réindexer (ingest)")
        self._load_collection()
        self.busy = False

    def run_backup(self):
        if self.busy:
            return
        self.busy = True
        self.backup_btn.config(state="disabled", text="Sauvegarde en cours…")
        threading.Thread(target=self._backup_thread, args=(True,), daemon=True).start()

    def _maybe_auto_backup(self):
        """Sauvegarde silencieuse au démarrage si la dernière date de plus de 24h.
        Ne bloque pas le chat : tourne en fond, sans passer par self.busy."""
        threading.Thread(target=self._auto_backup_thread, daemon=True).start()

    def _auto_backup_thread(self):
        try:
            if backup.needs_backup():
                message = backup.run_backup()
                self.root.after(0, self._backup_done, message, False)
        except Exception:
            pass  # sauvegarde auto silencieuse : pas d'interruption si ça échoue

    def _backup_thread(self, from_button):
        try:
            message = backup.run_backup()
        except Exception as e:
            message = f"Erreur de sauvegarde : {e}"
        self.root.after(0, self._backup_done, message, from_button)

    def _backup_done(self, message, from_button):
        self._append(f"\n💾 {message}\n", "debug")
        if from_button:
            self.backup_btn.config(state="normal", text="💾 Sauvegarder")
            self.busy = False

    def send_question(self):
        # Bloque tout nouvel envoi tant qu'Aklos traite encore le précédent —
        # sans ça, un message tapé trop vite pendant un apprentissage en
        # cours pouvait être avalé comme réponse à la mauvaise question.
        if self.busy:
            return

        question = self.entry.get("1.0", "end-1c").strip()
        if not question or self.collection is None:
            return
        self.entry.delete("1.0", "end")
        self._resize_entry()
        self._append(f"\nToi > {question}\n", "user")

        # Confirmation en attente : la dernière réponse d'Aklos proposait une
        # suppression ('oublie >') et attend un numéro/liste/'tout' pour confirmer.
        if self.pending_forget is not None:
            matches, self.pending_forget = self.pending_forget, None
            max_number = len(chat.number_candidates(matches))
            selection = chat.parse_selection(question, max_number)
            if selection is None:
                self._append("Aklos > Annulé, rien n'a été supprimé.\n", "aklos")
                self._set_status("● Base chargée", "#7ee787")
            else:
                self.busy = True
                self.send_btn.config(state="disabled")
                threading.Thread(target=self._forget_thread, args=(matches, selection), daemon=True).start()
            return

        # Mode guidé : la dernière réponse d'Aklos attendait un nom de fichier.
        if self.pending_fact is not None:
            if question.lower() in {"annule", "annuler", "cancel"}:
                self.pending_fact = None
                self._append("Aklos > Annulé.\n", "aklos")
                self._set_status("● Base chargée", "#7ee787")
                return
            fact, self.pending_fact = self.pending_fact, None
            self.busy = True
            self.send_btn.config(state="disabled")
            threading.Thread(target=self._learn_thread, args=(fact, question), daemon=True).start()
            return

        forget_match = chat.FORGET_PATTERN.match(question)
        if forget_match:
            destination, search_text = forget_match.groups()
            search_text = search_text.strip()
            if len(search_text) < chat.MIN_FORGET_LENGTH:
                self._append(
                    f"Aklos > Texte trop court pour chercher en toute sécurité "
                    f"(minimum {chat.MIN_FORGET_LENGTH} caractères).\n",
                    "aklos",
                )
                return
            matches = chat.find_forgettable(search_text, destination)
            numbered = chat.number_candidates(matches)
            if not numbered:
                self._append(f"Aklos > Aucune information trouvée contenant « {search_text} ».\n", "aklos")
            else:
                lines = [f"  {n}. [{os.path.basename(fp)}] {cand['text']}" for n, fp, cand in numbered]
                preview = "\n".join(lines)
                self._append(
                    f"Aklos > J'ai trouvé :\n{preview}\n"
                    f"Réponds avec le(s) numéro(s) à supprimer (ex: 1 ou 1,3), "
                    f"'tout' pour tout supprimer, ou autre chose pour annuler.\n",
                    "aklos",
                )
                self.pending_forget = matches
                self._set_status("🗑️ En attente de confirmation…", ACCENT_LIGHT)
            return

        learn_match = chat.LEARN_PATTERN.match(question)
        if learn_match:
            destination, fact = learn_match.groups()
            if destination:
                self.busy = True
                self.send_btn.config(state="disabled")
                threading.Thread(target=self._learn_thread, args=(fact, destination), daemon=True).start()
            else:
                self.pending_fact = fact
                self._append(
                    "Aklos > Dans quel fichier je range ça ? "
                    "(ex: famille, perso, projet... — ou 'annule')\n",
                    "aklos",
                )
                self._set_status("📁 En attente du nom de fichier…", ACCENT_LIGHT)
            return

        self.busy = True
        self.send_btn.config(state="disabled")
        threading.Thread(target=self._answer_thread, args=(question,), daemon=True).start()

    def _set_status(self, text, color):
        self.status_label.config(text=text, fg=color)

    def _learn_thread(self, fact, destination):
        self.root.after(0, self._set_status, "🧠 Apprentissage en cours…", TEXT_COLOR)
        self.root.after(0, self._append, "Aklos > apprentissage en cours…\n", "debug")
        result = chat.learn_fact(fact, destination)
        self.root.after(0, self._append, result + "\n", "aklos")
        self.collection = chat.get_collection()  # la collection a été recréée par l'ingestion
        self.root.after(0, self._set_status, "● Base chargée", "#7ee787")
        self.root.after(0, self._finish_busy)

    def _forget_thread(self, matches, selection):
        self.root.after(0, self._set_status, "🗑️ Suppression en cours…", TEXT_COLOR)
        self.root.after(0, self._append, "Aklos > suppression en cours…\n", "debug")
        result = chat.apply_forget(matches, selection)
        self.root.after(0, self._append, result + "\n", "aklos")
        self.collection = chat.get_collection()  # la collection a été recréée par l'ingestion
        self.root.after(0, self._set_status, "● Base chargée", "#7ee787")
        self.root.after(0, self._finish_busy)

    def _finish_busy(self):
        self.busy = False
        self.send_btn.config(state="normal")

    def _answer_thread(self, question):
        self.root.after(0, self._set_status, "🧠 Réflexion…", ACCENT_LIGHT)

        chat.DEBUG = self.debug_var.get()
        override_scope, question = chat.parse_scope_prefix(question)
        standalone = chat.rewrite_query(question, self.history)
        if chat.DEBUG and standalone != question:
            self.root.after(0, self._append, f"  ↳ reformulée : {standalone}\n", "debug")

        # "Aklos > " n'est affiché qu'au premier fragment reçu, pour que les
        # lignes de debug (distances) passées via on_debug s'affichent AVANT,
        # dans le même ordre que côté CLI.
        first_token = [True]

        def handle_token(piece):
            if first_token[0]:
                first_token[0] = False
                self.root.after(0, self._append, "Aklos > ", "aklos")
            self.root.after(0, self._append, piece, None)

        # Streaming : chaque fragment de texte est affiché dans la fenêtre au
        # fur et à mesure, via on_token (marshalé sur le thread principal
        # Tkinter avec root.after, car Tkinter n'est pas thread-safe).
        answer, sources = chat.ask(
            self.collection, question, standalone,
            on_token=handle_token,
            on_debug=lambda line: self.root.after(0, self._append, line + "\n", "debug"),
            force_scope=override_scope,
        )

        if chat.DEBUG and sources and "AUCUN CONTEXTE" not in "".join(sources):
            self.root.after(0, self._append, f"\n📄 {', '.join(sources)}\n", "debug")
        else:
            self.root.after(0, self._append, "\n", None)

        self.history.append({"question": question, "answer": answer})
        self.history = self.history[-chat.MAX_HISTORY_TURNS:]
        self.root.after(0, self._set_status, "● Base chargée", "#7ee787")
        self.root.after(0, self._finish_busy)


if __name__ == "__main__":
    root = tk.Tk()
    AklosApp(root)
    root.mainloop()