"""
aklos_web.py — Interface web legere pour Aklos, pensee pour etre ouverte
depuis un iPad (ou tout autre appareil) sur le meme reseau Wi-Fi que la
machine qui la fait tourner (le Mac, typiquement).

Reutilise le meme moteur (chat.py) que Aklos_app.py / Aklos_app_charlotte.py
— juste une interface HTML au lieu de Tkinter, pas de logique dupliquee.

Usage :
    python3 aklos_web.py

Puis, depuis l'iPad (ou autre appareil, meme Wi-Fi), ouvrir Safari sur :
    http://<adresse IP de cette machine>:5000

Pour trouver l'IP sur Mac : Reglages Systeme > Wi-Fi > (i) a cote du
reseau connecte, ou dans le Terminal : ipconfig getifaddr en0

Astuce iPad : une fois la page ouverte dans Safari, bouton Partager ->
"Sur l'ecran d'accueil" -> ca cree une icone qui s'ouvre en plein ecran,
comme une vraie appli, sans passer par l'App Store.
"""
import chat
from flask import Flask, request, render_template_string

app = Flask(__name__)
collection = chat.get_collection()
history = []

PAGE = """
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aklos</title>
<style>
  * { box-sizing: border-box; }
  body {
    background:#0b0a0a; color:#f0e6df; font-family:-apple-system, sans-serif;
    margin:0; padding:16px; min-height:100vh; display:flex; flex-direction:column;
  }
  h1 { color:#d9a635; font-size:22px; margin:0 0 16px; }
  .chat { flex:1; overflow-y:auto; }
  .msg { margin:12px 0; line-height:1.45; }
  .user { color:#ec5f95; font-weight:bold; }
  .aklos { color:#d9a635; font-weight:bold; }
  form { display:flex; gap:8px; margin-top:16px; }
  textarea {
    flex:1; background:#161112; color:#f0e6df; border:1px solid #2a2224;
    border-radius:10px; padding:10px; font-size:16px; resize:none;
  }
  button {
    background:#ec5f95; color:white; border:none; border-radius:10px;
    padding:0 20px; font-weight:bold; font-size:16px;
  }
</style>
</head>
<body>
<h1>&#10022; Aklos</h1>
<div class="chat">
{% for h in history %}
  <div class="msg"><span class="user">Toi &gt;</span> {{ h.question }}</div>
  <div class="msg"><span class="aklos">Aklos &gt;</span> {{ h.answer }}</div>
{% endfor %}
</div>
<form method="post">
  <textarea name="question" rows="2" placeholder="Pose ta question..." autofocus></textarea>
  <button type="submit">Envoyer</button>
</form>
<script>
  var chat = document.querySelector('.chat');
  chat.scrollTop = chat.scrollHeight;
</script>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if question:
            override_scope, q = chat.parse_scope_prefix(question)
            standalone = chat.rewrite_query(q, history)
            answer, sources = chat.ask(collection, q, standalone, force_scope=override_scope)
            history.append({"question": question, "answer": answer})
            history[:] = history[-chat.MAX_HISTORY_TURNS:]
    return render_template_string(PAGE, history=history)


if __name__ == "__main__":
    # host="0.0.0.0" : accessible depuis les autres appareils du meme Wi-Fi,
    # pas seulement depuis cette machine.
    app.run(host="0.0.0.0", port=5000, debug=False)
