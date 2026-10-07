# 04 — Fonctionnalités manquantes : catalogue d'expert métier

> **Date** : 4 octobre 2026 · **Règle** — chaque ligne a été croisée avec le code
> existant avant d'être proposée. La colonne **Déjà présent ?** indique
> explicitement ce que le backend et le frontend couvrent **aujourd'hui**.
>
> **Priorité** — P0 indispensable avant mise en production · P1 important ·
> P2 confort.
> **Effort** — S (≤ 3 j) · M (≤ 2 semaines) · L (> 2 semaines).
>
> **Deux avertissements de méthode :**
> 1. **La_rows P0 de ce catalogue ne remplacent pas les corrections de bugs du
>    doc 01.** Un module d'imagerie sur une liste de factures qui renvoie 500
>    n'est pas un progrès. L'ordre du doc 05 est imperative.
> 2. **Le formulaire médicaments (14 molécules) n'est pas une pharmacopée.**
>    C'est un point de départ technique. Aucune prescription réelle ne doit être
>    délivrée sans relecture d'un pharmacien — c'est une obligation, pas une
>    précaution.

---

## Vue d'ensemble

| Axe | Proposées | Déjà dans le code | Priorité dominante |
|---|---|---|---|
| A. Blocages du cahier des charges | 6 | 0 | 🔴 P0 |
| B. SaaS & plateforme | 9 | 1 partiel | P0 (quotas) → P2 |
| C. Clinique | 16 | 3 partiels | 🔴 P0 (consentement) → P1 |
| D. Laboratoire de prothèses | 5 | 0 | P1 |
| E. Organisation du cabinet | 6 | 1 partiel | P1 |
| F. Hygiène & conformité | 4 | 0 | 🔴 P0 (traçabilité) |
| G. Finance | 9 | 3 partiels | P1 |
| H. Communication & fidélisation | 7 | 0 | P1 |
| I. Sécurité & données de santé | 8 | 3 partiels | 🔴 P0 |
| J. Technique & expérience | 8 | 2 partiels | P2 |
| **Total** | **78** | | |

---

## A. Ce que le cahier des charges initial n'a jamais couvert

Les 6 trous les plus coûteux, parce qu'ils sont **demandés par le premier patient**
que le logiciel accompagnera.

| # | Fonctionnalité | Description | Valeur métier | Backend | Frontend | Prio | Effort | Déjà présent ? |
|---|---|---|---|---|---|---|---|---|
| A1 | **Consentement éclairé signé** | Le patient signe (tablette) un consentement par acte ou par plan de traitement, versionné et horodaté, avant toute intervention | **Obligation légale.** Sans lui, l'assentement n'est pas demontrable | `consentements` + `signature_manuscribee` | Lecteur dans la consultation, sortie PDF | **P0** | M | ❌ aucun |
| A2 | **Radiographies & imagerie** | Stockage de panoramiques, rétro-alvéolaires, photos intra-orales ; visionneuse avec annotations | **Le dentiste ne peut pas prescrire un traitement sans voir le cliché.** Bloque l'implantologie, l'orthodontie, l'endodontie | Stockage objet (S3/MinIO) + `examens_imagerie` + vignettes | Visionneuse avec zoom, comparaison avant/après | **P0** | **L** | ❌ aucun — et **aucune couche de stockage de fichiers n'existe** (cf. doc 03 B1.4) |
| A3 | **Plan de traitement multi-séances** | Un plan chiffré en N actes, avec validation par le patient, suivi d'avancement, et facturation par séance | Évite la facturation « à la volée » qui est illisible pour le patient | `plans_traitement` + `lignes_plan` + `lignes_facture.plan_id` | Vue « qui en est à quelle séance » | **P0** | **L** | 🟡 partiel — `consultations` existe, aucun plan |
| A4 | **Suivi post-opératoire & complications** | Alerte à J+1/J+7/J+30 après une extraction ou une chirurgie, fiche de suivi, signalement de complication | Le suivi post-op est une obligation de bonne pratique **et** le moment où se joue la réputation | `suivis_post_op` + tâche planifiée | Timeline dans le dossier, bouton « signaler un incident » | P1 | M | ❌ aucun |
| A5 | **Contrôle périodique / rappels** | Rappeler chaque patient selon son dernier détartrage (6 mois), contrôle annuel, radiographie de contrôle | Remplit l'agenda des trous et fidélise. **Revenu récurrent, non facturable spontanément** | `recall` + tâche planifiée | Vague de rappels, export | P1 | M | ❌ aucun |
| A6 | **Certificats & courriers** | Génération d'arrêt de travail, certificat de scolarité, lettre de confrère, courrier d'orientation | Un geste's outil : le cabinet en fait tous les jours | Modèles + export PDF | Éditeur avec variables patient | P2 | S | ❌ aucun |

---

## B. SaaS & plateforme

| # | Fonctionnalité | Description | Valeur métier | Backend | Frontend | Prio | Effort | Déjà présent ? |
|---|---|---|---|---|---|---|---|---|
| B1 | **Utilisateurs du cabinet** | CRUD, invitation, activation, désactivation, réinitialisation de mot de passe | **La décision métier n°1.** Sans elle, un cabinet est mono-utilisateur | `POST/GET/PATCH/DELETE /utilisateurs` | Page déjà construite (état « indisponible ») | **P0** | **L** | 🔴 **404 — le service backend n'existe pas** (doc 01 B4) |
| B2 | **Plans & quotas** | Catalogue de plans (Essentiel/Pro/Cabinet), limites par plan (nb utilisateurs, stockage, RDV/mois) |.Modèle de revenu. **Bloque aussi la vente** : sans plafond, un client 500 utilisateurs coûte le même qu'un client 2 | `plans`, `abonnements`, `quotas` + middleware | Écran « votre plan » + alerte de limite | **P0** | M | ❌ aucun (`/master/societes` a `actif`, pas de plan) |
| B3 | **Facturation de l'éditeur** | Éditer la facture plateforme, encaisser (Wave/OM/carte), rapprocher | Sans lui, le métier n'est pas un métier | `abonnements` + `paiements_plateforme` | Page backoffice | P1 | **L** | ❌ aucun |
| B4 | **Personnalisation par cabinet** | Logo (déjà en base), couleurs, en-tête d'ordonnance/facture, tampon, signature numérique | Le document imprimé **représente** le cabinet. Un document générique fait amateur | `parametres_cabinet` (JSON) + gabarits PDF | Éditeur de branding + aperçu du document | P1 | M | 🟡 `logo_url` existe, pas d'éditeur |
| B5 | **Personnalisation des rôles** | Rôles système + rôles personnalisés par tenant | Évite que l'administrateur écrive du SQL pour accommodated un remplaçant | `POST /rbac/roles` + `DELETE` | Page rôles existante (🔴 500) | **P0** | S | 🟡 **création OK, suppression absente** |
| B6 | **Multi-sites / multi-cabinets** | Un groupe de cliniques, plusieurs sites sous un même compte, RBAC par site | Cible commerciale réelle des groupes | `utilisateur_cabinet` + `cabinet_id` sur les tables métier | Sélecteur de site global | **P0** (décision 1) | **L** | 🟡 sites existent comme `cabinets`, rattachement non |
| B7 | **Export / portabilité des données** | Export complet du cabinet (CSV/JSON/PDF), emigration vers un autre hébergeur | **Obligation contractuelle + RGPD** : le client doit pouvoir récupérer ses données | Job d'export + téléchargement signé | Page « Mes données » | **P0** | M | ❌ aucun |
| B8 | **Import de données existantes** | Import patients, RDV, factures depuis Excel / autre logiciel (Dexter, Owimmo, logiciel local) | **Le frein n°1 à la vente.** Un cabinet ne veut pas ressaisir 3 000 patients | Job d'import + mapping colonnes + rapport d'anomalies | Assistant d'import en 4 étapes | P1 | **L** | ❌ aucun |
| B9 | **Aide en ligne & support** | Base de connaissances, guide du premier jour, contact support dans l'app | Réduit le coût de support, accélère la prise en main | Aucun (statique) | Pages d'aide + bouton support | P2 | S | ❌ aucun |

---

## C. Clinique

### C.1 Ce qui existe déjà — à ne pas re-proposer

| Fonctionnalité | État |
|---|---|
| Dossier médical | ✅ `dossiers_medicaux`, antécédents, états généraux |
| Odontogramme | ✅ 11 endpoints, dents, faces, historique, **charting parodontal** |
| Consultations & actes | ✅ 12 endpoints, actes réalisés, signatures |
| Ordonnances | ✅ 8 endpoints, lignes de prescription, contrôle d'interaction (14 molécules) |
| Rendez-vous | ✅ 12 endpoints, **contrainte d'exclusion PostgreSQL** sur le fauteuil, créneaux libres |
| Statuts terminaux qui libèrent le fauteuil | ✅ logique de service correcte |

### C.2 À ajouter

| # | Fonctionnalité | Description | Valeur métier | Backend | Frontend | Prio | Effort | Déjà présent ? |
|---|---|---|---|---|---|---|---|---|
| C1 | **Photos avant/après** | Galerie attachée à une dent ou un plan de traitement, comparaison | Preuve de résultat, marketing, dossier médico-légal | `medias` lié à `dents`/`consultations` | Vue comparative avec slider | P1 | M | 🟡 `signature_url` existe, pas de média |
| C2 | **Questionnaire médical pré-consultation** | Le patient remplit le formulaire (allergies, traitements en cours) avant le RDV via lien | **Gain de temps réel en fauteuil** + dossier complet dès l'arrivée | `questionnaires`, `reponses` | Lien public, Edition en consultation | P1 | M | ❌ aucun |
| C3 | **Devis alternatifs** | Plusieurs options de traitement chiffrées (conservatrice / prothétique), le patient choisit | **Décision éclairée = valeur moyenne supérieure.** Argumentaire pour l'acceptation | `devis` multiples par consultation | Comparateur côte à côte | P1 | M | 🟡 `devis` existe, pas de regroupement par consultation |
| C4 | **Pédodontie — carnet de l'enfant** | Dents permanentes (46, 61, 64…) **et** temporaires (51, 71, 74…), statut de la dent de lait, eruption, scellement des sillons | La moitié d'une clientèle de cabinet familial. **Impossible aujourd'hui de noter une dent temporaire** | `Odontogramme` par typologie de dent | Affichage 20 dents + 20 temporaires | P1 | **L** | ❌ **les dents temporaires n'existent pas dans le modèle** — à vérifier en priorité |
| C5 | **Suivi orthodontique** | Appareillage, date de pose, activations mensuelles, durée totale, bilan de fin | La croissance du chiffre d'affaires : le traitement le plus long et le plus rentable | `traitements_ortho` + activations | Timeline de traitement | P1 | M | ❌ aucun |
| C6 | **Urgences & urgences** | File d'attente dédiée, triage, « douleur » comme motif, sortie rapide sans dossier complet | Le cabinet perd de l'argent sur chaque patient d'urgence qui part sans être vu | `rdv.priorite` + file dédiée | Bandeau « urgence » dans l'agenda | P1 | S | 🟡 `rdv` a un motif, pas de priorité |
| C7 | **Protocoles de soins & modèles** | Modèles de comptes rendus, protocole par type d'acte, checklist de stérilisation intégrée | Cohérence de la prise en charge entre praticiens,gain de temps | `protocoles`, `modeles_documents` | Insertion en un clic | P2 | M | ❌ aucun |
| C8 | **Fiches de liaison / adressage** | Lettre de confrère sortante, compte rendu de correspondence,Orientation | Crée du réseau et évite les doublons d'examens | `courriers` | Modèle de courrier | P2 | S | ❌ aucun |
| C9 | **Templates de prescription par pathologie** | « Amoxicilline 500 mg, 3×/j, 7 j » pré-rempli, avec la posologie officielle | **Sécurité posologique** : le risque le plus grave en pratique dentaire | `protocoles_ordonnance` (clinique) | Prescriptions en 1 clic | P1 | S | 🟡 formulaire médicaments existe, pas de protocole |
| C10 | **Gestion des incidents & réclamations** | Fiche de réclamation, action corrective, analyse | **Obligation de matériovigilance.** Le dentiste est responsable de ses actes | `incidents` | Formulaire + tableau de bord | P1 | M | ❌ aucun |
| C11 | **Accordéon : signer le devis** | Signature électronique du devis / du plan de traitement par le patient | **Sans signature, pas de engagement.** Rend le devis opposable | `devis.signature` + hash | Signature sur tablette | **P0** | S | ❌ aucun |
| C12 | **Résultats de laboratoire prothétique** | Casier par acteur | Perte de prothèses = perte financière directe | `labos`, `bon_travail` | Suivi des envois | P1 | M | ❌ aucun |
| C13 | **Archives & ICD** | Archivage à N ans, ICD codée, recherche dans l'archive | **Obligation légale de conservation.** Dossier lost = dossier non opposable | `icd`, `archives` | File des archives | P1 | M | ❌ aucun |
| C14 | **Mails et rappels automatiques** | Confirmation de RDV par email 24 h avant, rappel J-1 | **Réduit le taux de non-présentation** (15-25 % dans beaucoup de cabinets) | Tâche planifiée + SMTP | Réglage par type de RDV | P1 | M | ❌ aucun |
| C15 | **Réservation en ligne par le patient** | Lien public, créneaux réservés par type d'acte et durée | **Canal d'acquisition.** Le patient réserve sans appeler | `slots publics` | Formulaire public | P1 | **L** | ❌ aucun |
| C16 | **Tableau de charge / productivité** | actes par praticien, taux de remplissage fauteuils, CA par praticien | **Aide à la décision commerciale** : qui rend, où investir | `stats` agrégées | Tableau de bord analytique | P2 | M | ❌ aucun |

---

## D. Laboratoire de prothèses

| # | Fonctionnalité | Description | Valeur métier | Backend | Frontend | Prio | Effort | Déjà présent ? |
|---|---|---|---|---|---|---|---|---|
| D1 | **Bons de travail prothèse** | Demande adressée au labo (type de prothèse, dents, shade, deadline) avec impression de commande | **Remplace le papier.** Sans traçabilité, un litige sur une prothèse est indéfendable | `bons_travail` + `lignes_bon` | Création depuis la consultation, impression | P1 | M | ❌ aucun |
| D2 | **Suivi envois / retours** | Statuts : envoyé, reçu labo, en fabrication, retourné, posé | **Évite les prothèses perdues** (cause n°1 de perte sèche en prothèse) | `mouvements_bon` | Timeline sur le bon | P1 | S | ❌ aucun |
| D3 | **Référentiel prothèses & prix** | Catalogue des types de prothèses (couronne, bridge, prothèse totale) avec prix dentiste | Évite la saisie manuelle, sécurise la marge | `nomenclature_prothese` | Autocomplétion | P1 | S | 🟡 `actes_nomenclature` existe, pas de spécialisation prothèse |
| D4 | **Fournisseurs de laboratoire** | Répertoire des labos, contact, délai moyen, notes | Compare les labs, sécurise les délais | `fournisseurs` | Fiche fournisseur | P2 | S | ❌ aucun |
| D5 | **Coût prothèse par patient** | Coût réel (labo + matière) vs prix payé | **Sans ça, la prothèse est à perte.** Beaucoup de cabinets ne le savent pas | `couts` agrégés | Marge par acte | P1 | M | ❌ aucun |

---

## E. Organisation du cabinet

| # | Fonctionnalité | Description | Valeur métier | Backend | Frontend | Prio | Effort | Déjà présent ? |
|---|---|---|---|---|---|---|---|---|
| E1 | **File d'attente temps réel** | Qui est arrivé, qui est en fauteuil, qui attend depuis combien de temps | **L'indicateur que le patient regarde en entrant.** Supprime les tensions à l'accueil | WebSocket + `etat_file` | Écran d'accueil | P1 | M | ❌ aucun (agenda statique) |
| E2 | **Tableau d'affichage / écran d'attente** | Écran patient avec RDV du jour, motifs d'attente, advertizing cabinet | Réduit le stress perçu, promeut les VPNs | API dedicate | Vue plein écran | P2 | S | ❌ aucun |
| E3 | **Planning des fauteuils & salles** | Vue par ressource, pas par praticien : affecter une salle/fauteuil au RDV | Optimise le taux d'occupation (objectif 80 %) | `rdv.fauteuil_id`, `salle_id` | Vue Planning par ressource | P1 | M | 🟡 `creneaux_fauteuil` existe, pas d'affectation au RDV |
| E4 | **Congés & remplacements** | Déclarer les absences d'un praticien, réaffecter ses RDV | Évite les RDV orphelins | `absences` + `reaffectation_rdv` | Vue calendrier praticiens | P1 | M | 🟡 `disponibilites` existe (travail), pas d'absence |
| E5 | **Tâches internes & to-do** | Liste de tâches par cabinet, assignée, avec échéance | Évite les petites choses qui ne se font jamais | `taches` | Panneau tâches | P2 | S | ❌ aucun |
| E6 | **Passation entre praticiens** | Note de passation : ce qui a été fait, ce qui reste, alertes | Évite les trous dans les plans longs (couronnes → prothèse) | `notes_passation` | Bloc dans le dossier | P1 | S | ❌ aucun |

---

## F. Hygiène & conformité

> **Axe le plus sous-estimé du cahier des charges.** Un cabinet qui ne peut pas
> prouver la stérilisation de ses instruments est, en France, **hors la loi**
> (décret 2001-654, obligation de traçabilité). En Afrique francophone, c'est
> une exigence de la autorité sanitaire nationale et un critère d'accréditation.

| # | Fonctionnalité | Description | Valeur métier | Backend | Frontend | Prio | Effort | Déjà présent ? |
|---|---|---|---|---|---|---|---|---|
| F1 | **Traçabilité de la stérilisation** | Un cycle = date, autoclave, opérateur, durée, température, **instruments** ; validation après chaque patient | **Obligation légale.** Le dossier médical doit permettre de prouver qu'un instrument a été stérilisé | `cycles_sterilisation` + `instruments` + `instrument_cycles` | Saisie au fauteuil, registre, export | **P0** | **L** | ❌ aucun |
| F2 | **Registre des déchets médicaux (DASRI)** | Registre journalier des déchets, quantité, transporteur, incinération | **Obligation légale** (DASRI — France) | `dechets_dasri` | Registre + export | P1 | M | ❌ aucun |
| F3 | **Contrôle qualité & maintenance** | Maintenance préventive des équipements, contrôle des ampoules, rapport | Prévient la panne en plein RDV (perte de chiffre direct) | `maintenances` | Calendrier de maintenance | P1 | M | 🟡 `fauteuils.état` existe (« en panne »), pas de suivi |
| F4 | **Matériovigilance** | Déclaration d'incident sur un dispositif médical (obligatoire) | **Obligation réglementaire** | `incidents` | Formulaire | P1 | S | ❌ aucun (cf. C10) |

---

## G. Finance

| # | Fonctionnalité | Description | Valeur métier | Backend | Frontend | Prio | Effort | Déjà présent ? |
|---|---|---|---|---|---|---|---|---|
| G1 | **Clôture de caisse** | Session de caisse (Z) : ouverture, recettes par mode, écart de species, clôture avec signature | **Obligation comptable.** Aucune clôture = aucune preuve de recette du jour | `sessions_caisse` + `clotures` | Écran Z, impression | **P0** | M | 🟡 `factures/journal-caisse` existe, pas de clôture ni d'écart de species |
| G2 | **Rapprochement bancaire** | Rapprocher les paiements Wave/OM/carte avec les relevés | **Les paiements mobiles sont très répandus au Sénégal et en Côte d'Ivoire** — sans rapprochement, l'encaissement est un flux aveugle | `rapprochements` | Import CSV, suggestion automatique | P1 | M | 🟡 `Paiement.reference` existe (réf transaction), pas de rapprochement |
| G3 | **Acomptes & plans de paiement** | Acompte à la pose, échéancier mensuel (déjà existant) | **Réduit l'impayé** et lisse la trésorerie | 🟡 existant (`echelonnement`) | — | fait | M | ✅ **déjà présent** |
| G4 | **Tiers payant & assurances** | Bordereau de remboursement, suivi des impayés, rejets, résiliation | **Double le panier moyen.** Beaucoup de cabinets refusent faute de suivi | `tiers_payants`, `bordereaux` | Suivi des créances, relance | P1 | **L** | ❌ aucun |
| G5 | **Rétrocessions praticiens** | Pourcentage par praticien ou acte, calcul de la part associate | **Modèle économique majeur** en cabinet de groupe | `retrocessions`, `reversements` | Simulation, bulletin | P1 | **L** | ❌ aucun |
| G6 | **Charges & dépenses du cabinet** | Loyers, salaires, Fournitures, avec categories | Sans suivi des charges, le CA ne dit rien du bénéfice | `depenses`, `categories_depenses` | Saisie + tableau de bord | P1 | M | ❌ aucun |
| G7 | **TVA & fiscalité locale** | Taux par acte, declarations périodiques, ventilation TVA | **Obligation fiscale.** Une erreur = redressement | `parametres_tva` | Paramétrage, export | P1 | M | 🟡 `Facture.montant_tva` existe, pas de paramétrage par taux |
| G8 | **Paiements mobiles** | Wave, Orange Money, carte — intégration + reçu | **Obligatoire au Sénégal/Côte d'Ivoire** | `modes_paiement` + webhook | Choix + reçu | P1 | M | 🟡 `ModePaiementEnum` inclut `MOBILE_MONEY`, mais **aucun provider intégré** |
| G9 | **Export comptable** | Export des écritures au format compatible avec les logiciels comptables du pays | Remplace la double saisie | `exports` | Génération + téléchargement | P1 | M | ❌ aucun |

---

## H. Communication & fidélisation

| # | Fonctionnalité | Description | Valeur métier | Backend | Frontend | Prio | Effort | Déjà présent ? |
|---|---|---|---|---|---|---|---|---|
| H1 | **Modèles de SMS/email personnalisables** | Modèles avec variables (`{{patient.prenom}}`, `{{rdv.date}}`), envoi unitaire ou en lot | **Le marketing ne s'improvise pas** ; des modèles font la différence | `modeles_messages` | Éditeur de modèles, envoi | P1 | M | ❌ aucun |
| H2 | **Campagnes ciblées** | « Patients à jour depuis 2 ans », « Rendez-vous jamais honorés », « Traitement en cours interrompu » | **Remplit l'agenda existant** — souvent plus rentable que d'en chercher de nouveaux | `campagnes` + `ciblage` | Sélection → envoi | P1 | M | ❌ aucun |
| H3 | **Satisfaction & réclamations** | Enquête par email/SMS après RDV, NPS, tableau de bord | **Mesurer avant d'agitner.** La réclamation connue coûte 10 fois moins cher que perdue | `enquetes`, `reponses` | Dashboard satisfaction | P2 | M | ❌ aucun |
| H4 | **Confirmation de RDV** | SMS/email J-7 et J-1 avec lien d'annulation | **Réduit les absents de 15-25 %** | Tâche planifiée | Automatique, réglage | P1 | S | ❌ aucun |
| H5 | **Relances d'impayés** | Relance automatique des factures échues, ton progressif, mention du dernier montant | **Élimine les impayés invisibles** | Tâche planifiée + fichier | Automatique, historique | P1 | S | 🟡 `Date_echeance` existe, pas de relance |
| H6 | **Parrainage & fidélité** | « Un ami Recommendations » : un patientExisting en amène un autre, les deux ont droit à un détartrage offert | **Croissance organique à coût quasi nul** | `parrainages` | Page publique | P2 | S | ❌ aucun |
| H7 | **Anniversaires** | « Joyeux anniversaire, −20 % ce mois-ci » | Simple, efficace, gratuit | Tâche planifiée | Automatique | P2 | S | ❌ aucun |

---

## I. Sécurité, légal & données de santé

| # | Fonctionnalité | Description | Valeur métier | Backend | Frontend | Prio | Effort | Déjà présent ? |
|---|---|---|---|---|---|---|---|---|
| I1 | **Journal d'audit immuable** | Append-only, hash chaîné : toute modification d'un dossier, d'une facture, d'un droit est tracée | **Se defence legally.** En cas de litige, c'est la preuve | `audit_logs` → hash chain | Consultation + export | **P0** | M | 🟡 `AuditLogTenant` existe avec `resource_type` — **mais pas d'immutabilité** (update/delete non bloqués) |
| I2 | **Accès « bris de glace »** | Accès motivé, tracé, avec alerte à l'intéressé | **Obligation RGPD** : tout accès doit être justifié | `acces_exceptionnels` | Workflow de justification | **P0** | M | ❌ aucun |
| I3 | **Droit à l'effacement / portabilité** | Export complet, anonymisation d'un dossier, purge à échéance | **Obligation légale.** Refus = sanction | Job d'anonymisation | Page « Mes données » | **P0** | M | 🟡 cf. B7 |
| I4 | **Politique de rétention** | Délais par catégorie (dossier médical, factures, logs), purge automatique | **Obligation légale** — et elle protège le client contre un stockage infini | `politiques_retencion` + job | Page de configuration | P1 | M | ❌ aucun |
| I5 | **Sauvegarde & restauration par tenant** | Dump quotidien par base, restauration testée, rétention configurable | **Obligation de continuité.** Perdre le dossier d'un patient = perte de confiance irréversible | `pg_dump` planifié + restauration | Page « sauvegardes » | **P0** | M | ❌ aucun (seul le **verrou Windows** qui bloque `_psycopg` empêche aujourd'hui un dump fiable) |
| I6 | **2FA** | Code TOTP sur application d'authentification | **Protection de l'accès au dossier médical** | TOTP sur `utilisateurs` | Setup + vérification | **P0** | M | 🟡 **Le mécanisme existe déjà pour `super_admins`** (`tentatives_echouees`, `verrouille_jusqua`) — à porter sur les utilisateurs du tenant |
| I7 | **Révocation de sessions actives** | Liste des sessions (appareil, IP, dernière activité), révocation à distance | **En cas de vol d'ordinateur**, c'est le seul moyen d'arrêter l'accès | `GET /sessions`, `DELETE /sessions/{id}` | Page « Mes sessions » | **P0** | S | 🟡 `SessionUser` **existe déjà** en base (ip, user_agent, jti) — **il manque juste les endpoints** |
| I8 | **Politique de mots de passe renforcée** | Longueur, complexité, expiration, vérification de similarité | **Exigé par la plupart des référentiels de sécurité** | `parametres_securite` + validation | Indicateur de robustesse | P1 | S | 🟡 hash bcrypt présent, politique non paramétrable |

---

## J. Technique & expérience

| # | Fonctionnalité | Description | Valeur métier | Backend | Frontend | Prio | Effort | Déjà présent ? |
|---|---|---|---|---|---|---|---|---|
| J1 | **Mode hors-ligne / dégradé** | Cache local, file d'attente des écritures, synchronisation | **Répond directement au contexte « connexion parfois instable »** | — (client) + sync | Service worker, IndexedDB | **P0** | **L** | ❌ aucun |
| J2 | **Notifications temps réel** | WebSocket : nouveau RDV, message de la secrétaire, agenda modifié | Évite les clashes et l'attente | WebSocket / SSE | Abonnement | P1 | M | ❌ aucun |
| J3 | **Import / export CSV & PDF** | Pour tous les modules | **Le praticien veut ses données.** Utile pour les statistiques personnelles | Endpoints d'export (Excel/PDF) | Bouton download | P1 | S | 🟡 `ACTION_EXPORT` existe pour 3 modules, aucun endpoint |
| J4 | **Impression thermique** | Reçu de paiement 80 mm, ordonnance, bon de labo | **Attendu en cabinet** : 80 % des cabinets n'ont pas d'imprimante A4 près du fauteuil | — | CSS `@media print` | P1 | S | ❌ aucun |
| J5 | **Multilingue (français, wolof)** | Interface + documents en français/wolof | **Adaptation au contexte** — le wolof est la langue quotidienne de nombreux patients | Fichiers de langue | i18n (react-i18next) | P1 | **L** | ❌ aucun (tous les libellés sont en dur — doc 02 § 3.3) |
| J6 | **Recherche globale** | Un champ qui cherche patient, RDV, facture, dossier, acte | **La vitesse d'usage au quotidien** | `/recherche` | Palette (Ctrl+K existe déjà) | **P0** | M | 🟡 **la palette Ctrl+K existe** mais ne fait que naviguer dans les écrans, **aucune recherche de données** |
| J7 | **Accessibilité (RGAA)** | Contrastes, focus clavier, navigation clavier complète, ARIA | **Obligation pour les marchés publics**, bonne pratique sinon | — | Audit + correctifs | P1 | M | 🟡 tokens de contraste OK, pas d'audit |
| J8 | **Signature manuscrite sur tablette** | Patient et praticien signent sur l'écran | **Remplace le papier** dans un cabinet sans photocopieuse | Stockage du tracé | Composant de signature | **P0** | M | ❌ aucun (cf. A1, C11) |

---

## Synthèse de priorisation

### Les P0 — indispensables avant la première facture

> **Rappel : les P0 ci-dessous ne servent à rien tant que `GET /factures` renvoie
> 500 et qu'un cabinet neuf ne peut rien facturer.** Ces deux corrections
> viennent **avant** tout ce tableau.

| # | Fonctionnalité | Pourquoi P0 | Effort |
|---|---|---|---|
| B1 | Utilisateurs du cabinet | La décision métier n°1 est inopérante sans elle | **L** |
| B5 | Personnalisation des rôles | Créables mais non supprimables | S |
| B6 | Multi-sites / RBAC par site | Décision d'architecture n°1 | **L** |
| B2 | Plans & quotas | Sans plafond, le modèle de revenu n'existe pas | M |
| B7 | Export / portabilité | Obligation contractuelle + RGPD | M |
| A1 | Consentement signé | Obligation légale, absente | M |
| C11 | Signature du devis | Sans signature, pas d'engagement opposable | S |
| A2 | Imagerie & radiographies | **Le dentiste ne peut pas prescrire sans voir le cliché** — bloque l'implantologie, l'ortho, l'endodontie | **L** |
| A3 | Plans de traitement multi-séances | Évite la facturation à la volée illisible | **L** |
| F1 | Traçabilité de la stérilisation | **Obligation légale de stérilisation** | **L** |
| G1 | Clôture de caisse | Obligation comptable | M |
| I1 | Journal d'audit immuable | Sans preuve, pas de défense | M |
| I2 | Accès bris de glace | Obligation RGPD | M |
| I5 | Sauvegarde par tenant | Continuité d'activité | M |
| I6 | 2FA | Protection du dossier médical | M |
| I7 | Révocation de sessions | **La table existe déjà — 2 endpoints** | S |
| J1 | Mode hors-ligne | Contexte instable | **L** |
| J6 | Recherche globale de données | La palette existe, sans la recherche | M |
| J8 | Signature manuscrite | Remplace le papier | M |

### Ce qui est déjà partially présent (à ne pas compter deux fois)

- **Échelonnement / acomptes** (G3) — ✅ existant
- **Rôles personnalisés** (B5) — 🟡 création OK, suppression manque
- **Rotation et révocation des refresh tokens** (I7) — 🟡 table existe, endpoints manquent
- **Verrouillage après échecs** — 🟡 présent pour Super Admin, à porter sur les utilisateurs
- **Journal d'audit** (I1) — 🟡 table et lecture existent, pas d'immutabilité
- **Logo du cabinet** (B4) — 🟡 colonne existe, pas d'éditeur
- **Paiements mobiles** (G8) — 🟡 l'énumération existe, aucun provider

### Les 3 ajouts les moins attendus

1. **Traçabilité de la stérilisation (F1)** — le cahier des charges initial ne
   mentionne pas l'hygiène. C'est pourtant une **obligation légale** et un
   critère d'accréditation. On ne peut pas ouvrir un cabinet sans.
2. **Rapprochement des paiements mobiles (G2)** — au Sénégal et en Côte
   d'Ivoire, une part majeure des encaissements passe par Wave et Orange Money.
   Sans rapprochement bancaire, **le chiffre d'affaires du jour est un flux
   aveugle**.
3. **Mode hors-ligne (J1)** — demandé explicitement dans le contexte. Un logiciel
   de gestion qui perd la connexion en plein rendez-vous est un logiciel que le
   praticien contourne. C'est aussi le premier motif de désabonnement.
