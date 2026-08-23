"""
person.py — Convertit les possessifs de la première personne ("mon", "ma",
"mes") vers la deuxième personne ("ton", "ta", "tes") dans un texte.

Pourquoi : ce que tu écris via 'apprend >' est à TON point de vue
("Charlotte est ma fille"). Mais quand Aklos te répond, c'est LUI qui te
parle, donc il doit dire "ta fille", pas recopier ton "ma". On le fait ici,
au moment où le texte est enregistré, plutôt que de compter sur le modèle
pour bien le reformuler à chaque réponse (il s'est trompé en le faisant lui-même).

Pas besoin de connaître le genre du mot qui suit : "mon"/"ma"/"mes"
l'encodent déjà correctement (et gèrent même l'élision devant une voyelle,
ex: "mon épouse"). On change juste la personne, un mot pour un mot.
"""
import re

POSSESSIVES = {
    "mon": "ton",
    "ma": "ta",
    "mes": "tes",
}

# \b...\b = "mot entier seulement" (ne touche pas à "mont", "amas", etc.)
PATTERN = re.compile(r"\b(" + "|".join(POSSESSIVES.keys()) + r")\b", re.IGNORECASE)


def normalize_person(text: str) -> str:
    """Remplace mon/ma/mes par ton/ta/tes (mots entiers, insensible à la casse,
    en gardant la majuscule si le mot d'origine en avait une)."""

    def repl(match):
        word = match.group(0)
        replacement = POSSESSIVES[word.lower()]
        return replacement.capitalize() if word[0].isupper() else replacement

    return PATTERN.sub(repl, text)