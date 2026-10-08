# Exploitation de la plateforme — commandes opérateur

> Ce document s'adresse à qui a un **accès au serveur**. Ces commandes ne sont
> jamais exposées en HTTP : une route HTTP qui réinitialiserait un mot de passe
> serait une cible évidente, et n'aurait aucune justification opérationnelle.

## Le compte

Le Super Admin de la plateforme est **`rhonekane@gmail.com`**.

Il est créé **sans mot de passe utilisable** : son empreinte est celle d'un secret
aléatoire jamais affiché, jamais transmis, jamais écrit. Le compte est donc
inutilisable tant que vous n'avez pas choisi de mot de passe. C'est délibéré —
c'est la seule façon qu'aucun secret ne traverse une conversation.

## Choisir votre mot de passe

### La méthode recommandée : `--generer`

```powershell
cd Backend
.\.venv\Scripts\python.exe -m src.modules.platform.admin reinitialiser-mot-de-passe `
    --email rhonekane@gmail.com `
    --motif "Ouverture du backoffice" `
    --generer
```

La commande **génère** un mot de passe et l'affiche **une seule fois**, après avoir
vérifié qu'il est bien recorded. Copiez-le : il ne sera plus jamais montré.

**Prouvez cette méthode avant `--generer`** — elle est la seule qui n'ait pas
d'entrée àhavoir.

### Pourquoi pas la saisie masquée

`getpass` est le mécanisme prévu, mais sur un terminal que le programme ne
contrôle pas il lit **en echo**, et **une entrée vide est acceptée sans erreur**.
Un compte se retrouve alors avec un mot de passe que personne ne connaît — et
l'échec n'apparaît qu'à la connexion, où l'opérateur conclut à tort que son mot de
passe est erroné.

La commande vérifie désormais ce qu'elle a enregistré, avant de valider : un
hachage étant irréversible, une saisie captée de travers ne se révélerait
sinon qu'au moment de se connecter. En cas d'échec de la vérification, **rien
n'est conservé**.

### Saisie masquée (si vous la préférez)

Sur le serveur, dans le dossier `Backend` :

```powershell
cd Backend
.\.venv\Scripts\python.exe -m src.modules.platform.admin reinitialiser-mot-de-passe `
    --email rhonekane@gmail.com `
    --motif "Ouverture du backoffice"
```

La commande affiche `Mot de passe du compte plateforme :` et **attend une saisie
masquée** — rien n'est écrit dans l'historique du shell, et rien ne s'affiche à
l'écran.

Les sessions ouvertes avec l'ancien mot de passe sont **révoquées**, et le
compte est marqué « changement de mot de passe obligatoire ».

Si vous préférez ne pas saisir, fournissez le mot de passe par variable
d'environnement (utile en intégration continue) :

```powershell
$env:PLATFORM_ADMIN_PASSWORD = "…"
.\.venv\Scripts\python.exe -m src.modules.platform.admin reinitialiser-mot-de-passe `
    --email rhonekane@gmail.com --motif "Ouverture du backoffice"
Remove-Item Env:\PLATFORM_ADMIN_PASSWORD
```

**Jamais en argument de ligne de commande** : la ligne de commande est visible dans
l'historique du shell *et* dans la liste des processus.

## Commandes disponibles

| Commande | Effet |
|---|---|
| `lister` | Comptes, rôle, statut, état de la 2FA, dernier login. **Aucun secret.** |
| `creer-super-admin --email <e> --motif <m>` | Crée le compte, ou le met à niveau s'il existe (idempotent) |
| `reinitialiser-mot-de-passe --email <e> --motif <m>` | Réinitialise le mot de passe et **révoque les sessions** |
| `reinitialiser-2fa --email <e> --motif <m>` | Efface le secret TOTP et les codes de secours, révoque les sessions |

`--motif` est **obligatoire** sur toute action : il est écrit au journal d'audit
plateforme, avec l'acteur `operateur@localhost`. Une réinitialisation sans motif
serait une trace inexploitable.

## Garde-fous

- **Pas de confirmation interactive.** Ces commandes supposent un accès serveur,
  et chaque action est journalisée. Le `--motif` vaut la trace.
- **Refus en production.** Si `ENVIRONMENT` vaut `PROD` ou `PRODUCTION`, la
  commande **refuse de s'exécuter** sans l'option explicite
  `--autorise-en-production`. Réinitialiser un accès en production est une prise
  de contrôle légitime — c'est aussi exactement ce que ferait un attaquant
  ayant gagné un accès.
- **Journal d'audit** : chaque action écrit une entrée (acteur, cible, motif,
  avant/après). Le journal est **immuable** — la triggers SQL interdit le
  `TRUNCATE`.

## Ce que ces commandes ne font pas

Elles ne **créent pas** de Super Admin si la base plateforme n'est pas à jour : le
rôle `SUPER_ADMIN_PLATEFORME` doit exister. En son absence, la commande s'arrête
avec un message explicite plutôt que de créer un compte sans rôle — un compte sans
rôle ne pourrait rien faire, et le défaut serait observé bien plus tard.

## Incident en cours

Le flux d'enrôlement 2FA est **incomplet** : la connexion d'un compte sans 2FA
active émet bien un jeton d'enrôlement, mais la route de préparation renvoie une
erreur serveur. L'état exact et l'ordre de reprise sont dans `docs/PROGRESS.md`,
en tête de fichier.

Tant que ce correctif n'est pas livré, **un seul accès plateforme reste
utilisable**, et c'est une raison de plus pour ne pas multiplier les comptes
Super Admin.