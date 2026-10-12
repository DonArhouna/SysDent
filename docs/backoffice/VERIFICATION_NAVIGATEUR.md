# Vérification navigateur du tableau de bord

Cette page n'est **pas** un compte rendu : je n'ai pas de navigateur, donc je
n'ai rien vu. C'est une liste de ce qu'il faut regarder, avec ce qui serait
anormal. Un point coché veut dire « regardé », jamais « vérifié par moi ».

À faire sur le backoffice, session ouverte, avec l'onglet Réseau ouvert.

---

## 1. Layout

| Ce qu'il faut voir | Ce qui serait anormal |
|---|---|
| Une **sidebar** à gauche, avec les entrées de navigation | La page occupe toute la largeur, sans navigation |
| Une **navbar** en haut, avec la bascule de thème et le compte | Aucun bandeau supérieur ; impossible de changer de thème ni de sortir |
| Le contenu du tableau de bord **à l'intérieur** de ce cadre | Le tableau s'affiche seul, comme une page sans chrome |
| La sidebar **repliable** (icône de reduction) | La sidebar ne se replie pas, ou recouvre le contenu |

Référence : l'application client, même emplacement, mêmes proportions.

## 2. Onglet Réseau

| Ce qu'il faut voir | Ce qui serait anormal |
|---|---|
| **Un seul** `GET /api/v1/platform/stats/dashboard`, en **200** | Plusieurs appels identiques ; c'est le signe que l'écran refait l'agrégation |
| **Aucun 500** | Un 500 : le défaut est dans le backend, pas dans l'affichage |
| **Aucun 401 répété** | Deux 401 d'affilée sur la même requête : le client tente un rejeu après échec du renouvellement |
| Aucun 401 du tout si la session vient d'être ouverte | Un 401 isolé sur `/dashboard` : jeton périmé, il faut se reconnecter |

## 3. Les chiffres

| Ce qu'il faut voir | Ce qui serait anormal |
|---|---|
| Pour le statut **Actif**, **deux lignes distinctes** : le total, et en dessous la part « N sans base » | Une seule ligne, ou un total qui englobe les bases absentes sans le dire |
| La carte **Base absente**, avec la conséquence en legende (« le login de ces cabinets échoue ») | Aucun chiffre, ou un chiffrepresented comme un simple total |
| Les mêmes nombres dans l'onglet Réseau (dans le corps de la reponse 200) | L'écran affiche autre chose que ce que le serveur a renvoyé |

## 4. Erreur et vide

| Ce qu'il faut voir | Ce qui serait anormal |
|---|---|
| **Backend arrêté** : un message d'erreur et un bouton **« Réessayer »** | Un **0** quelque part. « 0 cabinet » pendant une panne affirme que la plateforme est vide : c'est un autre mensonge |
| **Plateforme vide** : « Aucun cabinet », et **pas** de bouton « Réessayer » | Un bouton « Réessayer » alors qu'il n'y a rien à réessayer |
| Après « Réessayer », backend relancé : les chiffres apparaissent | L'écran reste bloqué sur l'erreur |

## 5. Thèmes

| Ce qu'il faut voir | Ce qui serait anormal |
|---|---|
| Clair et sombre : mêmes **arrondis**, mêmes **couleurs** de liseré, mêmes cartes | Un arrondi ou une couleur qui change entre les deux thèmes |
| Les mêmes contrastes que le client | Un texte qui devient illisible sur fond sombre |
| La bascule de thème **persiste** après rechargement | Le thème revient à clair à chaque rechargement |

## 6. Tablette

| Ce qu'il faut voir | Ce qui serait anormal |
|---|---|
| La sidebar se replie en rail, ou devient un **drawer** avec overlay | La sidebar reste ouverte et mange la moitié de l'écran |
| Le bouton d'ouverture du drawer est dans la navbar | Aucun moyen d'ouvrir la navigation |
| Les cartes KPI se réorganisent en grille, sans débordement | Texte tronqué, carte qui déborde, scroll horizontal |

---

## Ce que je ne peux pas dire

- Que le rendu **ressemble** au client. Je n'ai comparé aucun pixel.
- Que les arrondis, espacements et couleurs sont **identiques**. C'est l'objet
  de `npm run design:parite`, qui n'existe pas encore.

Si un point coché ne correspond pas, le traceback du backend est la pièce à
lire d'abord : le journal du processus, dans la console qui l'a lancé.