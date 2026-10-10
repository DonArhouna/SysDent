"""Contrôle d'intégrité du dépôt : léger, et il échoue quand on le trompe.

**Pourquoi ce contrôle existe.** En octobre 2026, une instruction d'écriture a
produit des fichiers contenant des caractères CJK au milieu de commentaires en
français. Un fichier reste parfaitement syntaxiquement valide : il compile, les
tests passent, et le défaut ne se voit qu'en lisant le commentaire. Seul un
contrôle automatique le voit.

**Deux règles de caractères, de portée différente — et la différence est
justifiée par un chiffre.** En appliquant « tout hors ASCII » à tout le dépôt,
on obtient 765 signalements : presque tous des traits de cadre (U+2500), des
symboles de section (U+00A7), des signes de multiplication (U+00D7), une lettre
grecque (U+03B2), des émojis d'avertissement (U+26A0) — de la typographie
volontaire et ancienne. Une règle qui hurle sur 765 cas déjà connus ne sera lue
par personne, et le vrai défaut passera avec. D'où la séparation :

- **Étrangers** (bloquant, toujours) : caractères d'une écriture non latine —
  CJK, hiragana, katakana, hangul, cyrillique, arabe, hébreu, devanagari, thaï —
  et le caractère de remplacement U+FFFD. Rien de tout cela n'a de sens dans un
  texte français : c'est la signature exacte du défaut cherché.
- **ASCII strict** (fichiers touchés) : en plus, tout ce qui n'est ni ASCII ni
  accent français. Sur le périmètre des seuls fichiers modifiés, la règle est
  tenable et sans faux positif ; sur tout le dépôt, elle serait ignorée.

**Un fichier n'est jamais déclaré corrompu sur une intuition** : seuls les
points de code exacts sont rapportés, jamais le caractère lui-même.

**Usage.**

```
python scripts/controle_integrite.py               # fichiers modifiés (git), strict
python scripts/controle_integrite.py --tout        # dépôt entier, règles bloquantes
python scripts/controle_integrite.py chemin/...    # périmètre explicite, strict
```

Code de sortie 1 si une règle est violée, 0 sinon.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import subprocess
import sys
from typing import Iterable

RACINE = pathlib.Path(__file__).resolve().parents[2]
BACKEND = RACINE / "Backend"

#: Accents français, ligatures et ponctuation admise par la règle stricte.
CARACTERES_ADMIS = set(
    "àâäéèêëîïôöùûüÿçÀÂÄÉÈÊËÎÏÔÖÙÛÜŸÇ"
    "œŒæÆ"  # ligatures
    "°–—’«»…€"  # ponctuation typographique
    "’‘“”«»\u00a0"  # apostrophes et espaces typographiques
    "→"  # flèche « puis, donc » : convention établie dans ce dépôt
)

#: Plages de caractères **typographiques**, admises par la règle stricte.
#:
#: Élargies après usage réel : en l'appliquant aux huit fichiers à corriger, la
#: règle stricte a signalé 55 caractères, tous des traits de cadre de tableaux
#: (U+2500) et des flèches (U+2194). Le dépôt trace ses tableaux ainsi depuis le
#: début, et le hook bloque tout commit touchant ces fichiers : une règle que
#: l'on contourne à chaque fois n'est plus une règle.
#:
#: Ces plages ne franchissent pas la frontière des écritures : la règle bloquante
#: ci-dessous reste la seule qui juge d'une dégradation, et elle est inchangée.
PLAGES_TYPOGRAPHIE = (
    (0x2190, 0x21FF, "flèches"),
    (0x2500, 0x257F, "traits de cadre"),
    (0x2580, 0x259F, "éléments de bloc"),
)

#: Plages de caractères d'écritures non latines, et le caractère de remplacement.
#: Intervalles inclusifs. Rien de tout cela n'a de raison d'apparaître dans un
#: commentaire ou un identifiant français : c'est la signature du défaut que
#: ce contrôle cherche.
PLAGES_ETRANGERES = (
    (0x0400, 0x04FF, "cyrillique"),
    (0x0590, 0x05FF, "hebreu"),
    (0x0600, 0x06FF, "arabe"),
    (0x0900, 0x097F, "devanagari"),
    (0x0E00, 0x0E7F, "thai"),
    (0x1100, 0x11FF, "hangul (jamo)"),
    (0x3040, 0x309F, "hiragana"),
    (0x30A0, 0x30FF, "katakana"),
    (0x3130, 0x318F, "hangul (compatibilite)"),
    (0x3400, 0x4DBF, "CJK"),
    (0x4E00, 0x9FFF, "CJK"),
    (0xA960, 0xA97F, "hangul"),
    (0xAC00, 0xD7AF, "hangul"),
    (0xFFFD, 0xFFFD, "caractere de remplacement"),
)

#: Extensions relues par le contrôle des caractères.
EXTENSIONS = (".py", ".md", ".ts", ".tsx", ".vue", ".json", ".yml", ".yaml", ".ini", ".sql")

#: Les trois chaînes de migrations : (fichier .ini, dossier de versions).
CHAINEES = {
    "master": ("alembic.ini", "alembic"),
    "plateforme": ("alembic_platform.ini", "alembic_platform"),
    "tenant": ("alembic_tenant.ini", "alembic_tenant"),
}


def categorie_etrangere(caractere: str) -> str | None:
    """Nom de l'écriture si le caractère n'a rien à faire dans un texte français."""
    code = ord(caractere)
    for debut, fin, nom in PLAGES_ETRANGERES:
        if debut <= code <= fin:
            return nom
    return None


def _admis_strict(caractere: str) -> bool:
    if caractere in CARACTERES_ADMIS or " " <= caractere <= "~":
        return True
    code = ord(caractere)
    for debut, fin, _ in PLAGES_TYPOGRAPHIE:
        if debut <= code <= fin:
            return True
    return False


def controler_caracteres(chemins: Iterable[pathlib.Path], *, strict: bool) -> list[str]:
    """
    `strict=False` : seuls les caractères d'une écriture non latine sont refusés.
    `strict=True` : en plus, tout ce qui n'est ni ASCII ni accent français.
    """
    echecs: list[str] = []
    for chemin in chemins:
        if not chemin.is_file() or chemin.suffix not in EXTENSIONS:
            continue
        try:
            contenu = chemin.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            echecs.append(f"{chemin.relative_to(RACINE)}: illisible en UTF-8")
            continue

        for numero, ligne in enumerate(contenu.splitlines(), 1):
            trouves: list[tuple[int, str, str]] = []
            for position, caractere in enumerate(ligne):
                nom = categorie_etrangere(caractere)
                if nom is not None:
                    trouves.append((position, f"U+{ord(caractere):04X}", nom))
                elif strict and not _admis_strict(caractere):
                    trouves.append(
                        (position, f"U+{ord(caractere):04X}", "hors ASCII et accents")
                    )

            if trouves:
                details = ", ".join(f"{code} ({nom})" for _, code, nom in trouves)
                colonnes = ", ".join(str(p + 1) for p, _, _ in trouves)
                echecs.append(
                    f"{chemin.relative_to(RACINE)}:{numero} -> {details} [colonnes {colonnes}]"
                )
    return echecs


def controler_compilation(chemins: Iterable[pathlib.Path]) -> list[str]:
    """
    Tout fichier Python du périmètre compile.

    Pas de `py_compile` ici : `ast.parse` suffit et n'écrit aucun fichier, donc
    le contrôle ne laisse pas de `.pyc` derrière lui.
    """
    echecs: list[str] = []
    for chemin in chemins:
        if chemin.suffix != ".py" or not chemin.is_file():
            continue
        try:
            ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
        except SyntaxError as exc:
            echecs.append(f"{chemin.relative_to(RACINE)}: ligne {exc.lineno} : {exc.msg}")
        except (UnicodeDecodeError, OSError) as exc:
            echecs.append(f"{chemin.relative_to(RACINE)}: illisible ({exc})")
    return echecs


def controler_tetes() -> list[str]:
    """Une seule tête par chaîne, et chaque chaîne doit se charger."""
    echecs: list[str] = []
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
    except ImportError:
        return ["alembic indisponible : contrôle des têtes impossible"]

    for nom, (ini, dossier) in CHAINEES.items():
        racine = BACKEND
        if not (racine / dossier / "versions").is_dir():
            echecs.append(f"chaine {nom} : dossier {dossier}/versions introuvable")
            continue
        try:
            cfg = Config(str(racine / ini))
            cfg.set_main_option("script_location", str(racine / dossier))
            tetes = ScriptDirectory.from_config(cfg).get_heads()
        except Exception as exc:  # noqa: BLE001
            echecs.append(f"chaine {nom} : illisible ({type(exc).__name__})")
            continue
        if len(tetes) != 1:
            echecs.append(f"chaine {nom} : {len(tetes)} tetes {tetes}, une seule attendue")
    return echecs


def fichiers_modifies(racine: pathlib.Path) -> list[pathlib.Path]:
    """Fichiers touchés : modifiés, indexés ou non suivis."""
    try:
        sortie = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(racine),
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        ).stdout
    except Exception:  # noqa: BLE001
        return []

    fichiers: list[pathlib.Path] = []
    for ligne in sortie.splitlines():
        chemin = ligne[3:].strip()
        if " -> " in chemin:  # renommage
            chemin = chemin.split(" -> ", 1)[1]
        chemin = chemin.strip('"')
        if chemin:
            fichiers.append(racine / chemin)
    return fichiers


def tout_le_depot() -> list[pathlib.Path]:
    return [
        chemin
        for dossier in (
            "Backend/src",
            "Backend/tests",
            "Backend/scripts",
            "Backend/alembic",
            "Backend/alembic_platform",
            "Backend/alembic_tenant",
            "docs",
            "Frontend/src",
            "Backoffice/src",
        )
        for chemin in (RACINE / dossier).rglob("*")
        if chemin.is_file()
    ]


def principal(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Controle d'integrite du depot.")
    analyseur.add_argument("chemins", nargs="*", help="perimetre explicite")
    analyseur.add_argument(
        "--tout",
        action="store_true",
        help="tout le depot, regles bloquantes seules (la regle ASCII stricte "
             "y produit trop de faux positifs)",
    )
    arguments = analyseur.parse_args(argv)

    if arguments.chemins:
        # Chemins relatifs au répertoire courant, pas à la racine du dépôt : le
        # contrôle se lance depuis `Backend/`, et une racine mal choisie ne
        # levait aucune erreur — elle analysait un fichier inexistant et
        # renvoyait « OK ». Un contrôle qui ne peut pas mentir ne doit pas
        # pouvoir être silencieusement inerte.
        perimetre = [pathlib.Path(c).resolve() for c in arguments.chemins]
        strict = True
    elif arguments.tout:
        perimetre = tout_le_depot()
        strict = False
    else:
        perimetre = fichiers_modifies(RACINE)
        strict = True

    python = [p for p in perimetre if p.suffix == ".py"]

    echecs: list[str] = []
    echecs += controler_compilation(python)
    echecs += controler_caracteres(perimetre, strict=strict)
    echecs += controler_tetes()

    regle = "compilation, caracteres (stricts), une seule tete par chaine" if strict else (
        "compilation, caracteres d'ecritures non latines, une seule tete par chaine"
    )
    print(f"Perimetre : {len(perimetre)} fichier(s) - {regle}")

    absents = [p for p in perimetre if not p.exists()]
    if absents:
        for chemin in absents:
            print(f"  - INTROUVABLE : {chemin}")
        print("\nUn chemin introuvable n'est pas une conformance : c'est un contrôle inerte.")
        return 1
    if echecs:
        print(f"\n{len(echecs)} PROBLEME(S) :\n")
        for ligne in echecs:
            print(f"  - {ligne}")
        return 1

    print("OK.")
    return 0


if __name__ == "__main__":
    sys.exit(principal())