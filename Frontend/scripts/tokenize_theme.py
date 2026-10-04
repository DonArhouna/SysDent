"""
Remplace les couleurs Tailwind codées en dur par les tokens de design SysDent.

Pourquoi : les pages codaient `bg-slate-900/60`, `text-slate-400`... ce qui rendait
le mode clair illisible (blocs sombres sur fond blanc) et, inversement, certains
fichiers clairs étaient invisibles en mode sombre. Les tokens (`bg-card`,
`text-muted-foreground`, `border-border`...) s'adaptent automatiquement au thème.

EXCLUS VOLONTAIREMENT : les vues d'impression (facture-print-modal,
ordonnance-print-view) qui doivent rester blanches sur papier quel que soit le thème.

Usage : python scripts/tokenize_theme.py [--dry-run]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CIBLES = [RACINE / "src" / "features", RACINE / "src" / "pages"]

# Vues d'impression : blanches sur papier par conception, jamais tokenisées.
EXCLUS = {
    "facture-print-modal.tsx",
    "ordonnance-print-view.tsx",
}

# Table de correspondance. Les clés sont triées par longueur décroissante à
# l'exécution pour que `bg-slate-900/60` soit traité avant `bg-slate-900`.
CORRESPONDANCES: dict[str, str] = {
    # ---- Surfaces neutres (structure) ----
    "bg-slate-950": "bg-background",
    "bg-slate-900": "bg-card",
    "bg-slate-800": "bg-muted",
    "bg-slate-700": "bg-muted",
    "bg-slate-100": "bg-muted",
    "bg-slate-50": "bg-muted",
    "border-slate-900": "border-border",
    "border-slate-800": "border-border",
    "border-slate-700": "border-border",
    "border-slate-600": "border-input",
    "border-slate-400": "border-input",
    "border-slate-200": "border-border",
    "border-slate-100": "border-border",
    "divide-slate-800": "divide-border",
    "divide-slate-100": "divide-border",
    # ---- Textes neutres ----
    "text-slate-900": "text-foreground",
    "text-slate-800": "text-foreground",
    "text-slate-700": "text-foreground",
    "text-slate-600": "text-muted-foreground",
    "text-slate-500": "text-muted-foreground",
    "text-slate-400": "text-muted-foreground",
    "text-slate-300": "text-card-foreground",
    "text-slate-200": "text-foreground",
    "text-slate-100": "text-foreground",
    # ---- Succès (payé, actif, validé) ----
    "text-emerald-900": "text-success",
    "text-emerald-800": "text-success",
    "text-emerald-700": "text-success",
    "text-emerald-600": "text-success",
    "text-emerald-500": "text-success",
    "text-emerald-400": "text-success",
    "text-emerald-300": "text-success",
    "bg-emerald-950": "bg-success/15",
    "bg-emerald-100": "bg-success/15",
    "bg-emerald-50": "bg-success/15",
    "bg-emerald-600": "bg-success",
    "bg-emerald-500": "bg-success",
    "border-emerald-800": "border-success/40",
    "border-emerald-700": "border-success/40",
    "border-emerald-600": "border-success/40",
    # ---- Alerte (impayé, seuil, attention) ----
    "text-amber-800": "text-warning",
    "text-amber-700": "text-warning",
    "text-amber-600": "text-warning",
    "text-amber-400": "text-warning",
    "text-amber-300": "text-warning",
    "text-amber-200": "text-warning",
    "bg-amber-950": "bg-warning/15",
    "bg-amber-100": "bg-warning/15",
    "border-amber-800": "border-warning/40",
    "border-amber-700": "border-warning/40",
    "border-amber-600": "border-warning/40",
    # ---- Danger (annulé, erreur, critique) ----
    "text-rose-400": "text-danger",
    "text-rose-300": "text-danger",
    "text-rose-200": "text-danger",
    "bg-rose-950": "bg-danger/15",
    "bg-rose-500": "bg-danger",
    "border-rose-800": "border-danger/40",
    "border-rose-700": "border-danger/40",
    "border-rose-600": "border-danger/40",
    # ---- Primaire / accent bleu ----
    "text-cyan-800": "text-primary",
    "text-cyan-400": "text-primary",
    "text-cyan-300": "text-primary",
    "text-cyan-200": "text-primary",
    "text-blue-700": "text-primary",
    "text-blue-500": "text-primary",
    "text-blue-300": "text-primary",
    "bg-cyan-950": "bg-primary/15",
    "bg-cyan-100": "bg-primary/15",
    "bg-blue-950": "bg-primary/15",
    "bg-blue-50": "bg-primary/10",
    "bg-cyan-600": "bg-primary",
    "border-cyan-800": "border-primary/40",
    "border-cyan-700": "border-primary/40",
    "border-cyan-500": "border-primary/40",
    "border-cyan-400": "border-primary/40",
    "border-blue-500": "border-primary/40",
    # ---- Accent violet ----
    "text-purple-400": "text-accent-purple",
    "text-purple-300": "text-accent-purple",
    "text-indigo-300": "text-accent-purple",
    "bg-indigo-950": "bg-accent-purple/15",
    "border-indigo-700": "border-accent-purple/40",
    # ---- États interactifs ----
    "hover:text-slate-200": "hover:text-foreground",
    "hover:text-rose-400": "hover:text-danger",
    "hover:text-cyan-400": "hover:text-primary",
    "hover:text-cyan-300": "hover:text-primary",
    "hover:text-amber-700": "hover:text-warning",
    "hover:bg-slate-800": "hover:bg-muted",
    "hover:bg-emerald-950": "hover:bg-success/15",
    "hover:bg-rose-950": "hover:bg-danger/15",
    "hover:bg-emerald-700": "hover:bg-success/90",
}


def construire_motifs() -> list[tuple[re.Pattern[str], str]]:
    """Compile les motifs, du plus long au plus court, avec garde de frontière."""
    motifs = []
    for source in sorted(CORRESPONDANCES, key=len, reverse=True):
        # Le préfixe peut être précédé d'un modificateur Tailwind (hover:, focus:,
        # group-hover:...) : on le laisse intact. Le suffixe d'opacité optionnel
        # (`/60`) est consommé puis abandonné : le token porte déjà sa teinte.
        motif = re.compile(
            r"(?<![\w/-])" + re.escape(source) + r"(?:/[0-9]{1,3})?(?![\w-])"
        )
        motifs.append((motif, CORRESPONDANCES[source]))
    return motifs


def traiter(chemin: Path, motifs, dry_run: bool) -> int:
    source = chemin.read_text(encoding="utf-8")
    resultat = source
    total = 0
    for motif, remplacement in motifs:
        resultat, n = motif.subn(remplacement, resultat)
        total += n
    if total and not dry_run:
        chemin.write_text(resultat, encoding="utf-8")
    return total


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    motifs = construire_motifs()

    fichiers = []
    for dossier in CIBLES:
        fichiers.extend(sorted(dossier.rglob("*.tsx")))

    grand_total = 0
    for chemin in fichiers:
        if chemin.name in EXCLUS:
            print(f"  EXCLU   {chemin.relative_to(RACINE)}  (vue d'impression)")
            continue
        n = traiter(chemin, motifs, dry_run)
        if n:
            rel = chemin.relative_to(RACINE)
            print(f"  {n:4d}    {rel}")
            grand_total += n

    mode = " (DRY-RUN, rien écrit)" if dry_run else ""
    print(f"\nTotal remplacements : {grand_total}{mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())