"""
Aklos_app_charlotte.py — Variante visuelle d'Aklos pour Charlotte (thème
noir / rose / or), pour son futur MacBook Air.

Même logique, même moteur (chat.py / ingest.py / backup.py) que
Aklos_app.py — seule la palette de couleurs change. Gardé comme fichier à
part (plutôt que de modifier Aklos_app.py) car les deux thèmes sont
destinés à des installations différentes.

À placer dans le même dossier que ingest.py et chat.py (jarvis-rag/).

Usage :
    python Aklos_app_charlotte.py
"""
import contextlib
import io
import os
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext

# Voir Aklos_app.py pour l'explication détaillée : nécessaire pour un build
# .exe/.app empaqueté en --windowed (pas de console), à cause des emojis
# dans les print() de chat.py/ingest.py.
if getattr(sys, "frozen", False) or sys.stdout is None:
    sys.stdout = io.StringIO()
if getattr(sys, "frozen", False) or sys.stderr is None:
    sys.stderr = io.StringIO()

import chat  # réutilise get_collection / ask / rewrite_query de chat.py
import ingest  # réindexation directe (pas de subprocess : compatible .app empaqueté)
import backup  # sauvegarde de data/ (bouton + auto au démarrage)

# --- Thème "Charlotte" : noir profond, rose mauve discret, rose vif, or ---
BG = "#0b0a0a"             # fond principal, noir vrai
PANEL = "#161112"          # zones de contenu (chat, saisie), noir légèrement teinté
ACCENT = "#ec5f95"         # rose vif : bouton Envoyer, hover des boutons utilitaires, "Toi"
ACCENT_LIGHT = "#d9a635"   # or : titre "Aklos" + réponses d'Aklos
ACCENT_MUTED = "#c98aa3"   # rose mauve discret : boutons Réindexer/Sauvegarder au repos
TEXT_COLOR = "#f0e6df"     # texte principal, blanc cassé chaleureux
USER_COLOR = "#ec5f95"     # "Toi" — même rose vif que le bouton Envoyer
DEBUG_COLOR = "#8a6b73"    # gris rosé discret pour les lignes de debug
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 11, "bold")

ENTRY_MAX_LINES = 4  # hauteur max de la barre de saisie avant qu'elle scrolle


class AklosApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Aklos")
        self.root.geometry("760x620")
        self.root.minsize(560, 440)
        self.root.configure(bg=BG)
        if sys.platform == "darwin":
            # Force l'opacité de la fenêtre : sur certaines versions de Tk
            # sous macOS, les fenêtres sont non-opaques par défaut (effet
            # "vitre" qui laisse voir ce qu'il y a derrière), quel que soit
            # le bg réglé sur les widgets.
            with contextlib.suppress(Exception):
                self.root.wm_attributes("-transparent", False)

        self.collection = None
        self.history = []
        self.pending_fact = None  # texte en attente d'une destination (mode guidé)
        self.pending_forget = None  # {filepath: (new_content, removed)} en attente de confirmation oui/non
        self.busy = False  # True pendant qu'une requête (question/apprend/ingest) tourne

        self._build_ui()
        self._load_collection()
        self._maybe_auto_backup()
        self._fix_macos_blank_window()
        self._set_macos_dock_icon()

    def _set_macos_dock_icon(self):
        """Remplace l'icône générique (fusée Python) affichée dans le Dock
        pendant l'exécution par l'icône Aklos, sans avoir besoin d'empaqueter
        l'app en .app complet (nécessite pyobjc-framework-Cocoa)."""
        if sys.platform != "darwin":
            return
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aklos_icon_mac.png")
        if not os.path.exists(icon_path):
            print(f"[debug icone] fichier introuvable : {icon_path}")
            return
        try:
            from AppKit import NSApplication, NSImage
            image = NSImage.alloc().initByReferencingFile_(icon_path)
            NSApplication.sharedApplication().setApplicationIconImage_(image)
            print("[debug icone] icone appliquee avec succes")
        except Exception as e:
            print(f"[debug icone] erreur : {e}")

    def _fix_macos_blank_window(self):
        """Contourne un bug connu de Tkinter sur macOS (Big Sur et +) où la
        fenêtre s'affiche transparente/vide au lancement tant qu'on ne force
        pas un redessin (redimensionnement ou déplacement). On simule ce
        redessin automatiquement 150ms après l'ouverture."""
        if sys.platform != "darwin":
            return

        def _nudge():
            largeur = self.root.winfo_width()
            hauteur = self.root.winfo_height()
            self.root.geometry(f"{largeur}x{hauteur + 1}")
            self.root.after(30, lambda: self.root.geometry(f"{largeur}x{hauteur}"))

        self.root.after(150, _nudge)

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
            bg=PANEL, fg=ACCENT_MUTED, activebackground=ACCENT,
            relief="flat", font=FONT, padx=10, pady=6, cursor="hand2",
        )
        self.ingest_btn.pack(side="left", pady=8)

        self.backup_btn = tk.Button(
            btn_frame, text="💾 Sauvegarder", command=self.run_backup,
            bg=PANEL, fg=ACCENT_MUTED, activebackground=ACCENT,
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
        input_frame.columnconfigure(0, weight=1)
        input_frame.columnconfigure(1, weight=0)

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

    # ---------- Logique (identique à Aklos_app.py) ----------
    def _load_collection(self):
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
        if event.state & 0x0001:  # Shift enfoncé
            return None
        self.send_question()
        return "break"

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
        def on_progress(msg):
            self.root.after(0, self._append, msg + "\n", "debug")

        try:
            ingest.run_ingest(on_progress=on_progress)
            output = None
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
        threading.Thread(target=self._auto_backup_thread, daemon=True).start()

    def _auto_backup_thread(self):
        try:
            if backup.needs_backup():
                message = backup.run_backup()
                self.root.after(0, self._backup_done, message, False)
        except Exception:
            pass

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
        if self.busy:
            return

        question = self.entry.get("1.0", "end-1c").strip()
        if not question or self.collection is None:
            return
        self.entry.delete("1.0", "end")
        self._resize_entry()
        self._append(f"\nToi > {question}\n", "user")

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

        first_token = [True]

        def handle_token(piece):
            if first_token[0]:
                first_token[0] = False
                self.root.after(0, self._append, "Aklos > ", "aklos")
            self.root.after(0, self._append, piece, None)

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
