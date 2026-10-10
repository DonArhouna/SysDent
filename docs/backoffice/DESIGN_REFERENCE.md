# Design référence — parité avec l'application client (SysDent Pro)

> Source : lecture du code du client (`Frontend/`), **pas de mémoire**. La loi de
> ce document : **tu reprends tout.** Les seules différences autorisées sont
> celles qui montrent qu'il s'agit du backoffice (voir « Différenciation »).

## 1. Tokens (source unique : `Frontend/src/index.css`)

La police de référence est la **serif du navigateur** (Times New Roman par
défaut Tailwind), demandée explicitement pour la sidebar.midtier:
- Couleurs en **HSL** dans les variables CSS (`--background`, `--card`,
  `--primary`, `--success`, `--warning`, `--danger`,
  `--accent-{blue,green,purple,orange}`, `--kpi-{blue,green,purple,orange}`,
  `--surface`, `--surface-border`, `--surface-hover`, `--sidebar*`, `--ring`).
- Mécanisme de thème : `darkMode: 'class'` Tailwind, classe '.dark' sur
  `<html>`, persistance `localStorage['sysdent-theme']`, sombre par défaut,
  script anti-FOUC dans `index.html`.
- Rayons (`tailwind.config.js`): `card` = **0.75rem**, `xl2` = **1.25rem**,
  `xl3` = **1.5rem** ; pill = `rounded-full` ; sidebar = `rounded-xl3`.
- Ombres : `shadow-float` (douce et diffuse : `0 8px 32px -8px rgb(0 0 0/0.18), 0 2px 8px -2px rgb(0 0 0/0.08)`).
- Espacement : gouttière du shell `p-3 md:p-4` autour de la fenêtre ;
  `mt-3 md:mt-4` entre navbar et contenu.
- Transitions : durée ≤ 200 ms ; pas d'animation si `prefers-reduced-motion`.

## 2. Tableau de correspondance

| Composant backoffice | Fichier client source | Note |
|---|---|---|
| AppSidebar | `Frontend/src/components/layout/sidebar.tsx` | identique, non corrigé |
| Topbar | `Frontend/src/components/layout/topbar.tsx | identique |
| AppShell | `Frontend/src/components/layout/app-shell.tsx` | identique |
| PageHeader | `Frontend/src/components/ui/page-header.tsx` | identique |
| StatCard | `Frontend/src/components/dashboard/stat-card.tsx` | identique |
| StatusBadge | `Frontend/src/components/ui/status-badge.tsx` | identique |
| Pagination | `Frontend/src/components/ui/pagination.tsx` | identique |
| EmptyState | `Frontend/src/components/ui/empty-state.tsx` | identique |
| ConfirmDialog | `Frontend/src/components/ui/confirm-dialog.tsx` | identique |
| Drawer | `Frontend/src/components/ui/drawer.tsx` | identique |
| Modal | `Frontend/src/components/ui/modal.tsx` | identique |
| Table (THead/TBody/TRow/TH/TD) | `Frontend/src/components/ui/table.tsx` | identique |
| Card, Button, Input, Label, Select, Skeleton, Toast | `Frontend/src/components/ui/*.tsx` | identiques |
| ThemeToggle | `Frontend/src/components/layout/theme-toggle.tsx` | identique |
| Page de connexion | `Frontend/src/pages/login.tsx` | à adapter pour 2FA |
| `<Can>` | `Frontend/src/components/auth/can.tsx` | identique |

## 3. Détails visuels à retrouver à l'identique

### Sidebar (`.floating-panel`, `rounded-xl3`, `font-serif`)
- En-tête : carré 40×40 arrondi (rounded-xl) `bg-primary`, 2 lettres en fonte
  noire sur fond plein, **dans un seul lien** vers `/dashboard` (titre du lien,
  pas bouton séparé) ; libellé `SysDent Pro` + sous-titre accroche en gris
  (`Sparkles` violet 12×12) ; **chevron de repli** à droite de l'en-tête.
- Recherche de fonction : chmp pilule (`rounded-full`) 36px, `Search` à gauche,
  placeholder « Rechercher une fonction… » ; filtre réel du contenu, sections
  auto-dépliées pendant la recherche ; largeur pilule 36px.
- Sections : titre en majuscules espacées (10px, `uppercase tracking-wider`),
  chevron de repli, **seule zone défilable** (`scrollbar-none`, overflow-y) ;
  dépli/repli animé par `grid-rows-[0fr]/[1fr]` (200 ms ease-out).
- Éléments : pilules (`rounded-full`), icône 16×16, 13px ; actif =
  `bg-primary text-primary-foreground shadow-sm`, texte medium ;
  inactif = `text-sidebar-foreground`, hover : translate-x 0.5 + surface-hover.
- Ligne verticale de hiérarchie : `ul` avec `ml-3.5 pl-2 border-l
  border-sidebar-border`.
- Pied : carte utilisateur = `rounded-xl2 border surface` avec `Avatar` +
  nom complet + rôle, quand dépliée seulement.
- **Retrait au repli** : titre de section → filet horizontal ; texte →icône
  seule (title + aria-label).

### Navbar (`.floating-panel`, `rounded-xl2`, h-16)
- **Pas de bouton de menu** : le repli vit dans l'en-tête de la sidebar.
- Recherche globale : pilule `` à gauche, `Search`, placeholder «                Rechercher une page, une action… », raccourci `Ctrl+K` (kbd). Clic ouvre la palette.
- Bouton menu mobile : `lg:hidden` (bouton `Menu`). Sur desktop, on replie via la sidebar.
- Bloc droit : badge rôle (`COULEURS_ROLES`), date longue française, ThèmeToggle, icône notifications (state vide), bloc utilisateur (avatar + nom + rôle, chevron) menant à un menu (Mon compte, Paramètres, Déconnexion).
- Fermeture par clic et `Échap` dans le menu.

### AppShell
- Fenêtre : `relative flex h-screen overflow-hidden bg-background p-3 md:p-4`.
- Sidebar ancrée à gauche (≥ lg) : wrapper `w-[268px]` ou `w-[80px]` replié,
  `transition-[width]`.
- Drawer mobile (< lg) : overlay `bg-black/50 backdrop-blur-sm` + panneau
  `slide-in-from-left` 268px.
- Navbar en top ; `main` : `mt-3 flex-1 overflow-y-auto rounded-xl2`.

### Cartes KPI (`StatCard`)
- `rounded-xl2 border border-border border-l-4 bg-card shadow-float`,
  `--liseré` = couleur de l'accent.
- Label : **uppercase**, 12px, semibold, `tracking-wider`, gris.
- Valeur : `text-2xl sm:text-3xl font-bold break-words tabular-nums`.
- Légende : 12px gris.
- Pastille icône : `icon-chip` (40×40, `rounded-xl`) teintée en haut à droite
  (`bg-accent-*/15 text-accent-*`).
- 3 états : `chargement` (skeleton), `hint` (erreur API), valeur.

### Table
- `THead` : `h-10 px-4 text-xs font-semibold uppercase tracking-wide
  text-muted-foreground`; en-têtes discrets.
- `TRow` : `border-b border-border hover:bg-muted/50 transition-colors`.
- `TD` : `px-4 py-3 align-middle`.
- État vide : `EmptyState` (pastille 48×48 rounded-xl2, fond muted).

### Badges
- `StatusBadge` : 6 tons sémantiques (`neutral`, `info`, `success`, `warning`,
  `danger`, `purple`), 11px semibold `rounded-full border px-2.5 py-0.5`.
- `Badge` : pastilles métier, même code couleur.

### Modales / Drawer / ConfirmDialog
- `Drawer` : panneaux `rounded-card border surface` sur `max-w-{sm..2xl}`,
  position right/left, fermeture par `Échap` ou clic extérieur.
- `ConfirmDialog` : `Modal sm` centrée, pastille danger 56×56 + titre +message
  + `Button outline` / `danger` / `primary`.
- Toast : pastilles flottantes, 4 types (success, error, warning, info), avec
  icône décorée (CheckCircle2, AlertCircle, ...).

### Page de connexion (`login.tsx`)
- Fond plein `bg-background`, **max-w-md** centré.
- Logo : carré 56×56 `rounded-2xl bg-primary` avec 2 lettres noires blanches +
  shadow-primary/30, titre `SysDent Pro` `text-2xl font-bold`, sous-titre 12px
  avec icône Sparkles violette.
- Carte formulaire : `rounded-card border border-border bg-card p-6 shadow-sm`.
- Champs : email + mot de passe avec **icônes absolues** (Mail, LockKeyhole)
  16×16 à gauche ; **œil** à droite pour montrer/cacher le mot de passe
  (`Eye/EyeOff`), bordure focus obligatoire.
- Message d'erreur : `role="alert"`, `rounded-lg border border-danger/30
  bg-danger/10 px-3 py-2 text-xs text-danger`.
- Bouton : `w-full`, `primary`, texte « Se connecter », état `loading`.
- Note bas de carte : « Votre cabinet est reconnu automatiquement à partir de
  votre email ».

## 4. Valeurs en dur relevées dans le client (à ne pas dériver)

- `icon-chip` : css `h-10 w-10` (`40×40`) et `rounded-xl`.
- Cartes KPI : classe `border-l-4` (4px).
- Sidebar : largeurs **268px** (`w-[268px]`) et rail **80px** (`w-[80px]`).
- Navbar : hauteur **h-16** ; mobile drawer : **inset-y-3 left-3 w-[268px]**.
- StatCard : `--liseré` lecture via `style={{ '--liseré': style.var }}`.
- Badge `text-[9px]`, `text-[10px]`, `text-[11px]`, `text-[12px]`,
  `text-[13px]`, `text-[14px]` : tailles arbitraires Tailwind et volontaires.
      → à reprendre telles quelles (l'intention est déjà la police du DS).
- Palette des **couleurs** du client : aucun hex en dur : tout HSL via
  variables CSS et classes sémantiques. Reprendre tel quel.
- Situations où le client utilise les **couleurs natives Tailwind**
  (`emerald-500/30`, `rose-500/30`, `amber-500/30`, `blue-500/30`) : **uniquement**
  dans **`toast.tsx`**. Deux options équivalentes : (1) mettre dans une
  entrée de `design-ecarts-autorises.json`, ou (2) basculer sur les tokens
  (recommandé). On trancrit l'intention via les variables token
  (`--success`, `--danger`, `--warning`, `--primary`).

## 5. Différenciation autorisée (exclusivement)

- Badge « Plateforme » permanent dans la navbar : badge `Plateforme` avec
  accent `--plateforme` (nouveau token propre au backoffice).
- Accent `--plateforme` utilisé **avec parcimonie** : badge, élément actif de
  sidebar, liseré principal des cartes KPI.
- Nom de l'app : « SysDent Pro – Backoffice » (sidebar et titre d'onglet).
- Favicon distinct.
