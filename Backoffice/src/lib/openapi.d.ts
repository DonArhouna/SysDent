/* Fichier genere. Ne pas editer a la main.
   Source : openapi.json (Backend/scripts/exporter_openapi.py)
   Regenerer : npm run types:generer
   Verifier  : npm run contrat:verifier */
export interface paths {
    "/api/v1/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Audit Logs
         * @description Consulte le journal d'audit légal du cabinet (Réservé aux profils autorisés).
         *
         *     Accepte un jeton support en lecture seule : diagnostiquer « qui a touché à ce
         *     dossier, et quand ? » est précisément le besoin du support, et le journal ne
         *     contient pas de contenu clinique — uniquement qui a fait quoi.
         */
        get: operations["list_audit_logs_api_v1_audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Login
         * @description Connexion utilisateur.
         *
         *     Le cabinet est résolu via l'index Master `utilisateur_index`, le mot de passe
         *     est vérifié en base argon2, et une session persistée est créée pour rendre
         *     le token révocable. Le cookie HttpOnly est déposé pour les navigateurs.
         */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Logout
         * @description Déconnexion : révoque la session en base et supprime le cookie.
         *
         *     Avant cette correction, le logout ne faisait que supprimer le cookie : le
         *     refresh token restait rejouable pendant 7 jours depuis n'importe quel client.
         */
        post: operations["logout_api_v1_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Me
         * @description Profil de l'utilisateur connecté.
         *
         *     Les données sont lues en base, pas dans le JWT : un jeton est signé mais pas
         *     chiffré, et il circule dans les en-têtes et les journaux. Y placer l'email
         *     et le nom exposerait des données personnelles à quiconque peut lire un
         *     access token (proxy, trace APM,support). La lecture en base a l'avantage
         *     secondaire de refléter immédiatement un changement de nom ou de rôle.
         */
        get: operations["get_me_api_v1_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Refresh Token
         * @description Rotation du refresh token.
         *
         *     Le rôle et les permissions sont RELUS en base à chaque renouvellement.
         *     L'ancienne version accordait `role="ADMIN_CABINET"` et `permissions=["ALL"]`
         *     en dur : n'importe quel refresh token d'un compte déclassé ou désactivé
         *     remontait en administrateur de cabinet.
         */
        post: operations["refresh_token_api_v1_auth_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cabinets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Cabinets
         * @description Sites de la société, avec leurs compteurs de salles, fauteuils et praticiens.
         */
        get: operations["lister_cabinets_api_v1_cabinets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cabinets/{cabinet_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Cabinet */
        get: operations["get_cabinet_api_v1_cabinets__cabinet_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Cabinet
         * @description Modifie un site (adresse, téléphone, horaires d'ouverture, activation).
         */
        patch: operations["update_cabinet_api_v1_cabinets__cabinet_id__patch"];
        trace?: never;
    };
    "/api/v1/cabinets/{cabinet_id}/fauteuils": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Fauteuils
         * @description Fauteuils d'un site, toutes salles confondues.
         *
         *     C'est la vue qu'un écran de planning consomme : placer un patient demande
         *     de savoir quel fauteuil est libre, pas dans quelle salle il se trouve.
         */
        get: operations["lister_fauteuils_api_v1_cabinets__cabinet_id__fauteuils_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Rattachement
         * @description Rattachement d'un praticien à un site (actif ou clôturé).
         */
        get: operations["get_rattachement_api_v1_cabinets__cabinet_id__praticiens__praticien_id__rattachement_get"];
        put?: never;
        /**
         * Rattacher Praticien
         * @description Rattache un praticien à un site, ou rouvre un rattachement clôturé.
         */
        post: operations["rattacher_praticien_api_v1_cabinets__cabinet_id__praticiens__praticien_id__rattachement_post"];
        /**
         * Detacher Praticien
         * @description Clôt le rattachement d'un praticien à un site.
         *
         *     La ligne n'est pas supprimée : `date_fin` est renseignée et le
         *     rattachement devient inactif. Les consultations passées restent attribuables.
         */
        delete: operations["detacher_praticien_api_v1_cabinets__cabinet_id__praticiens__praticien_id__rattachement_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cabinets/{cabinet_id}/salles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Salles
         * @description Salles d'un site, avec le nombre de fauteuils par salle.
         */
        get: operations["lister_salles_api_v1_cabinets__cabinet_id__salles_get"];
        put?: never;
        /**
         * Creer Salle
         * @description Crée une salle dans un site.
         */
        post: operations["creer_salle_api_v1_cabinets__cabinet_id__salles_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cabinets/{cabinet_id}/salles/{salle_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Supprimer Salle
         * @description Supprime une salle **vide**.
         *
         *     Une salle qui contient encore des fauteuils est refusée : il faut d'abord
         *     les désactiver un par un.
         */
        delete: operations["supprimer_salle_api_v1_cabinets__cabinet_id__salles__salle_id__delete"];
        options?: never;
        head?: never;
        /** Update Salle */
        patch: operations["update_salle_api_v1_cabinets__cabinet_id__salles__salle_id__patch"];
        trace?: never;
    };
    "/api/v1/caisse/paiements-hors-session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Paiements Hors Session
         * @description Encaissements qui n'appartiennent à aucune session de caisse.
         *
         *     Ce sont les paiements antérieurs au déploiement des sessions. Les lister
         *     n'est pas les dissimuler : une somme qui n'entre dans aucune clôture est une
         *     somme dont personne ne répond, et c'est exactement le genre d'écart qu'une
         *     clôture doit faire apparaître.
         */
        get: operations["paiements_hors_session_api_v1_caisse_paiements_hors_session_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/caisse/session-courante": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Session Courante
         * @description Session ouverte, ou `null` s'il n'y en a pas.
         *
         *     L'écran d'accueil du caissier s'appuie dessus : il affiche « caisse
         *     fermée » et le montant du dernier dépôt tant qu'aucune session n'est ouverte.
         */
        get: operations["session_courante_api_v1_caisse_session_courante_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/caisse/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Sessions
         * @description Historique des sessions de caisse, de la plus récente à la plus ancienne.
         *
         *     **Elle grossit sans fin** : au moins une session par caissier et par jour,
         *     donc environ 1 100 par an pour trois caissiers. La plafonner à 50 sans page
         *     faisait disparaître les sessions anciennes sans le moindre message — le
         *     défaut « donnée absente présentée comme un zéro », ici sur l'historique
         *     comptable.
         */
        get: operations["lister_sessions_api_v1_caisse_sessions_get"];
        put?: never;
        /**
         * Ouvrir Session
         * @description Ouvre la session de caisse avec le dépôt d'espèces du tiroir.
         *
         *     Le dépôt déclaré par le caissier est sa responsabilité personnelle : ce n'est
         *     pas de l'argent du cabinet. C'est pour cela qu'il est memorandum du début et
         *     de la fin, et non compté dans les recettes.
         */
        post: operations["ouvrir_session_api_v1_caisse_sessions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/caisse/sessions/{session_id}/cloture": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cloturer Session
         * @description Clôture la session et fige ses totaux.
         *
         *     Les totaux par mode sont recopiés dans la session à cet instant : un
         *     encaissement ultérieur ne réécrira pas cette journée. L'écart d'espèces est
         *     calculé et conservé, avec son motif s'il y en a un.
         */
        post: operations["cloturer_session_api_v1_caisse_sessions__session_id__cloture_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/caisse/sessions/{session_id}/paiements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Paiements De La Session
         * @description Détail des encaissements d'une session, avec l'auteur de chacun.
         */
        get: operations["paiements_de_la_session_api_v1_caisse_sessions__session_id__paiements_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/consultations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Consultations
         * @description Liste paginée des consultations du cabinet.
         */
        get: operations["list_consultations_api_v1_consultations_get"];
        put?: never;
        /**
         * Demarrer Consultation
         * @description Démarre une consultation pour un patient (Étape 4 du CDC).
         */
        post: operations["demarrer_consultation_api_v1_consultations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/consultations/{consultation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Consultation
         * @description Détail d'une consultation.
         */
        get: operations["get_consultation_api_v1_consultations__consultation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Consultation
         * @description Met à jour l'examen clinique et le diagnostic (Étape 5 du CDC).
         */
        patch: operations["update_consultation_api_v1_consultations__consultation_id__patch"];
        trace?: never;
    };
    "/api/v1/consultations/{consultation_id}/actes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Actes
         * @description Liste les actes réalisés sur la consultation, avec leur montant.
         */
        get: operations["list_actes_api_v1_consultations__consultation_id__actes_get"];
        put?: never;
        /**
         * Create Acte
         * @description Saisit un acte réalisé. Le tarif est résolu depuis la nomenclature.
         */
        post: operations["create_acte_api_v1_consultations__consultation_id__actes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/consultations/{consultation_id}/annuler": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Annuler Consultation
         * @description Annule une consultation. Refusé si des actes ont été saisis : un acte réalisé
         *     est un acte physique, il se facture ou se corrige, il ne s'efface pas.
         */
        post: operations["annuler_consultation_api_v1_consultations__consultation_id__annuler_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/consultations/{consultation_id}/detail": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Consultation Detail
         * @description Consultation complète : actes, total facturable, durée réelle et alertes
         *     cliniques du patient (RG02 : l'état général est-il à jour ?).
         */
        get: operations["get_consultation_detail_api_v1_consultations__consultation_id__detail_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/consultations/{consultation_id}/terminer": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Terminer Consultation
         * @description Clôture la consultation. Un diagnostic principal est obligatoire (Étape 6).
         */
        post: operations["terminer_consultation_api_v1_consultations__consultation_id__terminer_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/consultations/{consultation_id}/total": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Total Consultation
         * @description Total facturable de la consultation (RG07).
         *
         *     Point d'entrée du pôle facturation : la facture sera générée à partir de ce
         *     montant, jamais ressaisi par la secrétaire.
         */
        get: operations["total_consultation_api_v1_consultations__consultation_id__total_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/consultations/actes/{acte_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Delete Acte
         * @description Supprime un acte saisi par erreur. La trace d'audit est conservée.
         */
        delete: operations["delete_acte_api_v1_consultations_actes__acte_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Acte
         * @description Corrige un acte réalisé (quantité, dent, tarif négocié).
         */
        patch: operations["update_acte_api_v1_consultations_actes__acte_id__patch"];
        trace?: never;
    };
    "/api/v1/devis": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Devis
         * @description Liste paginée des devis.
         */
        get: operations["list_devis_api_v1_devis_get"];
        put?: never;
        /**
         * Creer Devis
         * @description Émet un devis (brouillon). Les montants sont calculés depuis les lignes.
         */
        post: operations["creer_devis_api_v1_devis_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/devis/{devis_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Devis
         * @description Détail d'un devis avec ses lignes.
         */
        get: operations["get_devis_api_v1_devis__devis_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/devis/{devis_id}/convertir": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Convertir Devis
         * @description RG14 : convertit un devis accepté en facture, lignes comprises. Une seule fois.
         */
        post: operations["convertir_devis_api_v1_devis__devis_id__convertir_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/devis/{devis_id}/statut": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Changer Statut Devis
         * @description Fait avancer le cycle : BROUILLON → ENVOYE → ACCEPTE/REFUSE.
         *
         *     Le passage à ACCEPTE exige `signature_patient: true` et une validité en
         *     cours. Un devis refusé ne se rouvre pas.
         */
        post: operations["changer_statut_devis_api_v1_devis__devis_id__statut_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/disponibilites/{disponibilite_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Supprimer Disponibilite
         * @description Retire une plage déclarée.
         */
        delete: operations["supprimer_disponibilite_api_v1_disponibilites__disponibilite_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/factures": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Factures
         * @description Liste paginée des factures du cabinet.
         */
        get: operations["list_factures_api_v1_factures_get"];
        put?: never;
        /**
         * Facturer Libre
         * @description Émet une facture hors consultation (produit, forfait, prestation directe).
         */
        post: operations["facturer_libre_api_v1_factures_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/factures/{facture_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Facture
         * @description Détail d'une facture : lignes, paiements, statut et reste à payer.
         */
        get: operations["get_facture_api_v1_factures__facture_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/factures/{facture_id}/annuler": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Annuler Facture
         * @description Annule une facture sans encaissement. Interdite si des paiements existent.
         */
        post: operations["annuler_facture_api_v1_factures__facture_id__annuler_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/factures/{facture_id}/echelonnement": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Echelonnement
         * @description Plan d'échelonnement de la facture, échéances comprises (null si absent).
         */
        get: operations["get_echelonnement_api_v1_factures__facture_id__echelonnement_get"];
        put?: never;
        /**
         * Creer Echelonnement
         * @description Crée le plan d'échelonnement du RESTE À PAYER et génère les échéances
         *     (RG08). Un seul plan actif par facture.
         */
        post: operations["creer_echelonnement_api_v1_factures__facture_id__echelonnement_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/factures/{facture_id}/paiements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Encaisser
         * @description Encaisse un paiement (multi-moyens : espèces, Wave, Orange Money, chèque...).
         *
         *     Sans `echeance_id` : paiement libre dans la limite du reste à payer.
         *     Avec `echeance_id` : montant EXACT du reste dû sur l'échéance.
         *     Le reçu est numéroté automatiquement (RECU-AAAAMMJJ-NNNN).
         */
        post: operations["encaisser_api_v1_factures__facture_id__paiements_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/factures/consultation/{consultation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Facturer Consultation
         * @description Émet la facture d'une consultation terminée depuis ses actes réalisés.
         *
         *     Les lignes sont importées des actes, le total est recalculé (RG07) :
         *     le montant n'est jamais fourni par le client. Une consultation déjà
         *     facturée est refusée (anti-doublon).
         */
        post: operations["facturer_consultation_api_v1_factures_consultation__consultation_id__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/factures/journal-caisse": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Journal Caisse
         * @description Journal de caisse : tous les encaissements avec facture, patient et mode.
         *     ⚠️ Déclaré AVANT `/factures/{facture_id}` : FastAPI teste les routes dans
         *     l'ordre de déclaration, le littéral serait sinon absorbé comme un UUID.
         */
        get: operations["journal_caisse_api_v1_factures_journal_caisse_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/fauteuils/{fauteuil_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Supprimer Fauteuil
         * @description Supprime un fauteuil **jamais utilisé**.
         *
         *     Un fauteuil ayant servi à une consultation est refusé
         *     (`FAUTEUIL_UTILISE`) : le désactiver préserve l'historique du lieu du soin.
         */
        delete: operations["supprimer_fauteuil_api_v1_fauteuils__fauteuil_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Fauteuil
         * @description Renomme un fauteuil, ajuste ses équipements, ou l'active / désactive.
         */
        patch: operations["update_fauteuil_api_v1_fauteuils__fauteuil_id__patch"];
        trace?: never;
    };
    "/api/v1/fauteuils/{fauteuil_id}/reactiver": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reactiver Fauteuil
         * @description Remet en service un fauteuil désactivé.
         */
        post: operations["reactiver_fauteuil_api_v1_fauteuils__fauteuil_id__reactiver_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/master/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Master Login
         * @description Connexion Super Admin à la console de plateforme (base Master).
         */
        post: operations["master_login_api_v1_master_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/master/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Master Logout
         * @description Déconnexion : révoque la session Master en base et supprime le cookie.
         */
        post: operations["master_logout_api_v1_master_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/master/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Master Me
         * @description Profil du Super Admin connecté.
         */
        get: operations["master_me_api_v1_master_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/master/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Master Refresh
         * @description Renouvelle un jeton de session console Master.
         */
        post: operations["master_refresh_api_v1_master_auth_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/master/societes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Societes
         * @description Liste des sociétés et cabinets provisionnés (accès Super Admin).
         */
        get: operations["list_societes_api_v1_master_societes_get"];
        put?: never;
        /**
         * Create Societe
         * @description Crée une nouvelle structure/société et provisionne son dossier dédié
         *     (base PostgreSQL + schéma Alembic + RBAC + compte admin).
         *
         *     L'auteur de l'opération est journalisé dans `audit_logs_global`.
         */
        post: operations["create_societe_api_v1_master_societes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/master/societes/{societe_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Societe
         * @description Détails d'une société et statut de sa base de données.
         */
        get: operations["get_societe_api_v1_master_societes__societe_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Societe
         * @description Met à jour les informations administratives d'une société.
         */
        patch: operations["update_societe_api_v1_master_societes__societe_id__patch"];
        trace?: never;
    };
    "/api/v1/master/societes/{societe_id}/statut": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Set Societe Statut
         * @description Suspend ou réactive un cabinet.
         *
         *     La suspension bloque les connexions du cabinet sans supprimer aucune donnée :
         *     les dossiers médicaux sont conservés (obligation médico-légale).
         */
        post: operations["set_societe_statut_api_v1_master_societes__societe_id__statut_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/master/statistiques": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Statistiques
         * @description Tableau de bord plateforme : volumes de cabinets et de sessions.
         */
        get: operations["statistiques_api_v1_master_statistiques_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/nomenclature/actes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Nomenclature
         * @description Nomenclature des actes dentaires du cabinet.
         */
        get: operations["list_nomenclature_api_v1_nomenclature_actes_get"];
        put?: never;
        /**
         * Create Acte Nomenclature
         * @description Ajoute un acte à la nomenclature du cabinet (tarifs selon acte et praticien).
         */
        post: operations["create_acte_nomenclature_api_v1_nomenclature_actes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/odontogramme/patients/{patient_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Odontogramme
         * @description Odontogramme complet du patient (32 dents adulte, 20 dents enfant — RG11).
         *
         *     L'odontogramme est généré à la première lecture s'il n'existe pas encore.
         */
        get: operations["get_odontogramme_api_v1_odontogramme_patients__patient_id__get"];
        put?: never;
        /**
         * Creer Odontogramme
         * @description Crée explicitement l'odontogramme d'un patient (choix adulte/enfant, RG11).
         *
         *     Idempotent : si l'odontogramme existe déjà, il est renvoyé tel quel. On ne
         *     réécrit jamais un odontogramme en cours d'utilisation, cela effacerait
         *     l'historique dentaire du patient.
         */
        post: operations["creer_odontogramme_api_v1_odontogramme_patients__patient_id__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/odontogramme/patients/{patient_id}/charting": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Chartings
         * @description Relevés parodontaux du patient, du plus récent au plus ancien.
         */
        get: operations["list_chartings_api_v1_odontogramme_patients__patient_id__charting_get"];
        put?: never;
        /**
         * Create Charting
         * @description Enregistre un relevé parodontal : sondage en 6 points et indices associés.
         */
        post: operations["create_charting_api_v1_odontogramme_patients__patient_id__charting_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/odontogramme/patients/{patient_id}/dent": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Dent
         * @description Change l'état d'une dent et écrit la ligne d'historique (RG10).
         *
         *     L'ancien état, la date, le praticien et la consultation sont conservés.
         */
        patch: operations["update_dent_api_v1_odontogramme_patients__patient_id__dent_patch"];
        trace?: never;
    };
    "/api/v1/odontogramme/patients/{patient_id}/dent/{numero_fdi}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Dent
         * @description État courant d'une dent, avec ses faces.
         */
        get: operations["get_dent_api_v1_odontogramme_patients__patient_id__dent__numero_fdi__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/odontogramme/patients/{patient_id}/dent/{numero_fdi}/faces": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Update Faces
         * @description Met à jour les faces d'une dent (lésion localisée).
         */
        put: operations["update_faces_api_v1_odontogramme_patients__patient_id__dent__numero_fdi__faces_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/odontogramme/patients/{patient_id}/dent/{numero_fdi}/historique": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Historique Dent
         * @description Historique horodaté d'une dent : qui a constaté quoi, et quand (RG10).
         */
        get: operations["get_historique_dent_api_v1_odontogramme_patients__patient_id__dent__numero_fdi__historique_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/odontogramme/patients/{patient_id}/dents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Dents
         * @description Met à jour plusieurs dents en une transaction (détartrage multi-dents).
         *
         *     Soit toutes les dents sont mises à jour, soit aucune : un lot partiellement
         *     appliqué laisserait l'odontogramme incohérent avec la consultation.
         */
        patch: operations["update_dents_api_v1_odontogramme_patients__patient_id__dents_patch"];
        trace?: never;
    };
    "/api/v1/odontogramme/patients/{patient_id}/historique": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Historique Global
         * @description Historique du patient toutes dents confondues, du plus récent au plus ancien.
         */
        get: operations["get_historique_global_api_v1_odontogramme_patients__patient_id__historique_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/odontogramme/referentiel/etats": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Referentiel Etats
         * @description Catalogue des états et des faces, avec leur code couleur.
         *
         *     Le frontend ne doit pas coder en dur ces listes : un état odontologique
         *     ajouté côté backend doit apparaître sans modification du composant SVG.
         */
        get: operations["referentiel_etats_api_v1_odontogramme_referentiel_etats_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/onboarding/etat": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * État de démarrage d'un cabinet (checklist)
         * @description Checklist de démarrage : sept étapes, celles qui sont faites et celles qui
         *     restent, chacune avec une consigne exploitable.
         *
         *     Alimentée par des **compteurs** (`sites`, `praticiens`, `actes`…), jamais par
         *     une lecture nominative : cet endpoint ne doit pas devenir un chemin de
         *     contournement vers les données d'un cabinet.
         *
         *     Le `tenant_id` est demandé en paramètre explicite : cette route est publique
         *     et n'a pas de jeton. Les valeurs qu'elle renvoie sont déjà agrégées et
         *     non sensibles ; elle est à protéger par un contrôle d'accès réseau (VOD /
         *     IP) si l'exposition publique n'est pas souhaitable.
         */
        get: operations["etat_api_v1_onboarding_etat_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/onboarding/inscription": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Créer un cabinet en essai
         * @description Auto-inscription : crée un cabinet **en essai** et son administrateur, par le
         *     service de provisionnement de la console.
         *
         *     Le cabinet est réellement provisionné (base, schéma, rôles, nomenclature,
         *     abonnement) — seule la connexion est verrouillée tant que l'e-mail n'est pas
         *     vérifié. Un e-mail de vérification est envoyé ; en développement, il est
         *     écrit sur la console par l'implémentation « log » de l'envoi de messages.
         *
         *     **Aucune information sur l'existence d'un cabinet ou d'un compte n'est
         *     renvoyée** : un e-mail déjà utilisé, un nom déjà pris et une erreur de
         *     provisionnement produisent le même statut et le même texte.
         */
        post: operations["inscrire_api_v1_onboarding_inscription_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/onboarding/verification-email": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Vérifier l'adresse e-mail
         * @description Valide le jeton reçu par e-mail et déverrouille la connexion du cabinet.
         *
         *     Le jeton est à **usage unique** et stocké haché : une fuite de la base ne
         *     permet ni de vérifier une adresse ni de prendre la main sur un cabinet. Un
         *     jeton déjà utilisé répond exactement comme un jeton inexistant.
         */
        post: operations["verifier_email_api_v1_onboarding_verification_email_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ordonnances": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Ordonnances
         * @description Ordonnances du cabinet, de la plus récente à la plus ancienne.
         */
        get: operations["list_ordonnances_api_v1_ordonnances_get"];
        put?: never;
        /**
         * Creer Ordonnance
         * @description Émet une ordonnance pour une consultation (UC7 du CDC).
         *
         *     Une contre-indication formelle (RG08) fait échouer la requête. Une simple
         *     précaution exige une justification écrite, conservée au dossier.
         */
        post: operations["creer_ordonnance_api_v1_ordonnances_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ordonnances/{prescription_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Ordonnance
         * @description Détail d'une ordonnance.
         */
        get: operations["get_ordonnance_api_v1_ordonnances__prescription_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Ordonnance
         * @description Modifie les notes d'une ordonnance non signée.
         */
        patch: operations["update_ordonnance_api_v1_ordonnances__prescription_id__patch"];
        trace?: never;
    };
    "/api/v1/ordonnances/{prescription_id}/lignes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Ajouter Ligne
         * @description Ajoute une ligne à une ordonnance non signée.
         *
         *     Le contrôle de contre-indication est refait intégralement : l'état du
         *     patient a pu changer depuis l'émission.
         */
        post: operations["ajouter_ligne_api_v1_ordonnances__prescription_id__lignes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ordonnances/{prescription_id}/lignes/{ligne_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Supprimer Ligne
         * @description Supprime une ligne d'une ordonnance non signée, avec trace en audit.
         */
        delete: operations["supprimer_ligne_api_v1_ordonnances__prescription_id__lignes__ligne_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ordonnances/{prescription_id}/signer": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Signer Ordonnance
         * @description Signe l'ordonnance : elle devient non modifiable.
         *
         *     Une ordonnance signée est un acte médical opposable. On ne la dé-signe pas,
         *     on en émet une nouvelle.
         */
        post: operations["signer_ordonnance_api_v1_ordonnances__prescription_id__signer_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ordonnances/controle": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Controler Prescription
         * @description Vérifie si une prescription serait possible, sans rien enregistrer.
         *
         *     Cas d'usage réel : le praticien hésite avant de saisir la posologie. Répondre
         *     tout de suite évite d'avoir à corriger une ordonnance émise.
         */
        post: operations["controler_prescription_api_v1_ordonnances_controle_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ordonnances/medicaments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Medicaments
         * @description Référentiel médicamenteux du cabinet, avec les règles de contre-indication.
         */
        get: operations["list_medicaments_api_v1_ordonnances_medicaments_get"];
        put?: never;
        /**
         * Create Medicament
         * @description Ajoute un médicament au référentiel du cabinet.
         *
         *     Ajouter un médicament ET ses règles de contre-indication est une opération
         *     de données : le moteur de contrôle n'a pas à être modifié.
         */
        post: operations["create_medicament_api_v1_ordonnances_medicaments_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/patients": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Patients
         * @description Recherche multicritère paginée des dossiers patients (UC2).
         */
        get: operations["list_patients_api_v1_patients_get"];
        put?: never;
        /**
         * Create Patient
         * @description Crée un dossier patient avec numéro auto-généré (UC1, Étape 1 du CDC).
         */
        post: operations["create_patient_api_v1_patients_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/patients/{patient_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Patient
         * @description Récupère l'identité administrative d'un dossier patient (UC2).
         */
        get: operations["get_patient_api_v1_patients__patient_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Patient
         * @description Met à jour les informations administratives du dossier (UC3).
         */
        patch: operations["update_patient_api_v1_patients__patient_id__patch"];
        trace?: never;
    };
    "/api/v1/patients/{patient_id}/antecedents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Antecedents
         * @description Liste les antécédents médicaux du patient (antécédents en cours d'abord).
         */
        get: operations["list_antecedents_api_v1_patients__patient_id__antecedents_get"];
        put?: never;
        /**
         * Create Antecedent
         * @description Ajoute un antécédent médical (UC7).
         */
        post: operations["create_antecedent_api_v1_patients__patient_id__antecedents_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/patients/{patient_id}/archiver": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Archive Patient
         * @description Archive un dossier sans le supprimer (UC12).
         */
        post: operations["archive_patient_api_v1_patients__patient_id__archiver_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/patients/{patient_id}/dossier": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Patient Dossier
         * @description Fiche dossier médical complète : identité + état général + antécédents +
         *     alertes cliniques calculées (UC5 « Consulter dossier médical »).
         */
        get: operations["get_patient_dossier_api_v1_patients__patient_id__dossier_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/patients/{patient_id}/etat-general": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Etat General
         * @description Lit l'état général du patient (allergies, grossesse, diabète, HTA).
         */
        get: operations["get_etat_general_api_v1_patients__patient_id__etat_general_get"];
        /**
         * Upsert Etat General
         * @description Crée ou met à jour l'état général du patient (Étape 2 du CDC).
         */
        put: operations["upsert_etat_general_api_v1_patients__patient_id__etat_general_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Patch Etat General
         * @description Mise à jour partielle de l'état général (vérification à chaque consultation, RG02).
         */
        patch: operations["patch_etat_general_api_v1_patients__patient_id__etat_general_patch"];
        trace?: never;
    };
    "/api/v1/patients/{patient_id}/reactiver": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reactivate Patient
         * @description Réactive un dossier archivé.
         */
        post: operations["reactivate_patient_api_v1_patients__patient_id__reactiver_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/patients/antecedents/{antecedent_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Antecedent
         * @description Met à jour un antécédent médical (clôture, précision du traitement).
         */
        patch: operations["update_antecedent_api_v1_patients_antecedents__antecedent_id__patch"];
        trace?: never;
    };
    "/api/v1/platform/acces-support": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister les accès support
         * @description Accès ouverts, du plus récent au plus ancien.
         *
         *     « Actif » = non révoqué et non expiré. C'est la réponse à « qui a accès à
         *     ce cabinet, là, maintenant ? » sans analyser un journal.
         */
        get: operations["lister_acces_support_api_v1_platform_acces_support_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/acces-support/{acces_id}/revocation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Révoquer un accès support
         * @description Coupe un accès. L'effet est immédiat : le jeton reste cryptographiquement
         *     valide jusqu'à son expiration, mais chaque requête faite avec est revalidée
         *     contre la base et refusée.
         *
         *     Révoquer un accès déjà révoqué n'est pas une erreur : l'opérateur doit pouvoir
         *     confirmer l'absence d'accès sans apprendre qu'il avait déjà coupé.
         */
        post: operations["revoquer_acces_support_api_v1_platform_acces_support__acces_id__revocation_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/annonces": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister les annonces
         * @description Toutes les annonces publiées, pour l'écran d'administration.
         */
        get: operations["lister_annonces_api_v1_platform_annonces_get"];
        put?: never;
        /**
         * Publier une annonce
         * @description Publie une bannière affichée par l'application cliente.
         *
         *     Ciblage : `plans_cibles` (codes de formules) et/ou `tenants_cibles` (UUID) ;
         *     les deux vides = tous les cabinets. Une annonce peut viser une formule
         *     entière (« maintenance dimanche 02:00 ») ou un client précis
         *     (« incident de facturation cabinet X »).
         */
        post: operations["publier_annonce_api_v1_platform_annonces_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/annonces/{annonce_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Désactiver une annonce
         * @description Arrête l'affichage de la bannière.
         *
         *     **Désactivation, pas suppression** : une maintenance passée doit rester
         *     consultable (« qui avait été prévenu, et depuis quand ? »), et une annonce
         *     supprimée serait absente du journal alors qu'elle a été affichée.
         */
        delete: operations["desactiver_annonce_api_v1_platform_annonces__annonce_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Consulter le journal d'audit plateforme
         * @description Journal immuable, filtrable.
         *
         *     **Aucune modification ni suppression n'est possible**, y compris par le code
         *     applicatif : la table porte des déclencheurs PostgreSQL qui refusent UPDATE,
         *     DELETE et TRUNCATE. Il n'existe donc volontairement aucun `PATCH` ni `DELETE`
         *     sur cette ressource — l'absence n'est pas un oubli, c'est la garantie.
         */
        get: operations["lister_audit_api_v1_platform_audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/audit/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Exporter le journal d'audit en CSV
         * @description Export CSV (séparateur `;`, tout cité) — ouvrable directement dans un tableur
         *     francophone.
         *
         *     Réservé à l'Auditeur et au Super Admin : l'export permet d'extraire le journal
         *     hors du système, ce qui est un acte de sortie de données, pas une simple
         *     consultation.
         */
        get: operations["exporter_audit_api_v1_platform_audit_export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/auth/2fa": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Deuxième étape : code TOTP
         * @description Valide le code TOTP (ou un code de secours) et ouvre la session.
         *
         *     **Seulement pour un compte déjà enrôlé** : un compte dont la 2FA n'est pas
         *     active reçoit un jeton d'enrôlement au login, jamais un défi ; et si un défi
         *     lui parvient quand même, ce chemin refuse avec le message d'un code
         *     invalide — il n'active jamais le second facteur.
         */
        post: operations["confirmer_2fa_api_v1_platform_auth_2fa_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/auth/2fa/activation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Activer le second facteur et ouvrir la session
         * @description Troisieme etape : le code TOTP confirme l'activation, la session s'ouvre.
         *
         *     C'est la **seule** voie qui emet une session pour un compte dont la 2FA
         *     vient d'etre activee. Le jeton d'enrolement est consomme ici et ne vaut plus
         *     rien : il ne reutilise pas le jeton de session, il disparait.
         *
         *     Le code est verifie **sur le secret en attente** — celui que le compte vient
         *     de scanner — et le secret est ensuite promu secret actif. Un code de secours
         *     ne peut pas activer : il ouvre une session, il n'enrole pas.
         *
         *     Les codes de secours sont renvoyes **une seule fois**. Ni la base ni le
         *     journal ne les conservent en clair.
         */
        post: operations["activer_2fa_api_v1_platform_auth_2fa_activation_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/auth/2fa/codes-secours/regenerer": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Régénérer les codes de secours
         * @description Remplace les codes de secours d'un compte déjà enrôlé par dix nouveaux.
         *
         *     **Seule voie de recours après la perte des codes.** Garde-fous identiques au
         *     login : limitation de débit sur (e-mail, IP), message générique en cas
         *     d'échec, et une session ouverte ne suffit pas — un **TOTP valide sur le
         *     secret actif** et un **motif** sont exigés. Les anciens codes sont invalidés
         *     dans la même transaction, les dix nouveaux ne sont renvoyés qu'ici, et le
         *     journal ne contient que leur nombre.
         */
        post: operations["regenerer_codes_secours_api_v1_platform_auth_2fa_codes_secours_regenerer_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/auth/2fa/preparation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Générer un secret TOTP
         * @description Génère un secret TOTP pour le compte connecté.
         *
         *     Le secret n'est renvoyé QU'ICI. Il est stocké chiffré (Fernet) et ne
         *     redevient jamais lisible : perdre son téléphone impose de passer par une
         *     réinitialisation tracée par un Super Admin.
         */
        get: operations["preparer_2fa_api_v1_platform_auth_2fa_preparation_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Première étape : e-mail + mot de passe
         * @description Vérifie l'e-mail et le mot de passe d'un compte de la console.
         *
         *     **La décision porte sur l'état actif du second facteur** :
         *
         *     - 2FA inactive → un **jeton d'enrôlement**, jamais une session ni un défi.
         *       Le chemin du défi refuse un compte non actif : l'enrôlement ne se fait
         *       que par `/2fa/preparation` puis `/2fa/activation`, la seule voie qui
         *       émette les codes de secours ;
         *     - 2FA active → un **défi** à saisir dans l'application d'authentification.
         *
         *     Dans les deux cas, aucun jeton de session n'est émis à cette étape : la
         *     session ne s'ouvre qu'après le second facteur.
         */
        post: operations["login_api_v1_platform_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Fermer la session
         * @description Révoque la session en base (le jeton de refresh devient inutilisable).
         */
        post: operations["logout_api_v1_platform_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Profil, rôles et permissions effectives
         * @description Profil de l'agent connecté.
         *
         *     `permissions` est la liste effective (`platform.<ressource>.<action>`) : c'est
         *     elle que l'interface doit utiliser pour afficher ou masquer un écran, plutôt
         *     qu'une liste de rôles réinterprétée côté client.
         */
        get: operations["me_api_v1_platform_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/auth/mot-de-passe": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Changer son mot de passe
         * @description Change le mot de passe du compte connecté, après validation de l'ancien.
         */
        post: operations["changer_mot_de_passe_api_v1_platform_auth_mot_de_passe_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Renouveler la session
         * @description Rotation du refresh token.
         *
         *     L'ancien jeton est révoqué au profit d'un nouveau : un refresh token volé
         *     n'est rejouable qu'une fois, et le rôle est RELU en base à chaque appel.
         */
        post: operations["refresh_api_v1_platform_auth_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/invoices": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister les factures de l'éditeur
         * @description Factures paginées, filtrables par cabinet et par statut.
         */
        get: operations["lister_factures_api_v1_platform_invoices_get"];
        put?: never;
        /**
         * Créer une facture manuellement
         * @description Émet une facture pour un cabinet.
         *
         *     **Aucun paiement automatique n'est branché** : le champ `reference_externe`
         *     est le point d'accroche prévu pour un prestataire, qui réconciliera le statut
         *     depuis une notification signée. Le statut ne doit JAMAIS être déduit d'un
         *     retour de navigateur — c'est le client qui déciderait s'il a payé.
         */
        post: operations["creer_facture_api_v1_platform_invoices_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/invoices/{facture_id}/statut": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Changer le statut d'une facture
         * @description Fait évoluer le statut d'une facture (marquage manuel du paiement en attendant le prestataire).
         */
        post: operations["changer_statut_facture_api_v1_platform_invoices__facture_id__statut_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/permissions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister le catalogue des permissions `platform.*`
         * @description Catalogue complet des permissions de la console, pour construire l'écran de matrice.
         */
        get: operations["lister_permissions_api_v1_platform_permissions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/plans": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister les plans
         * @description Catalogue des formules : prix, périodicité, quotas et fonctionnalités.
         */
        get: operations["lister_plans_api_v1_platform_plans_get"];
        put?: never;
        /**
         * Créer un plan
         * @description Crée une formule commerciale.
         *
         *     Les quotas sont stockés en JSONB : ce sont des données de configuration dont
         *     la forme évolue avec le produit, pas une structure figée. Le service
         *     d'application des quotas reste, lui, strictement typé.
         */
        post: operations["creer_plan_api_v1_platform_plans_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/plans/{plan_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Modifier un plan (crée une nouvelle version)
         * @description Modifie un plan : sa `version` est incrémentée et l'instantané précédent est
         *     archivé.
         *
         *     **Les abonnements existants ne sont PAS modifiés.** Chacun conserve la copie
         *     figée de son contrat (`plan_fige`) : augmenter un tarif ne réécrit jamais un
         *     contrat en cours.
         */
        patch: operations["modifier_plan_api_v1_platform_plans__plan_id__patch"];
        trace?: never;
    };
    "/api/v1/platform/plans/{plan_id}/revisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Historique des versions d'un plan
         * @description Toutes les versions archivées du plan : ce que chaque contrat a réellement signé.
         */
        get: operations["historique_plan_api_v1_platform_plans__plan_id__revisions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/roles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister les rôles de la console et leurs permissions
         * @description Catalogue des cinq rôles système et de leurs permissions effectives.
         */
        get: operations["lister_roles_api_v1_platform_roles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/sante": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * État de santé de la plateforme
         * @description Diagnostic RÉELLEMENT exécuté : base plateforme, base master, bases clients,
         *     divergence de schéma, catalogue commercial, jobs.
         *
         *     Le statut global est `ok` ou `degrade` — jamais de 500 justifiant le statut :
         *     une page de santé qui renvoie une erreur ne dit pas *quel* composant est en
         *     panne. Les messages techniques sont tronqués : une trace SQL complète peut
         *     contenir la chaîne de connexion, donc un mot de passe.
         */
        get: operations["sante_api_v1_platform_sante_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/stats/dashboard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Tout ce que le tableau de bord affiche, dans un seul appel
         * @description Agrégats du tableau de bord, calculés **une seule fois** : cabinets par
         *     statut et par plan, nouveaux cabinets des 30 derniers jours, essais
         *     proches de l'expiration, cabinets proches du quota, cabinets inactifs,
         *     résumé de santé, dernières annonces, dernières actions d'audit.
         *
         *     **Aucun contenu clinique** : seuls les compteurs et les noms de cabinets
         *     (déjà exposés ailleurs dans le monde plateforme) apparaissent ici. Un
         *     Dashboard doit être moins disant en données qu'en liens, et ce qu'il dit
         *     doit tenir dans une requête HTTP — pas une rafale de 3, 4, 6.
         *
         *     **Coût.** Tout vite dans des requêtes SQL sur la seule base plateforme,
         *     le temps de réponse est mesuré par le test de garde (visé : < 1 s a
         *     quelques cabinets, < 3 s à 50).
         */
        get: operations["stats_dashboard_api_v1_platform_stats_dashboard_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/stats/globales": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Vue d'ensemble de la base installée
         * @description Répartition par statut et par formule, croissance, cabinets inactifs, cabinets
         *     proches de leur quota.
         *
         *     **Aucun contenu clinique** : uniquement des compteurs agrégés, lus dans
         *     `stats_tenant` (une ligne par cabinet et par jour). Aucun accès aux bases
         *     clients n'a lieu ici — le coût est borné par le nombre de cabinets.
         */
        get: operations["stats_globales_api_v1_platform_stats_globales_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/stats/tenants/{tenant_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Statistiques d'un cabinet
         * @description Compteurs du cabinet et série temporelle.
         *
         *     Un cabinet sans relevé est renvoyé avec des compteurs à zéro et
         *     `releve=null` — pas d'erreur : un cabinet provisionné ce matin n'a pas encore
         *     eu son relevé nocturne, et « pas encore de données » n'est pas une panne.
         */
        get: operations["stats_tenant_api_v1_platform_stats_tenants__tenant_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/subscriptions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister les abonnements
         * @description Tous les abonnements, avec le plan FIGÉ au moment de la souscription.
         */
        get: operations["lister_abonnements_api_v1_platform_subscriptions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/subscriptions/{abonnement_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Détail d'un abonnement */
        get: operations["detail_abonnement_api_v1_platform_subscriptions__abonnement_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/subscriptions/{abonnement_id}/plan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Changer le plan d'un abonnement
         * @description Change la formule d'un cabinet. Les nouveaux quotas s'appliquent
         *     immédiatement, et le passage est journalisé avec l'avant et l'après.
         */
        post: operations["changer_plan_api_v1_platform_subscriptions__abonnement_id__plan_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/subscriptions/tenant/{tenant_id}/historique": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Historique des changements d'un abonnement
         * @description Chronologie des souscriptions et changements de plan, avec le motif de chacun.
         */
        get: operations["historique_abonnement_api_v1_platform_subscriptions_tenant__tenant_id__historique_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/tenants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Registre paginé des cabinets
         * @description Registre des cabinets : recherche, filtres statut/plan/pays/période, pagination.
         *
         *     Le filtre `plan` parcourt les abonnements du tenant : le plan vit dans la
         *     base plateforme, pas dans `societes`, où il n'a pas sa place.
         */
        get: operations["lister_tenants_api_v1_platform_tenants_get"];
        put?: never;
        /**
         * Créer et provisionner un cabinet
         * @description Provisionne un cabinet de bout en bout : base dédiée, schéma, semis depuis les
         *     gabarits, dossier plateforme, abonnement, index de routage, invitation de
         *     l'administrateur.
         *
         *     **Tout ou rien.** En cas d'échec, chaque étape déjà effectuée est annulée
         *     (base supprimée, société supprimée) : il ne reste jamais de tenant à moitié
         *     créé, contrairement à l'outillage `/master/societes` d'origine qui laissait
         *     un état `PROVISIONING` orphelin.
         */
        post: operations["creer_tenant_api_v1_platform_tenants_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/tenants/{tenant_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Détail d'un cabinet
         * @description Fiche complète : identité, statut, préférences, abonnement et transitions possibles.
         */
        get: operations["detail_tenant_api_v1_platform_tenants__tenant_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Modifier les informations d'un cabinet
         * @description Met à jour l'identité (nom, contacts) ou les préférences (pays, langue, fuseau, devise).
         */
        patch: operations["modifier_tenant_api_v1_platform_tenants__tenant_id__patch"];
        trace?: never;
    };
    "/api/v1/platform/tenants/{tenant_id}/acces-support": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Ouvrir un accès support encadré
         * @description Émet un jeton d'accès à l'espace du cabinet, valable 30 minutes.
         *
         *     **Lecture seule par défaut.** Passer `lecture_seule=false` exige la
         *     permission `platform.support.grant_elevated` ET un motif d'au moins 40
         *     caractères justifiant pourquoi la lecture ne suffit pas — et le drapeau
         *     `PLATFORM_SUPPORT_ELEVATION_ABILITEE` doit être activé sur l'installation.
         *
         *     Le jeton returned porte `impersonated_by`, `support_reason`, `support_ticket`
         *     et `scope=support` : chaque action faite avec est attribuable à un agent et à
         *     un motif, sans que l'agent ait jamais eu accès au mot de passe du cabinet.
         *
         *     L'ouverture est écrite dans le journal immuable de la plateforme **et** dans
         *     le journal d'audit du cabinet.
         */
        post: operations["ouvrir_acces_support_api_v1_platform_tenants__tenant_id__acces_support_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/tenants/{tenant_id}/archivage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Archiver / désarchiver logiquement
         * @description Retire le cabinet du registre actif sans rien supprimer.
         *
         *     L'archivage est RÉVERSIBLE ; c'est ce qui en fait l'outil du quotidien. La
         *     suppression définitive, elle, est irréversible et exige trois verrous.
         */
        post: operations["archiver_tenant_api_v1_platform_tenants__tenant_id__archivage_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/tenants/{tenant_id}/historique": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Historique horodaté des transitions
         * @description Journal des changements de statut : horodatage, avant, après, motif, auteur, IP.
         *
         *     Alimente l'écran « pourquoi ce cabinet est-il suspendu ? », question à laquelle
         *     la console doit pouvoir répondre sans fouiller dans les logs.
         */
        get: operations["historique_tenant_api_v1_platform_tenants__tenant_id__historique_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/tenants/{tenant_id}/quotas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Consommation et limites d'un cabinet
         * @description Quota par quota : consommation, limite et taux d'usage.
         *
         *     La consommation vient du dernier relevé d'agrégats journalier, pas d'une
         *     requête dans la base du cabinet : cet écran reste donc instantané même avec
         *     plusieurs centaines de clients.
         */
        get: operations["quotas_tenant_api_v1_platform_tenants__tenant_id__quotas_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/tenants/{tenant_id}/quotas/simulation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Simuler l'effet d'un quota
         * @description « Avec 6 utilisateurs, le plan ESSENTIEL autorise-t-il encore ? »
         *
         *     Utile avant une intervention : l'opérateur voit le refus avant de le
         *     provoquer chez le client. Ne lève jamais — une simulation qui échoue
         *     n'apprend rien.
         */
        get: operations["simuler_quota_api_v1_platform_tenants__tenant_id__quotas_simulation_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/tenants/{tenant_id}/reactivation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Réactiver un cabinet
         * @description Rétablit l'accès d'un cabinet suspendu, ou confirme le passage en production d'un essai.
         */
        post: operations["reactiver_tenant_api_v1_platform_tenants__tenant_id__reactivation_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/tenants/{tenant_id}/resiliation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Résilier un cabinet
         * @description Fait passer le cabinet en `RESILIE` — état terminal : aucune transition sortante.
         *
         *     Aucune donnée n'est supprimée à ce stade. La suppression définitive est une
         *     opération distincte, avec ses propres verrous (double confirmation, droit
         *     spécifique, rétention).
         */
        post: operations["resilier_tenant_api_v1_platform_tenants__tenant_id__resiliation_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/tenants/{tenant_id}/suspension": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Suspendre un cabinet
         * @description Suspend l'accès du cabinet.
         *
         *     Effets immédiats : le login du cabinet est refusé, l'API du cabinet renvoie
         *     `TENANT_NOT_FOUND`, et **toutes les sessions ouvertes sont révoquées** — sans
         *     cela un utilisateur resterait connecté jusqu'à l'expiration de son jeton, sur
         *     un compte qu'on vient de suspendre.
         *
         *     Aucune donnée n'est supprimée : la suspension est réversible.
         */
        post: operations["suspendre_tenant_api_v1_platform_tenants__tenant_id__suspension_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/tenants/transitions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Matrice des transitions de statut
         * @description Table des transitions autorisées.
         *
         *     Exposée pour que le frontend puisse griser un bouton plutôt que d'attendre un
         *     422 : la règle est une donnée, pas une/devinette côté client.
         */
        get: operations["matrice_transitions_api_v1_platform_tenants_transitions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister les comptes de la console
         * @description Registre paginé des comptes de la console, filtrable par recherche et statut.
         */
        get: operations["lister_utilisateurs_api_v1_platform_users_get"];
        put?: never;
        /**
         * Créer un compte de la console
         * @description Crée un compte et renvoie, s'il est demandé, le PREPARATIF d'activation 2FA.
         *
         *     Le secret TOTP n'est renvoyé qu'ici : ni la base (chiffré) ni le journal ne
         *     le conservent en clair.
         */
        post: operations["creer_utilisateur_api_v1_platform_users_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/users/{utilisateur_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Détail d'un compte
         * @description Fiche d'un compte : identité, rôles, permissions effectives et sessions ouvertes.
         */
        get: operations["detail_utilisateur_api_v1_platform_users__utilisateur_id__get"];
        put?: never;
        post?: never;
        /**
         * Supprimer DÉFINITIVEMENT un compte
         * @description Suppression définitive, protégée par TROIS verrous :
         *
         *     1. la permission `platform.users.delete` (distincte de `deactivate`) ;
         *     2. une confirmation explicite — le corps doit contenir `SUPPRIMER` ;
         *     3. l'interdiction de supprimer le dernier Super Admin actif.
         *
         *     Le journal d'audit, lui, survit à la suppression du compte : effacer un agent
         *     ne doit pas effacer ce qu'il a fait.
         */
        delete: operations["supprimer_utilisateur_api_v1_platform_users__utilisateur_id__delete"];
        options?: never;
        head?: never;
        /**
         * Modifier un compte
         * @description Met à jour l'identité ou les rôles d'un compte.
         *
         *     Un changement de rôles **révoque les sessions ouvertes** : sans cela, un
         *     agent déclassé conserverait ses droits jusqu'à l'expiration de son jeton.
         */
        patch: operations["modifier_utilisateur_api_v1_platform_users__utilisateur_id__patch"];
        trace?: never;
    };
    "/api/v1/platform/users/{utilisateur_id}/desactivation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Désactiver un compte
         * @description Désactive un compte et coupe toutes ses sessions.
         *
         *     **Garde-fou** : refusé si le compte porte le rôle Super Admin et qu'aucun
         *     autre Super Admin actif ne subsiste.
         */
        post: operations["desactiver_utilisateur_api_v1_platform_users__utilisateur_id__desactivation_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/users/{utilisateur_id}/reactivation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Réactiver un compte
         * @description Réactive un compte désactivé. Le second facteur reste obligatoire.
         */
        post: operations["reactiver_utilisateur_api_v1_platform_users__utilisateur_id__reactivation_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/users/{utilisateur_id}/reinitialisation-acces": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Réinitialiser l'accès d'un compte
         * @description Remet à zéro l'authentification : nouveau secret 2FA, sessions révoquées.
         *
         *     Action de support classique (téléphone perdu). Toujours tracée, toujours avec
         *     motif obligatoire.
         */
        post: operations["reinitialiser_acces_api_v1_platform_users__utilisateur_id__reinitialisation_acces_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/praticiens": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Praticiens
         * @description Praticiens du cabinet, triés par nom de famille.
         *
         *     `cabinet_id` ne renvoie que ceux rattachés **activement** à ce site : c'est
         *     la liste que l'agenda doit proposer.
         */
        get: operations["lister_praticiens_api_v1_praticiens_get"];
        put?: never;
        /**
         * Creer Praticien
         * @description Rattache un compte existant au métier de praticien.
         *
         *     Le compte doit déjà exister : un praticien sans compte ne pourrait rien
         *     signer, or c'est la signature qui rend un acte opposable.
         */
        post: operations["creer_praticien_api_v1_praticiens_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/praticiens/{praticien_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Praticien */
        get: operations["get_praticien_api_v1_praticiens__praticien_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Praticien
         * @description Modifie la fiche professionnelle (titre, spécialité, numéro d'ordre, bio).
         */
        patch: operations["update_praticien_api_v1_praticiens__praticien_id__patch"];
        trace?: never;
    };
    "/api/v1/praticiens/{praticien_id}/creneaux": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Creneaux
         * @description Créneaux qu'on peut proposer au patient pour une date donnée.
         *
         *     C'est le calcul dont le module Agenda (D2B) aura besoin pour placer un
         *     rendez-vous. Il est exposé dès maintenant parce que le secrétariat en a
         *     besoin au téléphone, pour répondre à un patient qui demande « quand puis-je
         *     venir ? ».
         *
         *     Les plages `BLOCKING` sont déjà retirées du résultat. **Les rendez-vous déjà
         *     pris ne le sont pas** : à ce stade, aucun autre module ne les connaît. C'est
         *     D2B qui effectuera ce retranchement.
         */
        get: operations["lister_creneaux_api_v1_praticiens__praticien_id__creneaux_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/praticiens/{praticien_id}/disponibilites": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Disponibilites
         * @description Plages horaires déclarées par un praticien, récurrentes et exceptions.
         */
        get: operations["lister_disponibilites_api_v1_praticiens__praticien_id__disponibilites_get"];
        put?: never;
        /**
         * Creer Disponibilite
         * @description Déclare une plage de travail.
         *
         *     `type=BLOCKING` déclare une indisponibilité (congé, formation) qui RETIRE
         *     des créneaux ; `CONSULTATION` en crée. Les deux ne se confondent pas : un
         *     créneau réservé aux urgences n'est pas une absence.
         */
        post: operations["creer_disponibilite_api_v1_praticiens__praticien_id__disponibilites_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rbac/permissions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Permissions
         * @description Catalogue des permissions disponibles, pour construire l'écran d'attribution.
         */
        get: operations["list_permissions_api_v1_rbac_permissions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rbac/roles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Roles
         * @description Liste les rôles du cabinet avec leurs permissions effectives.
         *
         *     Route de diagnostic la plus utile du produit pour le support : « le compte
         *     du praticien a le bon rôle ? » se répond ici, sans toucher à une donnée
         *     patient. Elle accepte donc un jeton support (lecture seule).
         */
        get: operations["list_roles_api_v1_rbac_roles_get"];
        put?: never;
        /**
         * Create Role
         * @description Crée un rôle métier.
         *
         *     Le rôle naît SANS permission : l'administrateur accorde ensuite les droits
         *     une par une. Créer un rôle déjà armchairé de ADMIN_CABINET serait une
         *     escalade de privilèges en une seule requête.
         */
        post: operations["create_role_api_v1_rbac_roles_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rbac/roles/{role_id}/permissions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Grant Permission
         * @description Accorde une permission à un rôle (format MODULE:ACTION).
         */
        post: operations["grant_permission_api_v1_rbac_roles__role_id__permissions_post"];
        /**
         * Revoke Permission
         * @description Retire une permission d'un rôle.
         *
         *     L'opération est refusée sur ADMIN_CABINET : c'est le rôle de secours qui
         *     garantit qu'un cabinet ne peut pas se verrouiller hors de sa base.
         */
        delete: operations["revoke_permission_api_v1_rbac_roles__role_id__permissions_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/referentiel/disponibilites": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Referentiel Disponibilites
         * @description Jours de la semaine, types de plage et durée de créneau.
         *
         *     Publier la convention « 0 = lundi » évite que le frontend la redécouvre et
         *     diverge du backend — c'est le genre d'écart qui ne se voit qu'en production,
         *     le lundi matin.
         */
        get: operations["get_referentiel_disponibilites_api_v1_referentiel_disponibilites_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rendez-vous": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Rendez Vous
         * @description Rendez-vous du cabinet, du plus ancien au plus récent.
         *
         *     `du` / `au` filtrent sur l'INTERVALLE (et non sur un instant) : un
         *     rendez-vous de 14h30 à 15h est bien renvoyé pour `du=14h00`.
         */
        get: operations["lister_rendez_vous_api_v1_rendez_vous_get"];
        put?: never;
        /**
         * Creer Rendez Vous
         * @description Prend un rendez-vous (UC9).
         *
         *     **422 `CRENEAU_DEJA_OCCUPE`** si le créneau est pris. Le champ
         *     `error.details.conflits` nomme l'obstacle (avec qui, pour quel motif) : le
         *     frontend doit le montrer, et proposer d'autres horaires.
         *
         *     Un créneau hors disponibilités déclarées est **accepté** ; la réponse porte
         *     alors `hors_disponibilites: true` pour que l'interface le signale.
         */
        post: operations["creer_rendez_vous_api_v1_rendez_vous_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rendez-vous/{rendez_vous_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Rendez Vous */
        get: operations["get_rendez_vous_api_v1_rendez_vous__rendez_vous_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Rendez Vous
         * @description Corrige le motif, les notes, ou change le fauteuil tant que rien n'a commencé.
         */
        patch: operations["update_rendez_vous_api_v1_rendez_vous__rendez_vous_id__patch"];
        trace?: never;
    };
    "/api/v1/rendez-vous/{rendez_vous_id}/consultation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Demarrer Consultation
         * @description Ouvre la consultation quand le patient passe en salle.
         *
         *     C'est le SEUL endroit où `consultations.rendez_vous_id` et
         *     `consultations.fauteuil_id` sont posés : le fauteuil vient de l'occupation du
         *     rendez-vous, donc l'agenda et le dossier médical ne peuvent pas diverger sur
         *     le lieu du soin.
         *
         *     Le rendez-vous devient `EN_CONSULTATION` et sera `TERMINEE` par le module
         *     Consultations à la clôture du soin.
         */
        post: operations["demarrer_consultation_api_v1_rendez_vous__rendez_vous_id__consultation_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rendez-vous/{rendez_vous_id}/planifier": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Planifier Rendez Vous
         * @description Reporte un rendez-vous à un autre créneau.
         *
         *     Opération atomique : l'ancien créneau est libéré et le nouveau réservé. Le
         *     fauteuil se déplace avec, sauf indication contraire.
         */
        post: operations["planifier_rendez_vous_api_v1_rendez_vous__rendez_vous_id__planifier_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rendez-vous/{rendez_vous_id}/statut": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Changer Statut
         * @description Fait avancer le rendez-vous : confirmer, appeler en salle d'attente, passer
         *     en consultation, terminer, annuler, marquer absent.
         *
         *     **422 `TRANSITION_INTERDITE`** si le chemin n'existe pas. `error.details`
         *     indique les transitions possibles.
         *
         *     Un rendez-vous annulé ou manqué **libère son créneau automatiquement** : la
         *     contrainte d'exclusion ignore ces statuts.
         */
        post: operations["changer_statut_api_v1_rendez_vous__rendez_vous_id__statut_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rendez-vous/agenda": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Agenda
         * @description Journée d'agenda.
         *
         *     Renvoie les rendez-vous ET les indisponibilités de fauteuil dans la même
         *     réponse : un planning qui ignore un fauteuil au compresseur en panne
         *     propose un créneau qu'on ne pourra pas honorer.
         */
        get: operations["get_agenda_api_v1_rendez_vous_agenda_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rendez-vous/creneaux-libres": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Creneaux Libres
         * @description Créneaux réellement disponibles : heures déclarées **moins** ce qui est déjà
         *     pris (rendez-vous du praticien, fauteuils immobilisés).
         *
         *     ⚠️ Complète `GET /praticiens/{id}/creneaux` du module D2A, qui ne connaît que
         *     les heures déclarées. C'est cette route qu'un écran de prise de rendez-vous
         *     doit appeler.
         */
        get: operations["lister_creneaux_libres_api_v1_rendez_vous_creneaux_libres_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rendez-vous/fauteuils/blocage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Bloquer Fauteuil
         * @description Immobilise un fauteuil sans rendez-vous (panne, entretien).
         *
         *     ⚠️ `422 CRENEAU_DEJA_OCCUPE` si un rendez-vous occupe déjà le fauteuil sur
         *     cette plage : il faut d'abord déplacer ou annuler ce rendez-vous, pas
         *     supprimer son occupation.
         */
        post: operations["bloquer_fauteuil_api_v1_rendez_vous_fauteuils_blocage_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rendez-vous/fauteuils/blocage/{creneau_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Debloquer Fauteuil
         * @description Remet un fauteuil en service.
         *
         *     **422 `OCCUPATION_LIEE_A_UN_RDV`** si le créneau appartient à un rendez-vous :
         *     c'est le rendez-vous qu'il faut annuler ou déplacer, sinon le fauteuil
         *     resterait réservé sans que personne ne le sache.
         */
        delete: operations["debloquer_fauteuil_api_v1_rendez_vous_fauteuils_blocage__creneau_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rendez-vous/referentiel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Referentiel
         * @description Cycle de vie, motifs de blocage et durées usuelles.
         *
         *     Publier le graphe des transitions évite que le frontend invente un bouton
         *     « Terminer » sur un rendez-vous planifié, et montre au secrétariat
         *     uniquement les actions réellement possibles.
         */
        get: operations["get_referentiel_api_v1_rendez_vous_referentiel_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/salles/{salle_id}/fauteuils": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Creer Fauteuil
         * @description Ajoute un fauteuil dans une salle.
         */
        post: operations["creer_fauteuil_api_v1_salles__salle_id__fauteuils_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stock/alertes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Alertes
         * @description Alertes de stock minimum et de péremption.
         *
         *     Elles sont calculées à la demande et non stockées : une alerte enregistrée
         *     vieillit et finit par annoncer un problème qui n'existe plus.
         */
        get: operations["lister_alertes_api_v1_stock_alertes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stock/articles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Lister Articles */
        get: operations["lister_articles_api_v1_stock_articles_get"];
        put?: never;
        /**
         * Creer Article
         * @description Crée un article de stock.
         *
         *     La quantité initiale est enregistrée comme un mouvement d'entrée, pas
         *     écrite directement : le stock d'un article créé doit pouvoir s'expliquer
         *     comme n'importe quelle autre entrée.
         */
        post: operations["creer_article_api_v1_stock_articles_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stock/articles/{article_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Modifier Article */
        patch: operations["modifier_article_api_v1_stock_articles__article_id__patch"];
        trace?: never;
    };
    "/api/v1/stock/commandes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Commandes
         * @description Commandes fournisseur, paginées.
         *
         *     **Correction d'un silence** : la route plafonnait à 50 lignes sans `page` ni
         *     `offset`. Au-delà, les commandes existantes disparaissaient de l'écran sans
         *     aucun message — l'utilisateur croyait qu'il n'y avait rien d'autre. Une liste
         *     tronquée sans le dire est la même famille de défaut que le « aucune donnée »
         *     affiché comme un zéro.
         */
        get: operations["lister_commandes_api_v1_stock_commandes_get"];
        put?: never;
        /**
         * Creer Commande
         * @description Crée un bon de commande en brouillon.
         *
         *     Émettre une commande n'ajoute rien au stock : la matière n'arrive qu'à la
         *     réception. Sans cette séparation, le stock annoncerait des produits que le
         *     cabinet n'a pas.
         */
        post: operations["creer_commande_api_v1_stock_commandes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stock/commandes/{commande_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Changer Statut Commande
         * @description Fait avancer la commande dans son cycle de vie.
         *
         *     Les transitions autorisées sont explicites : une commande reçue ne se
         *     rouvre pas, une commande envoyée ne revient pas en brouillon.
         */
        patch: operations["changer_statut_commande_api_v1_stock_commandes__commande_id__patch"];
        trace?: never;
    };
    "/api/v1/stock/fournisseurs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Fournisseurs
         * @description Fournisseurs du cabinet, paginés.
         *
         *     La liste était renvoyée en entier. Un cabinet qui travaille avec un
         *     grossiste, un laboratoire et un fournisseur d'urgence en a quelques
         *     dizaines : la liste entière reste gérable, mais la réponse ne doit pas
         *     grossir indéfiniment alors qu'une borne est disponible.
         */
        get: operations["lister_fournisseurs_api_v1_stock_fournisseurs_get"];
        put?: never;
        /** Creer Fournisseur */
        post: operations["creer_fournisseur_api_v1_stock_fournisseurs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stock/fournisseurs/{fournisseur_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Modifier Fournisseur */
        patch: operations["modifier_fournisseur_api_v1_stock_fournisseurs__fournisseur_id__patch"];
        trace?: never;
    };
    "/api/v1/stock/mouvements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Mouvements
         * @description Historique des mouvements, du plus récent au plus ancien.
         */
        get: operations["lister_mouvements_api_v1_stock_mouvements_get"];
        put?: never;
        /**
         * Enregistrer Mouvement
         * @description Enregistre une entrée ou une sortie de matière.
         *
         *     Le stock n'est jamais écrit directement : tout passe par un mouvement, ce qui
         *     rend chaque écart d'inventaire explicable ligne par ligne.
         */
        post: operations["enregistrer_mouvement_api_v1_stock_mouvements_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stock/receptions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Enregistrer Reception
         * @description Enregistre une réception : le stock est crédité immédiatement.
         *
         *     Le crédit est automatique et tracable, sans validation à deux mains. Dans un
         *     cabinet d'une ou deux personnes, la double validation empêche la réception —
         *     donc le stock devient faux, et un stock faux est cru. Qui, quand et depuis
         *     quelle commande : la trace est complète, et c'est elle qui fait la sécurité.
         */
        post: operations["enregistrer_reception_api_v1_stock_receptions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/utilisateurs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Utilisateurs
         * @description Comptes du cabinet.
         *
         *     Le nom du site est résolu en une requête pour l'ensemble de la page : le
         *     frontend affiche «/site» dans la liste, et le faire ligne par ligne
         *     reviendrait à doubler le nombre d'allers-retours.
         */
        get: operations["lister_utilisateurs_api_v1_utilisateurs_get"];
        put?: never;
        /**
         * Creer Utilisateur
         * @description Crée un compte **et le rend connectable**.
         *
         *     L'écriture de la ligne de routage en base master est indissociable de la
         *     création : un compte sans elle existe mais ne peut jamais se connecter. Si
         *     elle échoue, la création échoue — on ne laisse pas d'adresse brûlée en base.
         */
        post: operations["creer_utilisateur_api_v1_utilisateurs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/utilisateurs/{utilisateur_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Obtenir Utilisateur
         * @description Fiche d'un compte, avec ses sessions ouvertes.
         */
        get: operations["obtenir_utilisateur_api_v1_utilisateurs__utilisateur_id__get"];
        put?: never;
        post?: never;
        /**
         * Desactiver Utilisateur
         * @description **Désactive** un compte — ne le supprime jamais.
         *
         *     Une consultation, un acte, une clôture de caisse le référencent : supprimer
         *     la ligne effacerait l'auteur d'un acte médical. Désactiver ferme l'accès,
         *     révoque les sessions, et conserve la preuve.
         */
        delete: operations["desactiver_utilisateur_api_v1_utilisateurs__utilisateur_id__delete"];
        options?: never;
        head?: never;
        /**
         * Modifier Utilisateur
         * @description Modifie profil, rôle, site ou état.
         *
         *     Trois refus sont non négociables : se désactiver soi-même, retirer le rôle
         *     d'administration au dernier administrateur, et désactiver le dernier
         *     administrateur. Un cabinet qui se verrouille n'a personne pour le rouvrir.
         */
        patch: operations["modifier_utilisateur_api_v1_utilisateurs__utilisateur_id__patch"];
        trace?: never;
    };
    "/api/v1/utilisateurs/{utilisateur_id}/mot-de-passe": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reinitialiser Mot De Passe
         * @description Réinitialise le mot de passe et rend un mot de passe temporaire, une fois.
         *
         *     Les sessions ouvertes sont révoquées : quelqu'un pouvait être connecté avec
         *     l'ancien mot de passe, et le changer ne doit pas laisser cette session
         *     valide.
         */
        post: operations["reinitialiser_mot_de_passe_api_v1_utilisateurs__utilisateur_id__mot_de_passe_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/utilisateurs/{utilisateur_id}/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lister Sessions
         * @description Sessions ouvertes d'un compte — pour voir qui est connecté, et terminer.
         */
        get: operations["lister_sessions_api_v1_utilisateurs__utilisateur_id__sessions_get"];
        put?: never;
        post?: never;
        /**
         * Revoquer Sessions
         * @description Termine toutes les sessions ouvertes d'un compte.
         */
        delete: operations["revoquer_sessions_api_v1_utilisateurs__utilisateur_id__sessions_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health Check
         * @description Vérification de l'état de fonctionnement du serveur.
         */
        get: operations["health_check_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AbonnementResponse */
        AbonnementResponse: {
            /**
             * Date Debut
             * Format: date-time
             */
            date_debut: string;
            /** Date Debut Essai */
            date_debut_essai?: string | null;
            /** Date Fin */
            date_fin?: string | null;
            /** Date Fin Essai */
            date_fin_essai?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Numero */
            numero: string;
            /** Plan */
            plan?: string | null;
            /** Plan Fige */
            plan_fige: {
                [key: string]: unknown;
            };
            /** Plan Id */
            plan_id?: string | null;
            /** Plan Nom */
            plan_nom?: string | null;
            /** Renouvellement Auto */
            renouvellement_auto: boolean;
            /** Statut */
            statut: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
        };
        /**
         * AccesSupportCreate
         * @description Demande d'accès au dossier d'un cabinet par un agent de la plateforme.
         */
        AccesSupportCreate: {
            /**
             * Lecture Seule
             * @description False demande une élévation : permission `platform.support.grant_elevated` + motif renforcé + PLATFORM_SUPPORT_ELEVATION_ABILITEE=true.
             * @default true
             */
            lecture_seule: boolean;
            /**
             * Motif
             * @description Obligatoire. Raison de l intervention, telle qu'elle sera lue dans le journal du cabinet. En écriture, 40 caractères minimum.
             * @example Ticket SUP-4821 — le praticien ne peut plus créer de rendez-vous
             */
            motif: string;
            /**
             * Ticket
             * @description Référence du ticket, si elle existe
             */
            ticket?: string | null;
        };
        /** AccesSupportResponse */
        AccesSupportResponse: {
            /**
             * Administrateur Notifie
             * @default false
             */
            administrateur_notifie: boolean;
            /** Agent Email */
            agent_email: string;
            /**
             * Cree Le
             * Format: date-time
             */
            cree_le: string;
            /**
             * Expire Le
             * Format: date-time
             */
            expire_le: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Lecture Seule */
            lecture_seule: boolean;
            /** Motif */
            motif: string;
            /** Motif Revoque */
            motif_revoque?: string | null;
            /** Revoque At */
            revoque_at?: string | null;
            /** Statut */
            statut: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /** Ticket */
            ticket?: string | null;
        };
        /**
         * ActeNomenclatureCreate
         * @description Création d'un acte de nomenclature (tarification du cabinet).
         */
        ActeNomenclatureCreate: {
            /**
             * Categorie
             * @description SOINS, PROTHESE, CHIRURGIE, ORTHO...
             */
            categorie: string;
            /**
             * Code
             * @description Code de l'acte (DT01, EXT01...)
             */
            code: string;
            /**
             * Duree Estimee Min
             * @default 30
             */
            duree_estimee_min: number;
            /** Libelle */
            libelle: string;
            /**
             * Tarif Base
             * @description Tarif de référence en FCFA
             */
            tarif_base: number | string;
            /**
             * Unitaire
             * @description Soin portant sur une dent : le numéro FDI sera alors obligatoire.
             * @default false
             */
            unitaire: boolean;
        };
        /**
         * ActeRealiseCreate
         * @description Saisie d'un acte réalisé. Le tarif est résolu côté service (nomenclature + praticien).
         */
        ActeRealiseCreate: {
            /**
             * Acte Id
             * Format: uuid
             * @description Acte de la nomenclature
             */
            acte_id: string;
            /**
             * Dent Numero
             * @description Numéro FDI si l'acte porte sur une dent
             */
            dent_numero?: number | null;
            /**
             * Description
             * @description Libellé retenu pour la facture
             */
            description?: string | null;
            /**
             * Face
             * @description MESIAL | DISTAL | VESTIBULAIRE | LINGUAL_PALATIN | OCCLUSAL_INCISAL
             */
            face?: string | null;
            /** Notes */
            notes?: string | null;
            /**
             * Quantite
             * @default 1
             */
            quantite: number;
            /**
             * Tarif Applique
             * @description Forfait non prévu (accord commercial). Sinon, tarif de la nomenclature.
             */
            tarif_applique?: number | string | null;
        };
        /** ActeRealiseResponse */
        ActeRealiseResponse: {
            /**
             * Acte Id
             * Format: uuid
             */
            acte_id: string;
            /**
             * Code Acte
             * @description Code de la nomenclature (dénormalisé pour l'affichage)
             */
            code_acte: string;
            /**
             * Consultation Id
             * Format: uuid
             */
            consultation_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Dent Numero */
            dent_numero?: number | null;
            /** Description */
            description?: string | null;
            /** Face */
            face?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Libelle Acte */
            libelle_acte: string;
            /**
             * Montant
             * @description tarif_applique × quantite (RG07 : calculé, jamais saisi)
             */
            montant: string;
            /** Notes */
            notes?: string | null;
            /** Quantite */
            quantite: number;
            /** Tarif Applique */
            tarif_applique: string;
        };
        /** ActeRealiseUpdate */
        ActeRealiseUpdate: {
            /** Dent Numero */
            dent_numero?: number | null;
            /** Description */
            description?: string | null;
            /** Face */
            face?: string | null;
            /** Notes */
            notes?: string | null;
            /** Quantite */
            quantite?: number | null;
            /** Tarif Applique */
            tarif_applique?: number | string | null;
        };
        /** Activation2FAResponse */
        Activation2FAResponse: {
            /** Instruction */
            instruction: string;
            /**
             * Secret
             * @description Secret TOTP base32 — affiché UNE seule fois
             */
            secret: string;
            /**
             * Uri
             * @description URI otpauth:// à encoder en QR Code
             */
            uri: string;
        };
        /** Activer2FARequest */
        Activer2FARequest: {
            /** Code */
            code: string;
        };
        /**
         * AgendaResponse
         * @description Journée d'agenda, prête à afficher.
         *
         *     Renvoie les rendez-vous ET les indisponibilités de fauteuil dans la même
         *     liste : un écran de planning qui n'affiche pas un fauteuil en réparation
         *     propose un créneau qu'on ne pourra pas honorer.
         */
        AgendaResponse: {
            /** Cabinet Id */
            cabinet_id?: string | null;
            /**
             * Date
             * Format: date-time
             */
            date: string;
            /**
             * Indisponibilites
             * @default []
             */
            indisponibilites: {
                [key: string]: unknown;
            }[];
            /**
             * Nb Annules
             * @default 0
             */
            nb_annules: number;
            /**
             * Nb Rendez Vous
             * @default 0
             */
            nb_rendez_vous: number;
            /**
             * Rendez Vous
             * @default []
             */
            rendez_vous: components["schemas"]["RendezVousResponse"][];
        };
        /** AlerteConsultation */
        AlerteConsultation: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Niveau */
            niveau: string;
        };
        /**
         * AlerteMedicale
         * @description Alerte clinique calculée à la volée (RG03, RG04).
         *
         *     Le seuil de gravité est fixé par la clinique, pas déduit du modèle :
         *     toute grossesse est un signal, toute allergie grave est un signal.
         */
        AlerteMedicale: {
            /**
             * Code
             * @description ALLERGIE | GROSSESSE | ALLAITEMENT | DIABETE | HTA | ANTECEDENT_CARDIAQUE | ANTECEDENT_ACTIF
             */
            code: string;
            /** Message */
            message: string;
            /**
             * Niveau
             * @description INFO | MODERE | GRAVE
             */
            niveau: string;
            /**
             * Source
             * @description ETAT_GENERAL ou ANTECEDENT
             */
            source: string;
        };
        /**
         * AlertePrescription
         * @description Alerte de contre-indication ou d'interaction.
         */
        AlertePrescription: {
            /** Code */
            code: string;
            /**
             * Condition
             * @description Condition clinique en cause, vide si interaction
             * @default
             */
            condition: string;
            /**
             * Gravite
             * @description INTERDIT ou PRECAUTION
             */
            gravite: string;
            /** Message */
            message: string;
        };
        /** AlerteStockResponse */
        AlerteStockResponse: {
            /** Article Id */
            article_id: string;
            /** Code */
            code: string;
            /** Date Peremption */
            date_peremption?: string | null;
            /** Designation */
            designation: string;
            /** Jours Restants */
            jours_restants?: number | null;
            /** Message */
            message: string;
            /** Niveau */
            niveau: string;
            /** Seuil */
            seuil?: number | null;
            /** Stock Actuel */
            stock_actuel: number;
            /** Type */
            type: string;
            /** Unite */
            unite: string;
        };
        /**
         * Allergie
         * @description Entrée de la liste `allergies` (JSONB) de l'état général (dictionnaire §5.2).
         */
        Allergie: {
            /**
             * Reaction
             * @description Manifestation observée
             */
            reaction?: string | null;
            /**
             * Severite
             * @description legere | moderee | grave
             * @default legere
             */
            severite: string;
            /**
             * Substance
             * @description Ex: Pénicilline, Latex, Iode
             */
            substance: string;
        };
        /** AnnonceCreate */
        AnnonceCreate: {
            /** Debut */
            debut?: string | null;
            /** Fin */
            fin?: string | null;
            /** Message */
            message: string;
            /**
             * Plans Cibles
             * @default []
             */
            plans_cibles: string[];
            /**
             * Tenants Cibles
             * @default []
             */
            tenants_cibles: string[];
            /** Titre */
            titre: string;
            /**
             * Type Annonce
             * @description INFO | MAINTENANCE | NOUVEAUTE | INCIDENT
             * @default INFO
             */
            type_annonce: string;
        };
        /** AnnonceResponse */
        AnnonceResponse: {
            /** Active */
            active: boolean;
            /**
             * Cree Le
             * Format: date-time
             */
            cree_le: string;
            /** Cree Par */
            cree_par?: string | null;
            /** Debut */
            debut?: string | null;
            /** Fin */
            fin?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Message */
            message: string;
            /**
             * Plans Cibles
             * @default []
             */
            plans_cibles: string[];
            /**
             * Tenants Cibles
             * @default []
             */
            tenants_cibles: string[];
            /** Titre */
            titre: string;
            /** Type Annonce */
            type_annonce: string;
        };
        /** AntecedentMedicalCreate */
        AntecedentMedicalCreate: {
            /**
             * Date Survenue
             * @description Date de survenue (nullable si non précisée)
             */
            date_survenue?: string | null;
            /**
             * Description
             * @description Description de l'antécédent
             */
            description: string;
            /**
             * En Cours
             * @description L'antécédent est-il toujours actif ?
             * @default false
             */
            en_cours: boolean;
            /** Notes */
            notes?: string | null;
            /**
             * Traitement Associe
             * @description Traitement en cours
             */
            traitement_associe?: string | null;
            /**
             * Type Antecedent
             * @description CHIRURGICAL | CARDIO | RESPIRATOIRE | ALLERGIE | DIABETE | HTA | FAMILIAL | DENTAIRE
             */
            type_antecedent: string;
        };
        /** AntecedentMedicalResponse */
        AntecedentMedicalResponse: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Date Survenue */
            date_survenue?: string | null;
            /** Description */
            description: string;
            /**
             * Dossier Medical Id
             * Format: uuid
             */
            dossier_medical_id: string;
            /** En Cours */
            en_cours: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Notes */
            notes?: string | null;
            /** Traitement Associe */
            traitement_associe?: string | null;
            /** Type Antecedent */
            type_antecedent: string;
        };
        /** AntecedentMedicalUpdate */
        AntecedentMedicalUpdate: {
            /** Date Survenue */
            date_survenue?: string | null;
            /** Description */
            description?: string | null;
            /** En Cours */
            en_cours?: boolean | null;
            /** Notes */
            notes?: string | null;
            /** Traitement Associe */
            traitement_associe?: string | null;
            /** Type Antecedent */
            type_antecedent?: string | null;
        };
        /** APIResponse[AbonnementResponse] */
        APIResponse_AbonnementResponse_: {
            data?: components["schemas"]["AbonnementResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[AccesSupportResponse] */
        APIResponse_AccesSupportResponse_: {
            data?: components["schemas"]["AccesSupportResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[ActeRealiseResponse] */
        APIResponse_ActeRealiseResponse_: {
            data?: components["schemas"]["ActeRealiseResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[Activation2FAResponse] */
        APIResponse_Activation2FAResponse_: {
            data?: components["schemas"]["Activation2FAResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[AgendaResponse] */
        APIResponse_AgendaResponse_: {
            data?: components["schemas"]["AgendaResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[AnnonceResponse] */
        APIResponse_AnnonceResponse_: {
            data?: components["schemas"]["AnnonceResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[AntecedentMedicalResponse] */
        APIResponse_AntecedentMedicalResponse_: {
            data?: components["schemas"]["AntecedentMedicalResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[ArticleStockResponse] */
        APIResponse_ArticleStockResponse_: {
            data?: components["schemas"]["ArticleStockResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[CabinetResponse] */
        APIResponse_CabinetResponse_: {
            data?: components["schemas"]["CabinetResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[ChartingParodontalResponse] */
        APIResponse_ChartingParodontalResponse_: {
            data?: components["schemas"]["ChartingParodontalResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[CommandeResponse] */
        APIResponse_CommandeResponse_: {
            data?: components["schemas"]["CommandeResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[ConsultationDetailResponse] */
        APIResponse_ConsultationDetailResponse_: {
            data?: components["schemas"]["ConsultationDetailResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[ConsultationResponse] */
        APIResponse_ConsultationResponse_: {
            data?: components["schemas"]["ConsultationResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[ControleContreIndicationResponse] */
        APIResponse_ControleContreIndicationResponse_: {
            data?: components["schemas"]["ControleContreIndicationResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[CreationUtilisateurResponse] */
        APIResponse_CreationUtilisateurResponse_: {
            data?: components["schemas"]["CreationUtilisateurResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[CreneauxResponse] */
        APIResponse_CreneauxResponse_: {
            data?: components["schemas"]["CreneauxResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[DashboardResponse] */
        APIResponse_DashboardResponse_: {
            data?: components["schemas"]["DashboardResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[DentResponse] */
        APIResponse_DentResponse_: {
            data?: components["schemas"]["DentResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[DetailUtilisateurResponse] */
        APIResponse_DetailUtilisateurResponse_: {
            data?: components["schemas"]["DetailUtilisateurResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[DevisResponse] */
        APIResponse_DevisResponse_: {
            data?: components["schemas"]["DevisResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[dict] */
        APIResponse_dict_: {
            /** Data */
            data?: {
                [key: string]: unknown;
            } | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[DisponibiliteResponse] */
        APIResponse_DisponibiliteResponse_: {
            data?: components["schemas"]["DisponibiliteResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[Enrolement2FAResponse] */
        APIResponse_Enrolement2FAResponse_: {
            data?: components["schemas"]["Enrolement2FAResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[EtatGeneralResponse] */
        APIResponse_EtatGeneralResponse_: {
            data?: components["schemas"]["EtatGeneralResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[FacturePlateformeResponse] */
        APIResponse_FacturePlateformeResponse_: {
            data?: components["schemas"]["FacturePlateformeResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[FactureResponse] */
        APIResponse_FactureResponse_: {
            data?: components["schemas"]["FactureResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[FauteuilResponse] */
        APIResponse_FauteuilResponse_: {
            data?: components["schemas"]["FauteuilResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[FournisseurResponse] */
        APIResponse_FournisseurResponse_: {
            data?: components["schemas"]["FournisseurResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[HistoriqueDentResponse] */
        APIResponse_HistoriqueDentResponse_: {
            data?: components["schemas"]["HistoriqueDentResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[InscriptionResponse] */
        APIResponse_InscriptionResponse_: {
            data?: components["schemas"]["InscriptionResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[AbonnementResponse]] */
        APIResponse_List_AbonnementResponse__: {
            /** Data */
            data?: components["schemas"]["AbonnementResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[AccesSupportResponse]] */
        APIResponse_List_AccesSupportResponse__: {
            /** Data */
            data?: components["schemas"]["AccesSupportResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[ActeRealiseResponse]] */
        APIResponse_List_ActeRealiseResponse__: {
            /** Data */
            data?: components["schemas"]["ActeRealiseResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[AlerteStockResponse]] */
        APIResponse_List_AlerteStockResponse__: {
            /** Data */
            data?: components["schemas"]["AlerteStockResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[AnnonceResponse]] */
        APIResponse_List_AnnonceResponse__: {
            /** Data */
            data?: components["schemas"]["AnnonceResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[AntecedentMedicalResponse]] */
        APIResponse_List_AntecedentMedicalResponse__: {
            /** Data */
            data?: components["schemas"]["AntecedentMedicalResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[CabinetResponse]] */
        APIResponse_List_CabinetResponse__: {
            /** Data */
            data?: components["schemas"]["CabinetResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[ChartingParodontalResponse]] */
        APIResponse_List_ChartingParodontalResponse__: {
            /** Data */
            data?: components["schemas"]["ChartingParodontalResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[CreneauLibre]] */
        APIResponse_List_CreneauLibre__: {
            /** Data */
            data?: components["schemas"]["CreneauLibre"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[dict]] */
        APIResponse_List_dict__: {
            /** Data */
            data?: {
                [key: string]: unknown;
            }[] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[DisponibiliteResponse]] */
        APIResponse_List_DisponibiliteResponse__: {
            /** Data */
            data?: components["schemas"]["DisponibiliteResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[EtatHistoriqueResponse]] */
        APIResponse_List_EtatHistoriqueResponse__: {
            /** Data */
            data?: components["schemas"]["EtatHistoriqueResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[FauteuilResponse]] */
        APIResponse_List_FauteuilResponse__: {
            /** Data */
            data?: components["schemas"]["FauteuilResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[HistoriqueStatutEntry]] */
        APIResponse_List_HistoriqueStatutEntry__: {
            /** Data */
            data?: components["schemas"]["HistoriqueStatutEntry"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[MedicamentResponse]] */
        APIResponse_List_MedicamentResponse__: {
            /** Data */
            data?: components["schemas"]["MedicamentResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[PermissionPlateformeResponse]] */
        APIResponse_List_PermissionPlateformeResponse__: {
            /** Data */
            data?: components["schemas"]["PermissionPlateformeResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[PlanResponse]] */
        APIResponse_List_PlanResponse__: {
            /** Data */
            data?: components["schemas"]["PlanResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[PlanRevisionResponse]] */
        APIResponse_List_PlanRevisionResponse__: {
            /** Data */
            data?: components["schemas"]["PlanRevisionResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[PraticienResponse]] */
        APIResponse_List_PraticienResponse__: {
            /** Data */
            data?: components["schemas"]["PraticienResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[RolePlateformeResponse]] */
        APIResponse_List_RolePlateformeResponse__: {
            /** Data */
            data?: components["schemas"]["RolePlateformeResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[RoleResponse]] */
        APIResponse_List_RoleResponse__: {
            /** Data */
            data?: components["schemas"]["RoleResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[SalleResponse]] */
        APIResponse_List_SalleResponse__: {
            /** Data */
            data?: components["schemas"]["SalleResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[List[SocieteResponse]] */
        APIResponse_List_SocieteResponse__: {
            /** Data */
            data?: components["schemas"]["SocieteResponse"][] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[LoginPlateformeResponse] */
        APIResponse_LoginPlateformeResponse_: {
            data?: components["schemas"]["LoginPlateformeResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[MasterTokenResponse] */
        APIResponse_MasterTokenResponse_: {
            data?: components["schemas"]["MasterTokenResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[MedicamentResponse] */
        APIResponse_MedicamentResponse_: {
            data?: components["schemas"]["MedicamentResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[MotDePasseTemporaireResponse] */
        APIResponse_MotDePasseTemporaireResponse_: {
            data?: components["schemas"]["MotDePasseTemporaireResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[MouvementStockResponse] */
        APIResponse_MouvementStockResponse_: {
            data?: components["schemas"]["MouvementStockResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[NoneType] */
        APIResponse_NoneType_: {
            /** Data */
            data?: null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[OdontogrammeResponse] */
        APIResponse_OdontogrammeResponse_: {
            data?: components["schemas"]["OdontogrammeResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[OnboardingEtatResponse] */
        APIResponse_OnboardingEtatResponse_: {
            data?: components["schemas"]["OnboardingEtatResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[OrdonnanceResponse] */
        APIResponse_OrdonnanceResponse_: {
            data?: components["schemas"]["OrdonnanceResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[PaiementResponse] */
        APIResponse_PaiementResponse_: {
            data?: components["schemas"]["PaiementResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[PatientDossierCompletResponse] */
        APIResponse_PatientDossierCompletResponse_: {
            data?: components["schemas"]["PatientDossierCompletResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[PatientResponse] */
        APIResponse_PatientResponse_: {
            data?: components["schemas"]["PatientResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[PlanEchelonnementResponse] */
        APIResponse_PlanEchelonnementResponse_: {
            data?: components["schemas"]["PlanEchelonnementResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[PlanResponse] */
        APIResponse_PlanResponse_: {
            data?: components["schemas"]["PlanResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[PlatformProfilResponse] */
        APIResponse_PlatformProfilResponse_: {
            data?: components["schemas"]["PlatformProfilResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[PlatformTokenResponse] */
        APIResponse_PlatformTokenResponse_: {
            data?: components["schemas"]["PlatformTokenResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[PraticienResponse] */
        APIResponse_PraticienResponse_: {
            data?: components["schemas"]["PraticienResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[QuotaResumeResponse] */
        APIResponse_QuotaResumeResponse_: {
            data?: components["schemas"]["QuotaResumeResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[RattachementResponse] */
        APIResponse_RattachementResponse_: {
            data?: components["schemas"]["RattachementResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[ReceptionResponse] */
        APIResponse_ReceptionResponse_: {
            data?: components["schemas"]["ReceptionResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[ReferentielJoursResponse] */
        APIResponse_ReferentielJoursResponse_: {
            data?: components["schemas"]["ReferentielJoursResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[RegenererCodesSecoursResponse] */
        APIResponse_RegenererCodesSecoursResponse_: {
            data?: components["schemas"]["RegenererCodesSecoursResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[RendezVousResponse] */
        APIResponse_RendezVousResponse_: {
            data?: components["schemas"]["RendezVousResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[RoleResponse] */
        APIResponse_RoleResponse_: {
            data?: components["schemas"]["RoleResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[SalleResponse] */
        APIResponse_SalleResponse_: {
            data?: components["schemas"]["SalleResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[SessionCaisseResponse] */
        APIResponse_SessionCaisseResponse_: {
            data?: components["schemas"]["SessionCaisseResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[SocieteResponse] */
        APIResponse_SocieteResponse_: {
            data?: components["schemas"]["SocieteResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[StatsGlobalesResponse] */
        APIResponse_StatsGlobalesResponse_: {
            data?: components["schemas"]["StatsGlobalesResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[StatsTenantResponse] */
        APIResponse_StatsTenantResponse_: {
            data?: components["schemas"]["StatsTenantResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[StatutRendezVousResponse] */
        APIResponse_StatutRendezVousResponse_: {
            data?: components["schemas"]["StatutRendezVousResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[SuperAdminResponse] */
        APIResponse_SuperAdminResponse_: {
            data?: components["schemas"]["SuperAdminResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[SupportTokenResponse] */
        APIResponse_SupportTokenResponse_: {
            data?: components["schemas"]["SupportTokenResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[TenantCreationResponse] */
        APIResponse_TenantCreationResponse_: {
            data?: components["schemas"]["TenantCreationResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[TenantDetailResponse] */
        APIResponse_TenantDetailResponse_: {
            data?: components["schemas"]["TenantDetailResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[TokenResponse] */
        APIResponse_TokenResponse_: {
            data?: components["schemas"]["TokenResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[Union[EtatGeneralResponse, NoneType]] */
        APIResponse_Union_EtatGeneralResponse__NoneType__: {
            data?: components["schemas"]["EtatGeneralResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[Union[SessionCaisseResponse, NoneType]] */
        APIResponse_Union_SessionCaisseResponse__NoneType__: {
            data?: components["schemas"]["SessionCaisseResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[UserProfileResponse] */
        APIResponse_UserProfileResponse_: {
            data?: components["schemas"]["UserProfileResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[UtilisateurDetailResponse] */
        APIResponse_UtilisateurDetailResponse_: {
            data?: components["schemas"]["UtilisateurDetailResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[UtilisateurPlateformeResponse] */
        APIResponse_UtilisateurPlateformeResponse_: {
            data?: components["schemas"]["UtilisateurPlateformeResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** APIResponse[UtilisateurResponse] */
        APIResponse_UtilisateurResponse_: {
            data?: components["schemas"]["UtilisateurResponse"] | null;
            /** Message */
            message?: string | null;
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** Archivage */
        Archivage: {
            /**
             * Archiver
             * @description true pour archiver logiquement, false pour rétablir
             */
            archiver: boolean;
            /** Motif */
            motif: string;
        };
        /** ArticleStockCreate */
        ArticleStockCreate: {
            /** Categorie */
            categorie: string;
            /** Code */
            code: string;
            /** Date Peremption */
            date_peremption?: string | null;
            /** Designation */
            designation: string;
            /** Emplacement */
            emplacement?: string | null;
            /**
             * Gere Par Lot
             * @default false
             */
            gere_par_lot: boolean;
            /**
             * Motif Initial
             * @description Motif de l'entrée de stock initial
             */
            motif_initial?: string | null;
            /**
             * Prix Achat
             * @default 0
             */
            prix_achat: number | string;
            /**
             * Quantite Stock
             * @default 0
             */
            quantite_stock: number;
            /**
             * Seuil Alerte
             * @default 0
             */
            seuil_alerte: number;
            /** Unite */
            unite: string;
        };
        /** ArticleStockResponse */
        ArticleStockResponse: {
            /** Actif */
            actif: boolean;
            /** Categorie */
            categorie: string;
            /** Code */
            code: string;
            /** Date Peremption */
            date_peremption?: string | null;
            /** Designation */
            designation: string;
            /** Emplacement */
            emplacement?: string | null;
            /**
             * Gere Par Lot
             * @default false
             */
            gere_par_lot: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Prix Achat */
            prix_achat: string;
            /**
             * Quantite Stock
             * @default 0
             */
            quantite_stock: number;
            /** Seuil Alerte */
            seuil_alerte: number;
            /**
             * Stocks Sites
             * @default []
             */
            stocks_sites: {
                [key: string]: unknown;
            }[];
            /** Unite */
            unite: string;
        };
        /**
         * ArticleStockUpdate
         * @description Mise à jour de la fiche d'un article.
         *
         *     Ni `quantite_stock` ni `date_peremption` : ce sont des faits de stock, pas
         *     des propriétés de fiche. Ils se modifient par un mouvement, ce qui laisse
         *     une trace — sinon une correction d'inventaire serait indiscernable d'un
         *     vol.
         */
        ArticleStockUpdate: {
            /** Actif */
            actif?: boolean | null;
            /** Categorie */
            categorie?: string | null;
            /** Code */
            code?: string | null;
            /** Designation */
            designation?: string | null;
            /** Emplacement */
            emplacement?: string | null;
            /** Gere Par Lot */
            gere_par_lot?: boolean | null;
            /** Prix Achat */
            prix_achat?: number | string | null;
            /** Seuil Alerte */
            seuil_alerte?: number | null;
            /** Unite */
            unite?: string | null;
        };
        /** AuditEntryResponse */
        AuditEntryResponse: {
            /** Acteur Email */
            acteur_email?: string | null;
            /** Acteur Id */
            acteur_id?: string | null;
            /** Action */
            action: string;
            /** Apres */
            apres?: {
                [key: string]: unknown;
            } | null;
            /** Avant */
            avant?: {
                [key: string]: unknown;
            } | null;
            /** Cible Id */
            cible_id?: string | null;
            /**
             * Horodatage
             * Format: date-time
             */
            horodatage: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Ip Address */
            ip_address?: string | null;
            /** Motif */
            motif?: string | null;
            /** Tenant Id */
            tenant_id?: string | null;
            /** Type Cible */
            type_cible?: string | null;
            /** User Agent */
            user_agent?: string | null;
        };
        /** AuditLogResponse */
        AuditLogResponse: {
            /** Action */
            action: string;
            /** Changes */
            changes?: {
                [key: string]: unknown;
            } | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Ip Address */
            ip_address?: string | null;
            /** Resource Id */
            resource_id: string;
            /** Resource Type */
            resource_type: string;
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
            /** User Agent */
            user_agent?: string | null;
            /** User Email */
            user_email?: string | null;
            /** User Id */
            user_id?: string | null;
        };
        /**
         * BlocageFauteuilCreate
         * @description Immobilise un fauteuil sur une plage, sans rendez-vous.
         *
         *     Le cas réel : un fauteuil au compresseur en panne. Il ne peut plus être
         *     proposé, et cela doit se voir dans l'agenda comme n'importe quel autre
         *     rendez-vous — c'est pourquoi l'occupation tient dans la MÊME table.
         */
        BlocageFauteuilCreate: {
            /**
             * Debut
             * Format: date-time
             */
            debut: string;
            /**
             * Duree Minutes
             * @default 60
             */
            duree_minutes: number;
            /**
             * Fauteuil Id
             * Format: uuid
             */
            fauteuil_id: string;
            /**
             * Motif
             * @description Un de ('RENDEZ_VOUS', 'MAINTENANCE', 'REPARATION', 'RESERVATION')
             */
            motif: string;
            /** Motif Detail */
            motif_detail?: string | null;
        };
        /** CabinetResponse */
        CabinetResponse: {
            /** Actif */
            actif: boolean;
            /** Adresse */
            adresse?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Email */
            email?: string | null;
            /** Horaires Ouverture */
            horaires_ouverture?: {
                [key: string]: unknown;
            } | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Logo Url */
            logo_url?: string | null;
            /**
             * Nb Fauteuils Actifs
             * @default 0
             */
            nb_fauteuils_actifs: number;
            /**
             * Nb Praticiens Actifs
             * @default 0
             */
            nb_praticiens_actifs: number;
            /**
             * Nb Salles
             * @default 0
             */
            nb_salles: number;
            /** Nom */
            nom: string;
            /** Telephone */
            telephone?: string | null;
            /** Ville */
            ville?: string | null;
        };
        /**
         * CabinetUpdate
         * @description Modification d'un site. Tous les champs sont facultatifs.
         */
        CabinetUpdate: {
            /** Actif */
            actif?: boolean | null;
            /** Adresse */
            adresse?: string | null;
            /** Email */
            email?: string | null;
            /** Horaires Ouverture */
            horaires_ouverture?: {
                [key: string]: unknown;
            } | null;
            /** Logo Url */
            logo_url?: string | null;
            /** Nom */
            nom?: string | null;
            /** Telephone */
            telephone?: string | null;
            /** Ville */
            ville?: string | null;
        };
        /** Challenge2FARequest */
        Challenge2FARequest: {
            /**
             * Code
             * @description Code TOTP à 6 chiffres fourni par l'application
             */
            code: string;
            /**
             * Jeton Challenge
             * @description Défi reçu à l'étape précédente (valable 5 minutes, à usage unique)
             */
            jeton_challenge: string;
        };
        /** ChangementMotDePasseRequest */
        ChangementMotDePasseRequest: {
            /** Ancien */
            ancien: string;
            /** Nouveau */
            nouveau: string;
        };
        /** ChangementPlan */
        ChangementPlan: {
            /** Motif */
            motif?: string | null;
            /**
             * Plan Code
             * @description Code du nouveau plan
             */
            plan_code: string;
        };
        /**
         * ChartingParodontalCreate
         * @description Relevé parodental d'une dent (Étape 6 du CDC).
         */
        ChartingParodontalCreate: {
            /** Consultation Id */
            consultation_id?: string | null;
            /**
             * Dent Id
             * Format: uuid
             */
            dent_id: string;
            /**
             * Furcation
             * @description Furcation 0 à 3
             */
            furcation?: number | null;
            /** Mobilite */
            mobilite?: number | null;
            /**
             * Nac
             * @description Niveau d'attachement clinique
             */
            nac?: number | null;
            /** Notes */
            notes?: string | null;
            /**
             * Plaque Ipv
             * @description Plaque visible / présence de plaque
             * @default false
             */
            plaque_ipv: boolean;
            /**
             * Recession
             * @description Récession gingivale en mm
             */
            recession?: number | null;
            /**
             * Saignement Bop
             * @description Saignement au sondage
             * @default false
             */
            saignement_bop: boolean;
            /**
             * Sondages
             * @description Sondage en 6 points. Omettre un site = non mesuré.
             */
            sondages?: components["schemas"]["SiteSondage"][] | null;
            /**
             * Suppuration
             * @description Suppuration
             * @default false
             */
            suppuration: boolean;
        };
        /** ChartingParodontalResponse */
        ChartingParodontalResponse: {
            /** Consultation Id */
            consultation_id?: string | null;
            /**
             * Date Examen
             * Format: date-time
             */
            date_examen: string;
            /**
             * Dent Id
             * Format: uuid
             */
            dent_id: string;
            /** Furcation */
            furcation?: number | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Mobilite */
            mobilite?: number | null;
            /** Nac */
            nac?: number | null;
            /** Notes */
            notes?: string | null;
            /** Plaque Ipv */
            plaque_ipv: boolean;
            /**
             * Profondeur Moyenne
             * @description Profondeur moyenne de sondage : indicateur de suivi parodontal.
             */
            readonly profondeur_moyenne: number | null;
            /** Recession */
            recession?: number | null;
            /** Saignement Bop */
            saignement_bop: boolean;
            /** Sondages */
            sondages?: {
                [key: string]: unknown;
            }[] | null;
            /** Suppuration */
            suppuration: boolean;
        };
        /** ClotureCaisseCreate */
        ClotureCaisseCreate: {
            /** Especes Comptees */
            especes_comptees: number | string;
            /** Motif Ecart */
            motif_ecart?: string | null;
            /** Notes */
            notes?: string | null;
        };
        /** CommandeCreate */
        CommandeCreate: {
            /**
             * Fournisseur Id
             * Format: uuid
             */
            fournisseur_id: string;
            /** Lignes */
            lignes: components["schemas"]["LigneCommandeCreate"][];
            /** Notes */
            notes?: string | null;
        };
        /** CommandeResponse */
        CommandeResponse: {
            /** Auteur */
            auteur?: string | null;
            /**
             * Date Commande
             * Format: date
             */
            date_commande: string;
            /**
             * Fournisseur Id
             * Format: uuid
             */
            fournisseur_id: string;
            /** Fournisseur Nom */
            fournisseur_nom?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Lignes
             * @default []
             */
            lignes: components["schemas"]["LigneCommandeResponse"][];
            /**
             * Montant Total
             * @default 0
             */
            montant_total: string;
            /** Notes */
            notes?: string | null;
            /** Numero */
            numero: string;
            statut: components["schemas"]["StatutCommandeEnum"];
        };
        /** ConsultationAnnuler */
        ConsultationAnnuler: {
            /**
             * Motif Annulation
             * @description Motif de l'annulation (obligatoire : engage la responsabilité du cabinet)
             */
            motif_annulation: string;
        };
        /**
         * ConsultationCreate
         * @description Démarrage d'une consultation (Étape 4 du CDC).
         */
        ConsultationCreate: {
            /** Anamnese */
            anamnese?: string | null;
            /**
             * Cabinet Id
             * @description Cabinet de realization. Par défaut, l'unique cabinet du tenant.
             */
            cabinet_id?: string | null;
            /**
             * Date Consultation
             * @description Par défaut, maintenant. Permet la saisie différée (consultation d'urgence).
             */
            date_consultation?: string | null;
            /**
             * Duree Minutes
             * @description Durée prévue de la séance
             * @default 30
             */
            duree_minutes: number;
            /**
             * Motif
             * @description Motif en clair saisi par le praticien
             */
            motif: string;
            /**
             * Motif Detail
             * @description Précision libre du motif
             */
            motif_detail?: string | null;
            /**
             * Patient Id
             * Format: uuid
             * @description Patient concerné (le dossier médical est résolu côté service)
             */
            patient_id: string;
            /**
             * @description Catégorie de motif (Étape 4 du CDC)
             * @default AUTRE
             */
            type_motif: components["schemas"]["MotifConsultationEnum"];
        };
        /**
         * ConsultationDetailResponse
         * @description Consultation avec ses actes, son total et les alertes cliniques du patient.
         */
        ConsultationDetailResponse: {
            /**
             * Actes
             * @default []
             */
            actes: components["schemas"]["ActeRealiseResponse"][];
            /**
             * Alertes
             * @default []
             */
            alertes: components["schemas"]["AlerteConsultation"][];
            /** Anamnese */
            anamnese?: string | null;
            /** Auteur Email */
            auteur_email?: string | null;
            /**
             * Auteur Id
             * Format: uuid
             */
            auteur_id: string;
            /**
             * Cabinet Id
             * Format: uuid
             */
            cabinet_id: string;
            /** Codes Cim10 */
            codes_cim10?: string[] | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Date Consultation
             * Format: date-time
             */
            date_consultation: string;
            /** Diagnostic Principal */
            diagnostic_principal?: string | null;
            /** Diagnostics Differentiels */
            diagnostics_differentiels?: string[] | null;
            /**
             * Dossier Medical Id
             * Format: uuid
             */
            dossier_medical_id: string;
            /** Duree Minutes */
            duree_minutes: number;
            /** Duree Reelle Minutes */
            duree_reelle_minutes?: number | null;
            /**
             * Etat General A Verifier
             * @default false
             */
            etat_general_a_verifier: boolean;
            /** Examen Endobuccal */
            examen_endobuccal?: string | null;
            /** Examen Exobuccal */
            examen_exobuccal?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Motif */
            motif: string;
            /** Motif Detail */
            motif_detail?: string | null;
            /**
             * Nb Actes
             * @default 0
             */
            nb_actes: number;
            /**
             * Patient Id
             * Format: uuid
             */
            patient_id: string;
            /** Patient Numero Dossier */
            patient_numero_dossier?: string | null;
            /** Plan Traitement */
            plan_traitement?: string | null;
            /** Praticien Id */
            praticien_id?: string | null;
            /** Prochain Rdv Prevu */
            prochain_rdv_prevu?: string | null;
            /** Recommandations */
            recommandations?: string | null;
            statut: components["schemas"]["StatutConsultationEnum"];
            /**
             * Total Actes
             * @default 0.00
             */
            total_actes: string;
            type_motif: components["schemas"]["MotifConsultationEnum"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** ConsultationResponse */
        ConsultationResponse: {
            /** Anamnese */
            anamnese?: string | null;
            /** Auteur Email */
            auteur_email?: string | null;
            /**
             * Auteur Id
             * Format: uuid
             */
            auteur_id: string;
            /**
             * Cabinet Id
             * Format: uuid
             */
            cabinet_id: string;
            /** Codes Cim10 */
            codes_cim10?: string[] | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Date Consultation
             * Format: date-time
             */
            date_consultation: string;
            /** Diagnostic Principal */
            diagnostic_principal?: string | null;
            /** Diagnostics Differentiels */
            diagnostics_differentiels?: string[] | null;
            /**
             * Dossier Medical Id
             * Format: uuid
             */
            dossier_medical_id: string;
            /** Duree Minutes */
            duree_minutes: number;
            /** Examen Endobuccal */
            examen_endobuccal?: string | null;
            /** Examen Exobuccal */
            examen_exobuccal?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Motif */
            motif: string;
            /** Motif Detail */
            motif_detail?: string | null;
            /**
             * Patient Id
             * Format: uuid
             */
            patient_id: string;
            /** Patient Numero Dossier */
            patient_numero_dossier?: string | null;
            /** Plan Traitement */
            plan_traitement?: string | null;
            /** Praticien Id */
            praticien_id?: string | null;
            /** Prochain Rdv Prevu */
            prochain_rdv_prevu?: string | null;
            /** Recommandations */
            recommandations?: string | null;
            statut: components["schemas"]["StatutConsultationEnum"];
            type_motif: components["schemas"]["MotifConsultationEnum"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * ConsultationTerminer
         * @description Clôture de la consultation (Étape 6 du CDC).
         */
        ConsultationTerminer: {
            /** Codes Cim10 */
            codes_cim10?: string[] | null;
            /**
             * Diagnostic Principal
             * @description Obligatoire si absent de la consultation : on ne clôt pas sans diagnostic.
             */
            diagnostic_principal?: string | null;
            /** Plan Traitement */
            plan_traitement?: string | null;
            /** Prochain Rdv Prevu */
            prochain_rdv_prevu?: string | null;
            /** Recommandations */
            recommandations?: string | null;
        };
        /**
         * ConsultationUpdate
         * @description Mise à jour clinique. Interdite sur une consultation terminée ou annulée.
         */
        ConsultationUpdate: {
            /** Anamnese */
            anamnese?: string | null;
            /** Codes Cim10 */
            codes_cim10?: string[] | null;
            /** Diagnostic Principal */
            diagnostic_principal?: string | null;
            /** Diagnostics Differentiels */
            diagnostics_differentiels?: string[] | null;
            /** Duree Minutes */
            duree_minutes?: number | null;
            /** Examen Endobuccal */
            examen_endobuccal?: string | null;
            /** Examen Exobuccal */
            examen_exobuccal?: string | null;
            /** Motif */
            motif?: string | null;
            /** Motif Detail */
            motif_detail?: string | null;
            /** Plan Traitement */
            plan_traitement?: string | null;
            /** Prochain Rdv Prevu */
            prochain_rdv_prevu?: string | null;
            /** Recommandations */
            recommandations?: string | null;
            type_motif?: components["schemas"]["MotifConsultationEnum"] | null;
        };
        /**
         * ControleContreIndication
         * @description Corps du contrôle à blanc : une ligne d'ordonnance, plus le patient visé.
         *
         *     `patient_id` est ici et non en query string parce qu'un contrôle à blanc
         *     EST une proposition d'ordonnance : tout ce qui la décrit doit tenir dans le
         *     même corps, sinon le frontend risque de contrôler pour un patient et
         *     prescrire pour un autre.
         */
        ControleContreIndication: {
            /**
             * Duree
             * @description Ex: 7 jours
             */
            duree?: string | null;
            /** Instructions */
            instructions?: string | null;
            /**
             * Justification Precaution
             * @description Obligatoire si le médicament déclenche une simple précaution (RG08).
             */
            justification_precaution?: string | null;
            /**
             * Medicament Id
             * @description Médicament du référentiel
             */
            medicament_id?: string | null;
            /**
             * Medicament Texte
             * @description Libellé libre si le produit n'est pas au référentiel
             */
            medicament_texte?: string | null;
            /**
             * Patient Id
             * Format: uuid
             */
            patient_id: string;
            /**
             * Posologie
             * @default 1 comprimé matin et soir
             */
            posologie: string;
            /**
             * Quantite
             * @default 1
             */
            quantite: number;
        };
        /**
         * ControleContreIndicationResponse
         * @description Résultat du contrôle à blanc (UC8).
         */
        ControleContreIndicationResponse: {
            /**
             * Alertes
             * @default []
             */
            alertes: components["schemas"]["AlertePrescription"][];
            /**
             * Conditions Actives
             * @description État clinique du patient ayant déclenché ces règles
             */
            conditions_actives?: {
                [key: string]: unknown;
            }[];
            /** Justification Requise */
            justification_requise: boolean;
            /** Prescription Possible */
            prescription_possible: boolean;
        };
        /** CreationUtilisateurResponse */
        CreationUtilisateurResponse: {
            /** @description À transmettre à l'utilisateur : le secret n'est plus jamais renvoyé ensuite */
            activation_2fa?: components["schemas"]["Activation2FAResponse"] | null;
            utilisateur: components["schemas"]["UtilisateurPlateformeResponse"];
        };
        /** CreneauLibre */
        CreneauLibre: {
            /**
             * Debut
             * Format: date-time
             */
            debut: string;
            /**
             * Fin
             * Format: date-time
             */
            fin: string;
        };
        /**
         * CreneauxResponse
         * @description Créneaux réellement proposables au patient pour une date.
         *
         *     C'est le calcul que le module Agenda consommera pour proposer des horaires
         *     au secrétariat. Il est exposé dès maintenant parce que le secrétariat en a
         *     besoin pour répondre au téléphone, avant même que le module Agenda existe.
         */
        CreneauxResponse: {
            /** Avertissement */
            avertissement?: string | null;
            /** Cabinet Id */
            cabinet_id?: string | null;
            /**
             * Creneaux
             * @description Paires ["HH:MM", "HH:MM"]. 30 min par défaut.
             */
            creneaux?: string[][];
            /**
             * Date
             * Format: date
             */
            date: string;
            /**
             * Duree Minutes
             * @default 30
             */
            duree_minutes: number;
            /**
             * Nb Plages Bloquantes
             * @default 0
             */
            nb_plages_bloquantes: number;
            /**
             * Nb Plages Consultation
             * @default 0
             */
            nb_plages_consultation: number;
            /**
             * Praticien Id
             * Format: uuid
             */
            praticien_id: string;
        };
        /**
         * DashboardItem
         * @description Un cabinet résumé pour le tableau de bord (pas de contenu clinique).
         */
        DashboardItem: {
            /** Jours Inactivite */
            jours_inactivite?: number | null;
            /** Nom */
            nom: string;
            /** Plan */
            plan?: string | null;
            /** Quotas */
            quotas?: {
                [key: string]: unknown;
            } | null;
            /** Statut */
            statut: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
        };
        /**
         * DashboardResponse
         * @description Tout ce que le tableau de bord affiche, dans **un** appel HTTP.
         *
         *     L'écran ne doit jamais faire deux requêtes pour une donnée agrégée : la
         *     latence de l'agrégation est payée par le serveur, une fois. Aucun contenu
         *     clinique, jamais — ces listes ne sont que des compteurs et des noms de
         *     cabinets déjà exposés par d'autres routes du monde plateforme.
         */
        DashboardResponse: {
            /**
             * Annonces
             * @default []
             */
            annonces: components["schemas"]["AnnonceResponse"][];
            /**
             * Audit
             * @default []
             */
            audit: components["schemas"]["AuditEntryResponse"][];
            /**
             * Essais Proches Expiration
             * @default []
             */
            essais_proches_expiration: components["schemas"]["DashboardItem"][];
            /**
             * Essais Restants Jours
             * @default 14
             */
            essais_restants_jours: number;
            /**
             * Inactifs 30J
             * @default []
             */
            inactifs_30j: components["schemas"]["DashboardItem"][];
            /**
             * Nouveaux 30J
             * @default 0
             */
            nouveaux_30j: number;
            /**
             * Par Formule
             * @default {}
             */
            par_formule: {
                [key: string]: number;
            };
            /**
             * Par Statut
             * @default {}
             */
            par_statut: {
                [key: string]: number;
            };
            /**
             * Proches Du Quota
             * @default []
             */
            proches_du_quota: components["schemas"]["DashboardItem"][];
            /**
             * Sante
             * @default {}
             */
            sante: {
                [key: string]: unknown;
            };
            /**
             * Total Cabinets
             * @default 0
             */
            total_cabinets: number;
        };
        /**
         * DentMiseAJour
         * @description Changement d'état d'une dent, identifiée par son numéro FDI.
         *
         *     Utilisé pour la mise à jour unitaire comme pour le lot : un seul schéma
         *     évite que les deux chemins n'appliquent des règles différentes.
         *
         *     Le nouvel état est obligatoire : c'est lui qui sera historisé (RG10).
         *     Répéter l'état courant n'est pas une erreur — un constat se confirme — mais
         *     l'historique conserve la ligne, avec un état antérieur identique.
         */
        DentMiseAJour: {
            /**
             * Consultation Id
             * @description Consultation à l'origine du constat (traçabilité RG10)
             */
            consultation_id?: string | null;
            /**
             * Date Constat
             * @description Par défaut, maintenant. Permet de rectifier un constat daté.
             */
            date_constat?: string | null;
            /**
             * Etat
             * @description État de la dent. Valeurs : 37 (dictionnaire §5.1)
             */
            etat: string;
            /**
             * Face
             * @description Face concernée, si la lésion est localisée
             */
            face?: string | null;
            /** Mobilite */
            mobilite?: number | null;
            /** Notes */
            notes?: string | null;
            /**
             * Numero Fdi
             * @description Numéro FDI de la dent (11-48 définitives, 51-85 lait)
             */
            numero_fdi: number;
            /**
             * Praticien Id
             * @description Praticien auteur. Par défaut, le praticien de l'utilisateur connecté.
             */
            praticien_id?: string | null;
        };
        /**
         * DentResponse
         * @description État courant d'une dent, prêt pour le rendu du composant SVG.
         */
        DentResponse: {
            /**
             * A Alerte
             * @default false
             */
            a_alerte: boolean;
            /** Etat Actuel */
            etat_actuel: string;
            /** Etat Libelle */
            etat_libelle?: string | null;
            /**
             * Faces
             * @default []
             */
            faces: components["schemas"]["FaceDentResponse"][];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Mobilite
             * @default 0
             */
            mobilite: number;
            /** Notes */
            notes?: string | null;
            /** Numero Fdi */
            numero_fdi: number;
            /** Numero Universal */
            numero_universal?: number | null;
        };
        /**
         * DentsMiseAJourLot
         * @description Mise à jour de plusieurs dents en une seule requête.
         *
         *     Utile au cabinet : un rendez-vous de détartrage touche souvent six dents
         *     d'un coup. Sans ce point d'entrée, il faudrait six requêtes et six
         *     écritures d'historique quasi identiques.
         */
        DentsMiseAJourLot: {
            /**
             * Consultation Id
             * @description Consultation commune à toutes les dents du lot
             */
            consultation_id?: string | null;
            /** Dents */
            dents: components["schemas"]["DentMiseAJour"][];
            /**
             * Praticien Id
             * @description Praticien commun à toutes les dents du lot
             */
            praticien_id?: string | null;
        };
        /** DesactivationRequest */
        DesactivationRequest: {
            /**
             * Motif
             * @description Motif obligatoire (journalisé)
             */
            motif: string;
        };
        /** DetailUtilisateurResponse */
        DetailUtilisateurResponse: {
            /** Permissions */
            permissions: string[];
            /** Sessions Actives */
            sessions_actives: number;
            utilisateur: components["schemas"]["UtilisateurPlateformeResponse"];
        };
        /** DevisCreate */
        DevisCreate: {
            /** Cabinet Id */
            cabinet_id?: string | null;
            /**
             * Date Validite
             * @description Par défaut : aujourd'hui + 30 jours
             */
            date_validite?: string | null;
            /** Lignes */
            lignes: components["schemas"]["LigneDevisEntree"][];
            /** Notes */
            notes?: string | null;
            /**
             * Patient Id
             * Format: uuid
             */
            patient_id: string;
            /** Praticien Id */
            praticien_id?: string | null;
        };
        /** DevisResponse */
        DevisResponse: {
            /** Cabinet Id */
            cabinet_id?: string | null;
            /** Date Signature */
            date_signature?: string | null;
            /** Date Validite */
            date_validite?: string | null;
            /** Facture Id */
            facture_id?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Lignes
             * @default []
             */
            lignes: components["schemas"]["LigneDevisResponse"][];
            /** Montant Total */
            montant_total: string;
            /** Notes */
            notes?: string | null;
            /** Numero */
            numero: string;
            /**
             * Patient Id
             * Format: uuid
             */
            patient_id: string;
            /** Praticien Id */
            praticien_id?: string | null;
            /** Signature Patient */
            signature_patient: boolean;
            statut: components["schemas"]["StatutDevisEnum"];
        };
        /**
         * DevisStatutUpdate
         * @description Transition du cycle de vie du devis. Voir `referentiel` du router.
         */
        DevisStatutUpdate: {
            /**
             * Signature Patient
             * @description Signature du patient, requise pour marquer un devis ACCEPTE
             * @default false
             */
            signature_patient: boolean;
            statut: components["schemas"]["StatutDevisEnum"];
        };
        /**
         * DisponibiliteCreate
         * @description Une plage de travail d'un praticien.
         *
         *     Récurrente (`jour_semaine`) ou exceptionnelle (`date_specifique`), ou les
         *     deux — une plage d'exception s'ajoute alors à la récurrence du même jour.
         */
        DisponibiliteCreate: {
            /**
             * Actif
             * @default true
             */
            actif: boolean;
            /**
             * Cabinet Id
             * @description Site concerné. Absent = valable pour tous les sites du praticien.
             */
            cabinet_id?: string | null;
            /**
             * Date Specifique
             * @description Jour précis (congé, remplacement).
             */
            date_specifique?: string | null;
            /**
             * Heure Debut
             * Format: time
             */
            heure_debut: string;
            /**
             * Heure Fin
             * Format: time
             */
            heure_fin: string;
            /**
             * Jour Semaine
             * @description 0 = lundi … 6 = dimanche. Absent = plage d'exception.
             */
            jour_semaine?: number | null;
            /**
             * Type
             * @description Un de ('CONSULTATION', 'URGENCE', 'BLOCKING')
             * @default CONSULTATION
             */
            type: string;
        };
        /** DisponibiliteResponse */
        DisponibiliteResponse: {
            /** Actif */
            actif: boolean;
            /** Cabinet Id */
            cabinet_id?: string | null;
            /** Date Specifique */
            date_specifique?: string | null;
            /**
             * Duree Minutes
             * @default 0
             */
            duree_minutes: number;
            /**
             * Heure Debut
             * Format: time
             */
            heure_debut: string;
            /**
             * Heure Fin
             * Format: time
             */
            heure_fin: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Jour Semaine */
            jour_semaine?: number | null;
            /** Libelle Jour */
            libelle_jour?: string | null;
            /** Plage */
            plage?: string | null;
            /**
             * Praticien Id
             * Format: uuid
             */
            praticien_id: string;
            /** Type */
            type: string;
        };
        /** EcheanceResponse */
        EcheanceResponse: {
            /** Date Paiement */
            date_paiement?: string | null;
            /**
             * Date Prevue
             * Format: date
             */
            date_prevue: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Montant Paye */
            montant_paye: string;
            /** Montant Prevu */
            montant_prevu: string;
            /** Numero */
            numero: number;
            /** Paiement Id */
            paiement_id?: string | null;
            statut: components["schemas"]["StatutEcheanceEnum"];
        };
        /**
         * Enrolement2FAResponse
         * @description Renvoye une fois, a l'activation : les codes de secours ne ressortent plus.
         */
        Enrolement2FAResponse: {
            /** Access Token */
            access_token: string;
            /** Codes Secours */
            codes_secours: string[];
            /** Expires In */
            expires_in: number;
            /** Refresh Expires In */
            refresh_expires_in: number;
            /** Refresh Token */
            refresh_token: string;
        };
        /** EtatGeneralCreate */
        EtatGeneralCreate: {
            /**
             * Alcool
             * @default false
             */
            alcool: boolean;
            /**
             * Allaitement
             * @description Allaitement en cours (RG04)
             * @default false
             */
            allaitement: boolean;
            /** Allergies */
            allergies?: components["schemas"]["Allergie"][] | null;
            /**
             * Antecedents Familiaux
             * @description Antécédents familiaux, texte libre
             */
            antecedents_familiaux?: string | null;
            /** Autres Conditions */
            autres_conditions?: string[] | null;
            /**
             * Diabete
             * @description Diabète connu (RG04 : précautions anesthésiques)
             * @default false
             */
            diabete: boolean;
            /**
             * Diabete Traitement
             * @description Traitement en cours (ex: Metformine 850 mg)
             */
            diabete_traitement?: string | null;
            /**
             * Diabete Type
             * @description type1 | type2 | gestationnel
             */
            diabete_type?: string | null;
            /** Examens Complementaires */
            examens_complementaires?: components["schemas"]["ExamenComplementaire"][] | null;
            /**
             * Grossesse
             * @description Patiente enceinte (RG04 : bloque certains médicaments)
             * @default false
             */
            grossesse: boolean;
            /**
             * Grossesse Terme
             * @description Terme de grossesse (ex: 32 SA / 8 mois)
             */
            grossesse_terme?: string | null;
            /**
             * Groupe Sanguin
             * @description Groupe sanguin (ex: O+, AB-)
             */
            groupe_sanguin?: string | null;
            /**
             * Hta
             * @description Hypertension artérielle
             * @default false
             */
            hta: boolean;
            /**
             * Hta Traitement
             * @description Traitement en cours (ex: Amlodipine 5 mg)
             */
            hta_traitement?: string | null;
            /**
             * Tabac
             * @default false
             */
            tabac: boolean;
        };
        /** EtatGeneralResponse */
        EtatGeneralResponse: {
            /**
             * A Jour Le
             * @description Dernier contrôle de l'état général. À vérifier à chaque consultation (RG02).
             */
            a_jour_le?: string | null;
            /** Alcool */
            alcool: boolean;
            /** Allaitement */
            allaitement: boolean;
            /** Allergies */
            allergies?: {
                [key: string]: unknown;
            }[] | null;
            /** Antecedents Familiaux */
            antecedents_familiaux?: string | null;
            /** Autres Conditions */
            autres_conditions?: string[] | null;
            /** Diabete */
            diabete: boolean;
            /** Diabete Traitement */
            diabete_traitement?: string | null;
            /** Diabete Type */
            diabete_type?: string | null;
            /**
             * Dossier Medical Id
             * Format: uuid
             */
            dossier_medical_id: string;
            /** Examens Complementaires */
            examens_complementaires?: {
                [key: string]: unknown;
            }[] | null;
            /** Grossesse */
            grossesse: boolean;
            /** Grossesse Terme */
            grossesse_terme?: string | null;
            /** Groupe Sanguin */
            groupe_sanguin?: string | null;
            /** Hta */
            hta: boolean;
            /** Hta Traitement */
            hta_traitement?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Tabac */
            tabac: boolean;
        };
        /**
         * EtatGeneralUpdate
         * @description Mise à jour partielle : uniquement les champs explicitement transmis sont modifiés.
         */
        EtatGeneralUpdate: {
            /** Alcool */
            alcool?: boolean | null;
            /** Allaitement */
            allaitement?: boolean | null;
            /** Allergies */
            allergies?: components["schemas"]["Allergie"][] | null;
            /** Antecedents Familiaux */
            antecedents_familiaux?: string | null;
            /** Autres Conditions */
            autres_conditions?: string[] | null;
            /** Diabete */
            diabete?: boolean | null;
            /** Diabete Traitement */
            diabete_traitement?: string | null;
            /** Diabete Type */
            diabete_type?: string | null;
            /** Examens Complementaires */
            examens_complementaires?: components["schemas"]["ExamenComplementaire"][] | null;
            /** Grossesse */
            grossesse?: boolean | null;
            /** Grossesse Terme */
            grossesse_terme?: string | null;
            /** Groupe Sanguin */
            groupe_sanguin?: string | null;
            /** Hta */
            hta?: boolean | null;
            /** Hta Traitement */
            hta_traitement?: string | null;
            /** Tabac */
            tabac?: boolean | null;
        };
        /** EtatHistoriqueResponse */
        EtatHistoriqueResponse: {
            /** Consultation Id */
            consultation_id?: string | null;
            /**
             * Date Constat
             * Format: date-time
             */
            date_constat: string;
            /**
             * Dent Id
             * Format: uuid
             */
            dent_id: string;
            /** Etat */
            etat: string;
            /** Etat Precedent */
            etat_precedent?: string | null;
            /** Face */
            face?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Notes */
            notes?: string | null;
            /** Praticien Id */
            praticien_id?: string | null;
        };
        /**
         * ExamenComplementaire
         * @description Entrée de la liste `examens_complementaires` (JSONB) (dictionnaire §5.2).
         */
        ExamenComplementaire: {
            /** Date */
            date?: null;
            /** Fichier Url */
            fichier_url?: string | null;
            /** Resultat */
            resultat?: string | null;
            /**
             * Type
             * @description Ex: NFS, Glycémie, Radio panoramique
             */
            type: string;
        };
        /** FaceDentResponse */
        FaceDentResponse: {
            /** Etat */
            etat: string;
            /** Face */
            face: string;
            /** Face Courte */
            face_courte: string;
            /** Notes */
            notes?: string | null;
        };
        /** FaceMiseAJour */
        FaceMiseAJour: {
            /**
             * Etat
             * @description État de la face. Valeurs : 37
             */
            etat: string;
            /** Face */
            face: string;
            /** Notes */
            notes?: string | null;
        };
        /**
         * FacesMiseAJour
         * @description Mise à jour des faces d'une dent en une requête.
         */
        FacesMiseAJour: {
            /** Faces */
            faces: components["schemas"]["FaceMiseAJour"][];
        };
        /**
         * FactureConsultationCreate
         * @description Options d'émission depuis une consultation (le total vient des actes).
         */
        FactureConsultationCreate: {
            /** Date Echeance */
            date_echeance?: string | null;
            /** Notes */
            notes?: string | null;
        };
        /**
         * FactureLibreCreate
         * @description Émission d'une facture hors consultation (produit, forfait, prestation directe).
         *
         *     Pour une facture issue d'une consultation, passer par
         *     `POST /factures/consultation/{consultation_id}` : les lignes y sont
         *     importées des actes réalisés, jamais ressaisies.
         */
        FactureLibreCreate: {
            /**
             * Cabinet Id
             * @description Site émetteur. Optionnel si le tenant n'a qu'un cabinet actif.
             */
            cabinet_id?: string | null;
            /** Date Echeance */
            date_echeance?: string | null;
            /**
             * Lignes
             * @description Au moins une ligne
             */
            lignes: components["schemas"]["LigneFactureEntree"][];
            /** Notes */
            notes?: string | null;
            /**
             * Patient Id
             * Format: uuid
             */
            patient_id: string;
            /**
             * Praticien Id
             * @description Praticien d'origine du soin, si pertinent (facture de prothèse...)
             */
            praticien_id?: string | null;
        };
        /** FacturePlateformeCreate */
        FacturePlateformeCreate: {
            /** Date Echeance */
            date_echeance?: string | null;
            /**
             * Lignes
             * @description [{ 'libelle': str, 'quantite': int, 'prix_unitaire': float, 'montant': float }]
             */
            lignes: {
                [key: string]: unknown;
            }[];
            /** Notes */
            notes?: string | null;
            /** Periode Debut */
            periode_debut?: string | null;
            /** Periode Fin */
            periode_fin?: string | null;
            /**
             * Statut
             * @description BROUILLON | EMISE
             * @default BROUILLON
             */
            statut: string;
        };
        /** FacturePlateformeResponse */
        FacturePlateformeResponse: {
            /** Date Echeance */
            date_echeance?: string | null;
            /** Date Emission */
            date_emission?: string | null;
            /** Date Paiement */
            date_paiement?: string | null;
            /** Devise */
            devise: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Lignes */
            lignes: unknown[];
            /** Montant */
            montant: string;
            /** Notes */
            notes?: string | null;
            /** Numero */
            numero: string;
            /** Periode Debut */
            periode_debut?: string | null;
            /** Periode Fin */
            periode_fin?: string | null;
            /** Reference Externe */
            reference_externe?: string | null;
            /** Statut */
            statut: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
        };
        /** FactureResponse */
        FactureResponse: {
            /**
             * Cabinet Id
             * Format: uuid
             */
            cabinet_id: string;
            /** Consultation Id */
            consultation_id?: string | null;
            /** Date Echeance */
            date_echeance?: string | null;
            /**
             * Date Emission
             * Format: date
             */
            date_emission: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Lignes
             * @default []
             */
            lignes: components["schemas"]["LigneFactureResponse"][];
            /** Montant Paye */
            montant_paye: string;
            /** Montant Restant */
            montant_restant: string;
            /** Montant Total */
            montant_total: string;
            /** Montant Tva */
            montant_tva: string;
            /** Numero */
            numero: string;
            /**
             * Paiements
             * @default []
             */
            paiements: components["schemas"]["PaiementResponse"][];
            /**
             * Patient Id
             * Format: uuid
             */
            patient_id: string;
            /** Praticien Id */
            praticien_id?: string | null;
            statut: components["schemas"]["StatutFactureEnum"];
        };
        /** FauteuilCreate */
        FauteuilCreate: {
            /**
             * Equipements
             * @description Ex: ["radiologie", "micromoteur", "compresseur"]
             */
            equipements?: string[] | null;
            /**
             * Numero
             * @description Libellé interne : F1, Fauteuil 3, Unit Nord…
             */
            numero: string;
        };
        /** FauteuilResponse */
        FauteuilResponse: {
            /** Actif */
            actif: boolean;
            /** Cabinet Id */
            cabinet_id?: string | null;
            /** Cabinet Nom */
            cabinet_nom?: string | null;
            /** Equipements */
            equipements?: string[] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nom Salle */
            nom_salle?: string | null;
            /** Numero */
            numero: string;
            /**
             * Salle Id
             * Format: uuid
             */
            salle_id: string;
        };
        /** FauteuilUpdate */
        FauteuilUpdate: {
            /** Actif */
            actif?: boolean | null;
            /** Equipements */
            equipements?: string[] | null;
            /** Numero */
            numero?: string | null;
        };
        /** FournisseurCreate */
        FournisseurCreate: {
            /** Adresse */
            adresse?: string | null;
            /** Contact */
            contact?: string | null;
            /** Email */
            email?: string | null;
            /** Nom */
            nom: string;
            /** Notes */
            notes?: string | null;
            /** Telephone */
            telephone?: string | null;
        };
        /** FournisseurResponse */
        FournisseurResponse: {
            /** Actif */
            actif: boolean;
            /** Adresse */
            adresse?: string | null;
            /** Contact */
            contact?: string | null;
            /** Email */
            email?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nom */
            nom: string;
            /** Notes */
            notes?: string | null;
            /** Telephone */
            telephone?: string | null;
        };
        /** FournisseurUpdate */
        FournisseurUpdate: {
            /** Actif */
            actif?: boolean | null;
            /** Adresse */
            adresse?: string | null;
            /** Contact */
            contact?: string | null;
            /** Email */
            email?: string | null;
            /** Nom */
            nom?: string | null;
            /** Notes */
            notes?: string | null;
            /** Telephone */
            telephone?: string | null;
        };
        /**
         * FrequenceEchelonnementEnum
         * @description Pas entre deux échéances d'un plan de paiement (RG08).
         * @enum {string}
         */
        FrequenceEchelonnementEnum: "HEBDO" | "BIMENSUEL" | "MENSUEL";
        /** HistoriqueDentResponse */
        HistoriqueDentResponse: {
            dent: components["schemas"]["DentResponse"];
            /** Historique */
            historique: components["schemas"]["EtatHistoriqueResponse"][];
        };
        /** HistoriqueStatutEntry */
        HistoriqueStatutEntry: {
            /** Auteur Email */
            auteur_email: string;
            /**
             * Horodatage
             * Format: date-time
             */
            horodatage: string;
            /** Ip Address */
            ip_address?: string | null;
            /** Motif */
            motif: string;
            /** Statut Nouveau */
            statut_nouveau: string;
            /** Statut Precedent */
            statut_precedent: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * InscriptionCreate
         * @description Formulaire d'inscription publique. Tous les messages d'erreur sont génériques.
         */
        InscriptionCreate: {
            /** Admin Nom */
            admin_nom: string;
            /** Admin Prenom */
            admin_prenom: string;
            /**
             * Email
             * Format: email
             */
            email: string;
            /** Jours Essai */
            jours_essai?: number | null;
            /** Mot De Passe */
            mot_de_passe: string;
            /** Nom Cabinet */
            nom_cabinet: string;
            /**
             * Pays
             * @default Sénégal
             */
            pays: string;
            /**
             * Plan Code
             * @description Formule d'essai ; le plan par défaut si absent
             */
            plan_code?: string | null;
            /**
             * Site Web Trap
             * @description Champ-piège anti-robot, masqué en CSS côté client. Un humain ne le remplit jamais ; un robot le remplit. À laisser vide.
             */
            site_web_trap?: string | null;
            /** Telephone */
            telephone?: string | null;
            /** Ville */
            ville?: string | null;
        };
        /** InscriptionResponse */
        InscriptionResponse: {
            /** Email */
            email: string;
            /**
             * Inscription Id
             * Format: uuid
             */
            inscription_id: string;
            /** Statut */
            statut: string;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
        };
        /** LigneCommandeCreate */
        LigneCommandeCreate: {
            /**
             * Article Id
             * Format: uuid
             */
            article_id: string;
            /** Prix Unitaire */
            prix_unitaire?: number | string | null;
            /** Quantite */
            quantite: number;
        };
        /** LigneCommandeResponse */
        LigneCommandeResponse: {
            /** Article Code */
            article_code?: string | null;
            /** Article Designation */
            article_designation?: string | null;
            /**
             * Article Id
             * Format: uuid
             */
            article_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Prix Unitaire */
            prix_unitaire: string;
            /** Quantite Commandee */
            quantite_commandee: number;
            /** Quantite Recue */
            quantite_recue: number;
        };
        /**
         * LigneDevisEntree
         * @description Ligne d'un devis : acte de nomenclature ou prestation libre.
         */
        LigneDevisEntree: {
            /**
             * Acte Id
             * @description Acte de la nomenclature (traçabilité du plan de traitement)
             */
            acte_id?: string | null;
            /**
             * Dent Numero
             * @description Numéro FDI si la ligne porte sur une dent
             */
            dent_numero?: number | null;
            /** Designation */
            designation: string;
            /** Prix Unitaire */
            prix_unitaire: number | string;
            /**
             * Quantite
             * @default 1
             */
            quantite: number;
        };
        /** LigneDevisResponse */
        LigneDevisResponse: {
            /** Acte Id */
            acte_id?: string | null;
            /** Dent Numero */
            dent_numero?: number | null;
            /** Designation */
            designation: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Montant */
            montant: string;
            /** Prix Unitaire */
            prix_unitaire: string;
            /** Quantite */
            quantite: number;
        };
        /**
         * LigneFactureEntree
         * @description Ligne d'une facture émise hors consultation (vente libre).
         */
        LigneFactureEntree: {
            /**
             * Designation
             * @description Libellé affiché sur la facture
             */
            designation: string;
            /**
             * Prix Unitaire
             * @description Prix unitaire en FCFA
             */
            prix_unitaire: number | string;
            /**
             * Quantite
             * @default 1
             */
            quantite: number;
        };
        /** LigneFactureResponse */
        LigneFactureResponse: {
            /** Acte Realise Id */
            acte_realise_id?: string | null;
            /** Designation */
            designation: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Montant */
            montant: string;
            /** Prix Unitaire */
            prix_unitaire: string;
            /** Quantite */
            quantite: number;
        };
        /**
         * LignePrescriptionCreate
         * @description Ligne d'ordonnance.
         *
         *     `medicament_id` ou `medicament_texte` : au moins l'un des deux. Un produit
         *     hors référentiel reste saisissable (produit local, préparation), mais alors
         *     aucune contre-indication automatique ne peut être évaluée — le service le
         *     signale explicitement.
         */
        LignePrescriptionCreate: {
            /**
             * Duree
             * @description Ex: 7 jours
             */
            duree?: string | null;
            /** Instructions */
            instructions?: string | null;
            /**
             * Justification Precaution
             * @description Obligatoire si le médicament déclenche une simple précaution (RG08).
             */
            justification_precaution?: string | null;
            /**
             * Medicament Id
             * @description Médicament du référentiel
             */
            medicament_id?: string | null;
            /**
             * Medicament Texte
             * @description Libellé libre si le produit n'est pas au référentiel
             */
            medicament_texte?: string | null;
            /**
             * Posologie
             * @default 1 comprimé matin et soir
             */
            posologie: string;
            /**
             * Quantite
             * @default 1
             */
            quantite: number;
        };
        /** LignePrescriptionResponse */
        LignePrescriptionResponse: {
            /** Dci */
            dci?: string | null;
            /** Duree */
            duree?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Instructions */
            instructions?: string | null;
            /** Justification Precaution */
            justification_precaution?: string | null;
            /** Medicament Id */
            medicament_id?: string | null;
            /** Medicament Texte */
            medicament_texte?: string | null;
            /** Nom Commercial */
            nom_commercial?: string | null;
            /** Posologie */
            posologie: string;
            /** Quantite */
            quantite: number;
        };
        /** LigneReceptionCreate */
        LigneReceptionCreate: {
            /** Date Peremption */
            date_peremption?: string | null;
            /**
             * Ligne Commande Id
             * Format: uuid
             */
            ligne_commande_id: string;
            /** Lot Code */
            lot_code?: string | null;
            /** Quantite Recue */
            quantite_recue: number;
        };
        /** LigneReceptionResponse */
        LigneReceptionResponse: {
            /** Date Peremption */
            date_peremption?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Ligne Commande Id
             * Format: uuid
             */
            ligne_commande_id: string;
            /** Lot Code */
            lot_code?: string | null;
            /** Quantite Recue */
            quantite_recue: number;
        };
        /**
         * LoginPlateformeResponse
         * @description Reponse de la premiere etape.
         *
         *     Trois cas distincts, et **jamais** les deux a la fois :
         *
         *     - session ouverte : `access_token` present ;
         *     - defi 2FA         : `jeton_challenge` present ;
         *     - enrolement       : `jeton_enrolement` present.
         *
         *     `access_token` n'est present que si le second facteur est actif. Le garantir
         *     ici evite qu'un evolution du service emette une session a un compte qui n'a
         *     pas de 2FA.
         */
        LoginPlateformeResponse: {
            /** Access Token */
            access_token?: string | null;
            /**
             * Activation Requise
             * @default false
             */
            activation_requise: boolean;
            /**
             * Deux Facteurs Requis
             * @default true
             */
            deux_facteurs_requis: boolean;
            /** Expiration Secondes */
            expiration_secondes?: number | null;
            /** Expires In */
            expires_in?: number | null;
            /** Jeton Challenge */
            jeton_challenge?: string | null;
            /** Jeton Enrolement */
            jeton_enrolement?: string | null;
            /** Refresh Expires In */
            refresh_expires_in?: number | null;
            /** Refresh Token */
            refresh_token?: string | null;
        };
        /** LoginRequest */
        LoginRequest: {
            /**
             * Cabinet Code
             * @description Code / Slug du cabinet si applicable
             */
            cabinet_code?: string | null;
            /**
             * Email
             * Format: email
             * @description Email professionnel
             */
            email: string;
            /**
             * Password
             * @description Mot de passe
             */
            password: string;
        };
        /** MasterTokenResponse */
        MasterTokenResponse: {
            /** Access Token */
            access_token: string;
            /** Email */
            email?: string | null;
            /**
             * Expires In
             * @description Durée de validité de l'access token en secondes
             */
            expires_in: number;
            /** Nom Complet */
            nom_complet?: string | null;
            /** Refresh Token */
            refresh_token: string;
            /**
             * Token Type
             * @default bearer
             */
            token_type: string;
        };
        /**
         * MedicamentCreate
         * @description Ajout d'un médicament au référentiel du cabinet.
         */
        MedicamentCreate: {
            /** Classe Therapeutique */
            classe_therapeutique?: string | null;
            /**
             * Contre Indications
             * @default []
             */
            contre_indications: components["schemas"]["RegleContreIndication"][];
            /**
             * Dci
             * @description Dénomination commune internationale
             */
            dci: string;
            /** Dosage */
            dosage?: string | null;
            /**
             * Forme
             * @default COMPRIME
             */
            forme: string;
            /** Nom Commercial */
            nom_commercial: string;
            /** Posologie Adulte */
            posologie_adulte?: string | null;
            /** Precautions */
            precautions?: string | null;
        };
        /** MedicamentResponse */
        MedicamentResponse: {
            /** Actif */
            actif: boolean;
            /** Classe Therapeutique */
            classe_therapeutique?: string | null;
            /** Contre Indications */
            contre_indications?: {
                [key: string]: unknown;
            }[] | null;
            /** Dci */
            dci: string;
            /** Dosage */
            dosage?: string | null;
            /** Forme */
            forme: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nom Commercial */
            nom_commercial: string;
            /** Posologie Adulte */
            posologie_adulte?: string | null;
            /** Precautions */
            precautions?: string | null;
        };
        /**
         * ModePaiementEnum
         * @enum {string}
         */
        ModePaiementEnum: "ESPECES" | "CARTE_BANCAIRE" | "CHEQUE" | "VIREMENT" | "MOBILE_MONEY" | "ASSURANCE";
        /**
         * MotDePasseTemporaireResponse
         * @description Mot de passe temporaire, renvoyé **une seule fois**.
         *
         *     Le serveur n'en conserve que l'empreinte : il ne peut donc pas le
         *     redonner. L'interface doit le dire explicitement, sinon l'utilisateur
         *     croira avoir saisir un mot de passe définitif.
         */
        MotDePasseTemporaireResponse: {
            /**
             * Avertissement
             * @default Communiquez ce mot de passe à l'utilisateur. Il ne sera plus jamais affiché : seul son empreinte est conservée.
             */
            avertissement: string;
            /** Temporaire */
            temporaire: string;
        };
        /**
         * MotifConsultationEnum
         * @description Motifs prévus par le CDC (Étape 4 du parcours patient).
         * @enum {string}
         */
        MotifConsultationEnum: "DOULEUR" | "CONTROLE" | "URGENCE" | "ESTHETIQUE" | "SUIVI" | "PROTHESE" | "ORTHODONTIE" | "AUTRE";
        /** MouvementStockCreate */
        MouvementStockCreate: {
            /**
             * Article Id
             * Format: uuid
             */
            article_id: string;
            /**
             * Cabinet Id
             * Format: uuid
             */
            cabinet_id: string;
            /** Lot Id */
            lot_id?: string | null;
            /** Motif */
            motif?: string | null;
            /** Quantite */
            quantite: number;
            type_mouvement: components["schemas"]["TypeMouvementStockEnum"];
        };
        /** MouvementStockResponse */
        MouvementStockResponse: {
            /** Article Code */
            article_code?: string | null;
            /** Article Designation */
            article_designation?: string | null;
            /**
             * Article Id
             * Format: uuid
             */
            article_id: string;
            /** Auteur */
            auteur?: string | null;
            /** Auteur Email */
            auteur_email?: string | null;
            /**
             * Cabinet Id
             * Format: uuid
             */
            cabinet_id: string;
            /** Commande Id */
            commande_id?: string | null;
            /**
             * Date Mouvement
             * Format: date-time
             */
            date_mouvement: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Motif */
            motif?: string | null;
            /** Quantite */
            quantite: number;
            /** Stock Apres */
            stock_apres: number;
            /** Stock Avant */
            stock_avant: number;
            type_mouvement: components["schemas"]["TypeMouvementStockEnum"];
        };
        /**
         * OdontogrammeCreer
         * @description Génération explicite d'un odontogramme.
         *
         *     Par défaut l'odontogramme est créé automatiquement à la première lecture :
         *     cette route sert aux cas de reprise (patient créé avant D1C) et au choix
         *     explicite du nombre de dents (RG11).
         */
        OdontogrammeCreer: {
            /**
             * Systeme Notation
             * @description FDI (par défaut) ou UNIVERSAL
             * @default FDI
             */
            systeme_notation: string;
            /**
             * Type
             * @description ADULTE (32 dents), ENFANT (20 dents) ou MIXTE
             * @default ADULTE
             */
            type: string;
        };
        /** OdontogrammeResponse */
        OdontogrammeResponse: {
            /** Dents */
            dents: components["schemas"]["DentResponse"][];
            /**
             * Dossier Medical Id
             * Format: uuid
             */
            dossier_medical_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nb Dents */
            nb_dents: number;
            /**
             * Nb Dents A Traiter
             * @default 0
             */
            nb_dents_a_traiter: number;
            /**
             * Nb Dents Absentes
             * @default 0
             */
            nb_dents_absentes: number;
            /**
             * Nb Dents Soignees
             * @default 0
             */
            nb_dents_soignees: number;
            /**
             * Patient Id
             * Format: uuid
             */
            patient_id: string;
            /**
             * Resume
             * @default
             */
            resume: string;
            /** Systeme Notation */
            systeme_notation: string;
            /** Type */
            type: string;
        };
        /** OnboardingEtatResponse */
        OnboardingEtatResponse: {
            /**
             * Etapes
             * @default []
             */
            etapes: {
                [key: string]: unknown;
            }[];
            /** Progression */
            progression: number;
            /** Tenant Id */
            tenant_id: string;
            /** Terminees */
            terminees: number;
            /** Total */
            total: number;
        };
        /**
         * OrdonnanceCreate
         * @description Émission d'une ordonnance (UC7 « Rédiger ordonnance »).
         */
        OrdonnanceCreate: {
            /**
             * Consultation Id
             * Format: uuid
             */
            consultation_id: string;
            /** Lignes */
            lignes: components["schemas"]["LignePrescriptionCreate"][];
            /**
             * Notes Generales
             * @description Consignes générales (ex: inicioure un bain de bouche chlorhexidine)
             */
            notes_generales?: string | null;
            /**
             * Patient Id
             * Format: uuid
             */
            patient_id: string;
        };
        /** OrdonnanceResponse */
        OrdonnanceResponse: {
            /**
             * Alertes
             * @default []
             */
            alertes: components["schemas"]["AlertePrescription"][];
            /**
             * Consultation Id
             * Format: uuid
             */
            consultation_id: string;
            /**
             * Date Ordonnance
             * Format: date-time
             */
            date_ordonnance: string;
            /** Date Signature */
            date_signature?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Lignes
             * @default []
             */
            lignes: components["schemas"]["LignePrescriptionResponse"][];
            /**
             * Nb Lignes
             * @default 0
             */
            nb_lignes: number;
            /** Notes Generales */
            notes_generales?: string | null;
            /** Numero */
            numero: string;
            /**
             * Patient Id
             * Format: uuid
             */
            patient_id: string;
            /**
             * Praticien Id
             * Format: uuid
             */
            praticien_id: string;
            /** Signe */
            signe: boolean;
        };
        /**
         * OrdonnanceUpdate
         * @description Modification d'une ordonnance NON signée.
         */
        OrdonnanceUpdate: {
            /** Notes Generales */
            notes_generales?: string | null;
        };
        /** OuvertureCaisseCreate */
        OuvertureCaisseCreate: {
            /**
             * Cabinet Id
             * Format: uuid
             */
            cabinet_id: string;
            /** Notes */
            notes?: string | null;
            /**
             * Ouverture Especes
             * @default 0.00
             */
            ouverture_especes: number | string;
        };
        /** PaginatedResponse[ArticleStockResponse] */
        PaginatedResponse_ArticleStockResponse_: {
            /** Items */
            items: components["schemas"]["ArticleStockResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[AuditEntryResponse] */
        PaginatedResponse_AuditEntryResponse_: {
            /** Items */
            items: components["schemas"]["AuditEntryResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[AuditLogResponse] */
        PaginatedResponse_AuditLogResponse_: {
            /** Items */
            items: components["schemas"]["AuditLogResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[CommandeResponse] */
        PaginatedResponse_CommandeResponse_: {
            /** Items */
            items: components["schemas"]["CommandeResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[ConsultationResponse] */
        PaginatedResponse_ConsultationResponse_: {
            /** Items */
            items: components["schemas"]["ConsultationResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[DevisResponse] */
        PaginatedResponse_DevisResponse_: {
            /** Items */
            items: components["schemas"]["DevisResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[dict] */
        PaginatedResponse_dict_: {
            /** Items */
            items: {
                [key: string]: unknown;
            }[];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[FacturePlateformeResponse] */
        PaginatedResponse_FacturePlateformeResponse_: {
            /** Items */
            items: components["schemas"]["FacturePlateformeResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[FactureResponse] */
        PaginatedResponse_FactureResponse_: {
            /** Items */
            items: components["schemas"]["FactureResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[FournisseurResponse] */
        PaginatedResponse_FournisseurResponse_: {
            /** Items */
            items: components["schemas"]["FournisseurResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[MouvementStockResponse] */
        PaginatedResponse_MouvementStockResponse_: {
            /** Items */
            items: components["schemas"]["MouvementStockResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[OrdonnanceResponse] */
        PaginatedResponse_OrdonnanceResponse_: {
            /** Items */
            items: components["schemas"]["OrdonnanceResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[PaiementCaisseResponse] */
        PaginatedResponse_PaiementCaisseResponse_: {
            /** Items */
            items: components["schemas"]["PaiementCaisseResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[PatientResponse] */
        PaginatedResponse_PatientResponse_: {
            /** Items */
            items: components["schemas"]["PatientResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[RendezVousResponse] */
        PaginatedResponse_RendezVousResponse_: {
            /** Items */
            items: components["schemas"]["RendezVousResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[SessionCaisseResponse] */
        PaginatedResponse_SessionCaisseResponse_: {
            /** Items */
            items: components["schemas"]["SessionCaisseResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[SessionUtilisateurResponse] */
        PaginatedResponse_SessionUtilisateurResponse_: {
            /** Items */
            items: components["schemas"]["SessionUtilisateurResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[TenantResponse] */
        PaginatedResponse_TenantResponse_: {
            /** Items */
            items: components["schemas"]["TenantResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[UtilisateurPlateformeResponse] */
        PaginatedResponse_UtilisateurPlateformeResponse_: {
            /** Items */
            items: components["schemas"]["UtilisateurPlateformeResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginatedResponse[UtilisateurResponse] */
        PaginatedResponse_UtilisateurResponse_: {
            /** Items */
            items: components["schemas"]["UtilisateurResponse"][];
            meta: components["schemas"]["PaginationMeta"];
            /**
             * Success
             * @default true
             */
            success: boolean;
        };
        /** PaginationMeta */
        PaginationMeta: {
            /** Has Next */
            has_next: boolean;
            /** Has Previous */
            has_previous: boolean;
            /** Limit */
            limit: number;
            /** Page */
            page: number;
            /** Total Pages */
            total_pages: number;
            /** Total Records */
            total_records: number;
        };
        /** PaiementCaisseResponse */
        PaiementCaisseResponse: {
            /** Auteur */
            auteur?: string | null;
            /**
             * Date Paiement
             * Format: date-time
             */
            date_paiement: string;
            /**
             * Facture Id
             * Format: uuid
             */
            facture_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            mode: components["schemas"]["ModePaiementEnum"];
            /** Montant */
            montant: string;
            /** Recu Numero */
            recu_numero: string;
            /** Reference */
            reference?: string | null;
        };
        /**
         * PaiementCreate
         * @description Encaissement d'une facture. `echeance_id` cible une échéance d'un plan (RG08).
         */
        PaiementCreate: {
            /**
             * Echeance Id
             * @description Si fourni : le paiement règle l'échéance indiquée. Le montant doit correspondre exactement au reste dû sur cette échéance.
             */
            echeance_id?: string | null;
            mode: components["schemas"]["ModePaiementEnum"];
            /**
             * Montant
             * @description Montant encaissé en FCFA
             */
            montant: number | string;
            /**
             * Reference
             * @description Référence transaction (Wave, Orange Money, chèque...)
             */
            reference?: string | null;
        };
        /** PaiementResponse */
        PaiementResponse: {
            /**
             * Date Paiement
             * Format: date-time
             */
            date_paiement: string;
            /** Echeance Id */
            echeance_id?: string | null;
            /**
             * Facture Id
             * Format: uuid
             */
            facture_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            mode: components["schemas"]["ModePaiementEnum"];
            /** Montant */
            montant: string;
            /** Recu Numero */
            recu_numero: string;
            /** Reference */
            reference?: string | null;
        };
        /** PatientArchive */
        PatientArchive: {
            /**
             * Motif
             * @description Motif de l'archivage (conservé dans l'audit médico-légal).
             */
            motif?: string | null;
        };
        /**
         * PatientCreate
         * @description Création d'un dossier patient (Étape 1 du workflow CDC).
         *
         *     Le `numero_dossier` n'est pas fourni : il est généré par le service (RG01).
         *     Les antécédents peuvent être créés dans le même appel que l'identité.
         */
        PatientCreate: {
            /** Adresse */
            adresse?: string | null;
            /**
             * Antecedents
             * @description Antécédents médicaux (Étape 3 du CDC).
             */
            antecedents?: components["schemas"]["AntecedentMedicalCreate"][] | null;
            /**
             * Date Naissance
             * Format: date
             * @description Date de naissance (RG : search par date naissance)
             */
            date_naissance: string;
            /** Email */
            email?: string | null;
            /** Employeur */
            employeur?: string | null;
            /** @description État général (Étape 2 du CDC). Créé avec le dossier si fourni. */
            etat_general?: components["schemas"]["EtatGeneralCreate"] | null;
            /** Groupe Sanguin */
            groupe_sanguin?: string | null;
            /** Nom */
            nom: string;
            /** Notes */
            notes?: string | null;
            /** Numero Piece Identite */
            numero_piece_identite?: string | null;
            /** Prenom */
            prenom: string;
            /** Profession */
            profession?: string | null;
            /** @default F */
            sexe: components["schemas"]["SexeEnum"];
            /**
             * Source
             * @description Recommandation, Réseaux, Passage...
             */
            source?: string | null;
            /**
             * Telephone 1
             * @description Téléphone principal (recherche patient)
             */
            telephone_1: string;
            /** Telephone 2 */
            telephone_2?: string | null;
            type_piece_identite?: components["schemas"]["TypePieceIdentiteEnum"] | null;
            /**
             * Ville
             * @default Dakar
             */
            ville: string | null;
        };
        /**
         * PatientDossierCompletResponse
         * @description Fiche patient complète : identité + état général + antécédents + alertes.
         */
        PatientDossierCompletResponse: {
            /** Actif */
            actif: boolean;
            /** Adresse */
            adresse?: string | null;
            /**
             * Alertes
             * @default []
             */
            alertes: components["schemas"]["AlerteMedicale"][];
            /**
             * Antecedents
             * @default []
             */
            antecedents: components["schemas"]["AntecedentMedicalResponse"][];
            /** Archive */
            archive: boolean;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Date Naissance
             * Format: date
             */
            date_naissance: string;
            /** Derniere Consultation */
            derniere_consultation?: string | null;
            /**
             * Dossier Medical Id
             * Format: uuid
             */
            dossier_medical_id: string;
            /** Email */
            email?: string | null;
            /** Employeur */
            employeur?: string | null;
            etat_general?: components["schemas"]["EtatGeneralResponse"] | null;
            /** Groupe Sanguin */
            groupe_sanguin?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Nb Consultations
             * @default 0
             */
            nb_consultations: number;
            /** Nom */
            nom: string;
            /** Notes */
            notes?: string | null;
            /** Numero Dossier */
            numero_dossier: string;
            /** Numero Piece Identite */
            numero_piece_identite?: string | null;
            /** Photo Url */
            photo_url?: string | null;
            /** Prenom */
            prenom: string;
            /** Profession */
            profession?: string | null;
            sexe: components["schemas"]["SexeEnum"];
            /** Source */
            source?: string | null;
            /** Telephone 1 */
            telephone_1: string;
            /** Telephone 2 */
            telephone_2?: string | null;
            type_piece_identite?: components["schemas"]["TypePieceIdentiteEnum"] | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Ville */
            ville?: string | null;
        };
        /** PatientResponse */
        PatientResponse: {
            /** Actif */
            actif: boolean;
            /** Adresse */
            adresse?: string | null;
            /** Archive */
            archive: boolean;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Date Naissance
             * Format: date
             */
            date_naissance: string;
            /** Email */
            email?: string | null;
            /** Employeur */
            employeur?: string | null;
            /** Groupe Sanguin */
            groupe_sanguin?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nom */
            nom: string;
            /** Notes */
            notes?: string | null;
            /** Numero Dossier */
            numero_dossier: string;
            /** Numero Piece Identite */
            numero_piece_identite?: string | null;
            /** Photo Url */
            photo_url?: string | null;
            /** Prenom */
            prenom: string;
            /** Profession */
            profession?: string | null;
            sexe: components["schemas"]["SexeEnum"];
            /** Source */
            source?: string | null;
            /** Telephone 1 */
            telephone_1: string;
            /** Telephone 2 */
            telephone_2?: string | null;
            type_piece_identite?: components["schemas"]["TypePieceIdentiteEnum"] | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Ville */
            ville?: string | null;
        };
        /**
         * PatientUpdate
         * @description Mise à jour administrative. Les champs non transmis restent inchangés.
         */
        PatientUpdate: {
            /** Adresse */
            adresse?: string | null;
            /** Date Naissance */
            date_naissance?: string | null;
            /** Email */
            email?: string | null;
            /** Employeur */
            employeur?: string | null;
            /** Groupe Sanguin */
            groupe_sanguin?: string | null;
            /** Nom */
            nom?: string | null;
            /** Notes */
            notes?: string | null;
            /** Numero Piece Identite */
            numero_piece_identite?: string | null;
            /** Prenom */
            prenom?: string | null;
            /** Profession */
            profession?: string | null;
            sexe?: components["schemas"]["SexeEnum"] | null;
            /** Source */
            source?: string | null;
            /** Telephone 1 */
            telephone_1?: string | null;
            /** Telephone 2 */
            telephone_2?: string | null;
            type_piece_identite?: components["schemas"]["TypePieceIdentiteEnum"] | null;
            /** Ville */
            ville?: string | null;
        };
        /** PermissionGrant */
        PermissionGrant: {
            /**
             * Action
             * @description READ, CREATE, UPDATE, DELETE, EXPORT, SIGN
             */
            action: string;
            /**
             * Module
             * @description Module (PATIENTS, CONSULTATIONS...)
             */
            module: string;
        };
        /** PermissionPlateformeResponse */
        PermissionPlateformeResponse: {
            /** Action */
            action: string;
            /** Code */
            code: string;
            /** Description */
            description: string;
            /** Ressource */
            ressource: string;
            /** Sensible */
            sensible: boolean;
        };
        /** PlanCreate */
        PlanCreate: {
            /**
             * Code
             * @description Code unique, normalisé en majuscules
             */
            code: string;
            /** Description */
            description?: string | null;
            /**
             * Devise
             * @default XOF
             */
            devise: string;
            /**
             * Features
             * @description {'stock': true, 'sms': true, 'rapports': true}
             */
            features?: {
                [key: string]: unknown;
            };
            /**
             * Jours Essai
             * @default 14
             */
            jours_essai: number;
            /** Nom */
            nom: string;
            /**
             * Periodicite
             * @description MENSUEL | ANNUEL | GRATUIT
             * @default MENSUEL
             */
            periodicite: string;
            /**
             * Plan Defaut
             * @default false
             */
            plan_defaut: boolean;
            /**
             * Prix
             * @description Prix HT par période
             */
            prix: number;
            /**
             * Quotas
             * @description {'utilisateurs': 5, 'sites': 1, 'praticiens': 2, 'stockage_octets': 1073741824, 'sms_par_mois': 200}
             */
            quotas?: {
                [key: string]: unknown;
            };
        };
        /**
         * PlanEchelonnementCreate
         * @description RG08 : les échéances sont générées par le service, jamais envoyées par le client.
         */
        PlanEchelonnementCreate: {
            /**
             * Date Debut
             * Format: date
             * @description Date de la première échéance
             */
            date_debut: string;
            /** @default MENSUEL */
            frequence: components["schemas"]["FrequenceEchelonnementEnum"];
            /**
             * Nombre Echeances
             * @description Nombre de versements (2 à 36)
             */
            nombre_echeances: number;
            /** Notes */
            notes?: string | null;
        };
        /** PlanEchelonnementResponse */
        PlanEchelonnementResponse: {
            /** Actif */
            actif: boolean;
            /**
             * Date Debut
             * Format: date
             */
            date_debut: string;
            /**
             * Echeances
             * @default []
             */
            echeances: components["schemas"]["EcheanceResponse"][];
            /**
             * Facture Id
             * Format: uuid
             */
            facture_id: string;
            frequence: components["schemas"]["FrequenceEchelonnementEnum"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Montant Total */
            montant_total: string;
            /** Nombre Echeances */
            nombre_echeances: number;
            /** Notes */
            notes?: string | null;
        };
        /** PlanResponse */
        PlanResponse: {
            /** Actif */
            actif: boolean;
            /** Code */
            code: string;
            /** Description */
            description?: string | null;
            /** Devise */
            devise: string;
            /** Features */
            features: {
                [key: string]: unknown;
            };
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Jours Essai */
            jours_essai: number;
            /** Nom */
            nom: string;
            /** Periodicite */
            periodicite: string;
            /** Plan Defaut */
            plan_defaut: boolean;
            /** Prix */
            prix: string;
            /** Quotas */
            quotas: {
                [key: string]: unknown;
            };
            /** Version */
            version: number;
        };
        /** PlanRevisionResponse */
        PlanRevisionResponse: {
            /** Auteur */
            auteur: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Instantane */
            instantane: {
                [key: string]: unknown;
            };
            /** Motif */
            motif?: string | null;
            /** Version */
            version: number;
        };
        /** PlanUpdate */
        PlanUpdate: {
            /** Actif */
            actif?: boolean | null;
            /** Description */
            description?: string | null;
            /** Devise */
            devise?: string | null;
            /** Features */
            features?: {
                [key: string]: unknown;
            } | null;
            /** Jours Essai */
            jours_essai?: number | null;
            /** Motif */
            motif?: string | null;
            /** Nom */
            nom?: string | null;
            /** Periodicite */
            periodicite?: string | null;
            /** Prix */
            prix?: number | null;
            /** Quotas */
            quotas?: {
                [key: string]: unknown;
            } | null;
        };
        /** PlatformLoginRequest */
        PlatformLoginRequest: {
            /**
             * Email
             * Format: email
             * @description Adresse e-mail du compte de la console
             */
            email: string;
            /** Mot De Passe */
            mot_de_passe: string;
        };
        /** PlatformProfilResponse */
        PlatformProfilResponse: {
            /**
             * Codes Secours A Regenerer
             * @default false
             */
            codes_secours_a_regenerer: boolean;
            /**
             * Cree Le
             * Format: date-time
             */
            cree_le: string;
            /** Dernier Login */
            dernier_login?: string | null;
            /** Deux Facteurs Actif */
            deux_facteurs_actif: boolean;
            /**
             * Email
             * Format: email
             */
            email: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nom */
            nom: string;
            /** Permissions */
            permissions: string[];
            /** Prenom */
            prenom: string;
            /** Roles */
            roles: string[];
            /** Statut */
            statut: string;
            /** Telephone */
            telephone?: string | null;
        };
        /** PlatformRefreshRequest */
        PlatformRefreshRequest: {
            /**
             * Refresh Token
             * @description Refresh token de la session courante
             */
            refresh_token: string;
        };
        /** PlatformTokenResponse */
        PlatformTokenResponse: {
            /** Access Token */
            access_token: string;
            /**
             * Expires In
             * @description Durée de validité de l'access token, en secondes
             */
            expires_in: number;
            /**
             * Refresh Expires In
             * @description Durée de validité du refresh token, en secondes
             */
            refresh_expires_in: number;
            /** Refresh Token */
            refresh_token: string;
            /**
             * Token Type
             * @default bearer
             */
            token_type: string;
        };
        /**
         * PraticienCreate
         * @description Rattachement d'un compte utilisateur au métier de praticien.
         *
         *     Le compte doit exister au préalable : un praticien est toujours un
         *     utilisateur authentifié, jamais une identité sans accès. C'est ce qui rend
         *     l'attribution d'une ordonnance ou d'une consultation traçable jusqu'à une
         *     personne physique.
         */
        PraticienCreate: {
            /** Bio */
            bio?: string | null;
            /**
             * Cabinet Id
             * @description Site de rattachement initial. Facultatif.
             */
            cabinet_id?: string | null;
            /**
             * Numero Ordre
             * @description Numéro d'inscription à l'ordre professionnel.
             */
            numero_ordre?: string | null;
            /** Signature Url */
            signature_url?: string | null;
            /**
             * Specialite
             * @default Chirurgien-Dentiste
             */
            specialite: string;
            /**
             * Titre
             * @default Dr
             */
            titre: string;
            /**
             * Utilisateur Id
             * Format: uuid
             */
            utilisateur_id: string;
        };
        /** PraticienResponse */
        PraticienResponse: {
            /** Bio */
            bio?: string | null;
            /**
             * Cabinets
             * @default []
             */
            cabinets: string[];
            /**
             * Compte Actif
             * @default true
             */
            compte_actif: boolean;
            /** Email */
            email?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Nb Disponibilites
             * @default 0
             */
            nb_disponibilites: number;
            /** Nom */
            nom?: string | null;
            /** Numero Ordre */
            numero_ordre?: string | null;
            /** Prenom */
            prenom?: string | null;
            /** Signature Url */
            signature_url?: string | null;
            /** Specialite */
            specialite: string;
            /** Titre */
            titre: string;
            /**
             * Utilisateur Id
             * Format: uuid
             */
            utilisateur_id: string;
        };
        /** PraticienUpdate */
        PraticienUpdate: {
            /** Bio */
            bio?: string | null;
            /** Numero Ordre */
            numero_ordre?: string | null;
            /** Signature Url */
            signature_url?: string | null;
            /** Specialite */
            specialite?: string | null;
            /** Titre */
            titre?: string | null;
        };
        /** QuotaResumeResponse */
        QuotaResumeResponse: {
            /**
             * Illimite
             * @default true
             */
            illimite: boolean;
            /** Plan */
            plan?: string | null;
            /** Plan Nom */
            plan_nom?: string | null;
            /** Releve Jour */
            releve_jour?: string | null;
            /**
             * Ressources
             * @default []
             */
            ressources: {
                [key: string]: unknown;
            }[];
        };
        /**
         * RattachementCreate
         * @description Rattachement d'un praticien à un site, sur une période.
         */
        RattachementCreate: {
            /** Date Debut */
            date_debut?: string | null;
            /** Date Fin */
            date_fin?: string | null;
        };
        /** RattachementResponse */
        RattachementResponse: {
            /** Actif */
            actif: boolean;
            /**
             * Cabinet Id
             * Format: uuid
             */
            cabinet_id: string;
            /** Cabinet Nom */
            cabinet_nom?: string | null;
            /**
             * Date Debut
             * Format: date
             */
            date_debut: string;
            /** Date Fin */
            date_fin?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Praticien Id
             * Format: uuid
             */
            praticien_id: string;
        };
        /** ReceptionCreate */
        ReceptionCreate: {
            /** Lignes */
            lignes: components["schemas"]["LigneReceptionCreate"][];
            /** Notes */
            notes?: string | null;
        };
        /** ReceptionResponse */
        ReceptionResponse: {
            /** Auteur */
            auteur?: string | null;
            /**
             * Commande Id
             * Format: uuid
             */
            commande_id: string;
            /**
             * Date Reception
             * Format: date
             */
            date_reception: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Lignes
             * @default []
             */
            lignes: components["schemas"]["LigneReceptionResponse"][];
            /** Notes */
            notes?: string | null;
            /** Numero */
            numero: string;
        };
        /**
         * ReferentielJoursResponse
         * @description Jours de la semaine et types de plage, pour peupler un formulaire.
         *
         *     Contrat explicite plutôt que de laisser le frontend deviner la convention
         *     (0 = lundi ?) et les libellés français.
         */
        ReferentielJoursResponse: {
            /** Duree Creneau Minutes */
            duree_creneau_minutes: number;
            /** Jours */
            jours: {
                [key: string]: unknown;
            }[];
            /** Types Plage */
            types_plage: {
                [key: string]: unknown;
            }[];
        };
        /** RefreshTokenRequest */
        RefreshTokenRequest: {
            /** Refresh Token */
            refresh_token: string;
        };
        /**
         * RegenererCodesSecoursRequest
         * @description Régénération des codes de secours : session + TOTP actif + motif obligatoire.
         */
        RegenererCodesSecoursRequest: {
            /**
             * Code
             * @description Code TOTP courant de l'application d'authentification (secret ACTIF)
             */
            code: string;
            /**
             * Motif
             * @description Motif de la régénération, consigné au journal d'audit
             */
            motif: string;
        };
        /**
         * RegenererCodesSecoursResponse
         * @description Les dix nouveaux codes, renvoyés **une seule fois** — jamais stockés en clair.
         */
        RegenererCodesSecoursResponse: {
            /** Codes Secours */
            codes_secours: string[];
        };
        /**
         * RegleContreIndication
         * @description Règle déclarée sur un médicament du référentiel.
         */
        RegleContreIndication: {
            /**
             * Condition
             * @description Condition clinique code (GROSSESSE, ALLERGIE_PENICILLINE...)
             */
            condition: string;
            /**
             * Gravite
             * @description INTERDIT (bloque) ou PRECAUTION (justification requise)
             * @default INTERDIT
             */
            gravite: string;
            /**
             * Message
             * @description Message destiné au praticien
             */
            message: string;
        };
        /** ReinitialisationAccesRequest */
        ReinitialisationAccesRequest: {
            /** Motif */
            motif: string;
        };
        /**
         * RendezVousCreate
         * @description Prise de rendez-vous (UC9 « Prendre rendez-vous »).
         *
         *     Le praticien est désigné par identifiant, jamais « le premier trouvé » :
         *     un cabinet multi-praticien doit savoir de qui il s'agit.
         */
        RendezVousCreate: {
            /**
             * Cabinet Id
             * @description Site concerné. Absent = le site de rattachement du praticien.
             */
            cabinet_id?: string | null;
            /**
             * Debut
             * Format: date-time
             */
            debut: string;
            /**
             * Duree Minutes
             * @description Valeurs usuelles : (15, 20, 30, 45, 60, 90, 120). Toute durée ≥ 5 est acceptée.
             * @default 30
             */
            duree_minutes: number;
            /**
             * Fauteuil Id
             * @description Fauteuil réservé. Absent = rendez-vous sans fauteuil (visite d'évaluation, urgences).
             */
            fauteuil_id?: string | null;
            /** Motif */
            motif: string;
            /** Notes */
            notes?: string | null;
            /**
             * Patient Id
             * Format: uuid
             */
            patient_id: string;
            /**
             * Praticien Id
             * Format: uuid
             */
            praticien_id: string;
            /**
             * Statut
             * @description Permet de créer directement en CONFIRME.
             * @default PLANIFIE
             */
            statut: string;
            /**
             * Type Motif
             * @default AUTRE
             */
            type_motif: string;
        };
        /** RendezVousResponse */
        RendezVousResponse: {
            /**
             * Cabinet Id
             * Format: uuid
             */
            cabinet_id: string;
            /** Cabinet Nom */
            cabinet_nom?: string | null;
            /** Consultation Id */
            consultation_id?: string | null;
            /**
             * Date Statut
             * Format: date-time
             */
            date_statut: string;
            /**
             * Debut
             * Format: date-time
             */
            debut: string;
            /** Duree Minutes */
            duree_minutes: number;
            /** Fauteuil Id */
            fauteuil_id?: string | null;
            /** Fauteuil Numero */
            fauteuil_numero?: string | null;
            /**
             * Fin
             * Format: date-time
             */
            fin: string;
            /**
             * Hors Disponibilites
             * @default false
             */
            hors_disponibilites: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Motif */
            motif: string;
            /** Motif Annulation */
            motif_annulation?: string | null;
            /** Notes */
            notes?: string | null;
            /** Numero Dossier */
            numero_dossier?: string | null;
            /**
             * Patient Id
             * Format: uuid
             */
            patient_id: string;
            /** Patient Nom */
            patient_nom?: string | null;
            /** Patient Prenom */
            patient_prenom?: string | null;
            /** Patient Telephone */
            patient_telephone?: string | null;
            /**
             * Praticien Id
             * Format: uuid
             */
            praticien_id: string;
            /** Praticien Nom */
            praticien_nom?: string | null;
            /** Praticien Titre */
            praticien_titre?: string | null;
            /** Statut */
            statut: string;
            /** Statut Libelle */
            statut_libelle: string;
            /**
             * Transitions Possibles
             * @default []
             */
            transitions_possibles: string[];
            /** Type Motif */
            type_motif: string;
        };
        /**
         * RendezVousUpdate
         * @description Modifications permises tant que le rendez-vous n'a pas commencé.
         */
        RendezVousUpdate: {
            /** Fauteuil Id */
            fauteuil_id?: string | null;
            /** Motif */
            motif?: string | null;
            /** Motif Annulation */
            motif_annulation?: string | null;
            /** Notes */
            notes?: string | null;
            /** Type Motif */
            type_motif?: string | null;
        };
        /** RoleCreate */
        RoleCreate: {
            /** Description */
            description?: string | null;
            /**
             * Niveau Hierarchie
             * @description 1 = plus élevé (ADMIN_CABINET)
             * @default 3
             */
            niveau_hierarchie: number;
            /**
             * Nom
             * @description Nom unique du rôle (ex: SECRETAIRE_NUIT)
             */
            nom: string;
        };
        /** RolePlateformeResponse */
        RolePlateformeResponse: {
            /** Code */
            code: string;
            /** Description */
            description?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Libelle */
            libelle: string;
            /** Nb Utilisateurs */
            nb_utilisateurs: number;
            /** Niveau Hierarchie */
            niveau_hierarchie: number;
            /** Permissions */
            permissions: string[];
            /** Systeme */
            systeme: boolean;
        };
        /** RoleResponse */
        RoleResponse: {
            /** Description */
            description?: string | null;
            /** Id */
            id: string;
            /**
             * Nb Utilisateurs
             * @default 0
             */
            nb_utilisateurs: number;
            /** Niveau Hierarchie */
            niveau_hierarchie: number;
            /** Nom */
            nom: string;
            /**
             * Permissions
             * @default []
             */
            permissions: string[];
        };
        /** SalleCreate */
        SalleCreate: {
            /** Etage */
            etage?: string | null;
            /**
             * Nom
             * @description Ex: Salle 1, Bloc opératoire
             */
            nom: string;
        };
        /** SalleResponse */
        SalleResponse: {
            /**
             * Cabinet Id
             * Format: uuid
             */
            cabinet_id: string;
            /** Etage */
            etage?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Nb Fauteuils
             * @default 0
             */
            nb_fauteuils: number;
            /**
             * Nb Fauteuils Actifs
             * @default 0
             */
            nb_fauteuils_actifs: number;
            /** Nom */
            nom: string;
        };
        /** SalleUpdate */
        SalleUpdate: {
            /** Etage */
            etage?: string | null;
            /** Nom */
            nom?: string | null;
        };
        /** SessionCaisseResponse */
        SessionCaisseResponse: {
            /**
             * Cabinet Id
             * Format: uuid
             */
            cabinet_id: string;
            /** Close Le */
            close_le?: string | null;
            /** Close Par */
            close_par?: string | null;
            /** Ecart Especes */
            ecart_especes?: string | null;
            /** Especes Attendues */
            especes_attendues: string;
            /** Especes Comptees */
            especes_comptees?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Motif Ecart */
            motif_ecart?: string | null;
            /** Nb Paiements */
            nb_paiements: number;
            /** Notes */
            notes?: string | null;
            /** Numero */
            numero: string;
            /**
             * Ouverte Le
             * Format: date-time
             */
            ouverte_le: string;
            /** Ouverte Par */
            ouverte_par?: string | null;
            /** Ouverture Especes */
            ouverture_especes: string;
            statut: components["schemas"]["StatutSessionCaisseEnum"];
            /** Total Assurance */
            total_assurance: string;
            /** Total Carte */
            total_carte: string;
            /** Total Cheque */
            total_cheque: string;
            /** Total Encaisse */
            total_encaisse: string;
            /** Total Especes */
            total_especes: string;
            /** Total Mobile Money */
            total_mobile_money: string;
            /** Total Virement */
            total_virement: string;
        };
        /** SessionUtilisateurResponse */
        SessionUtilisateurResponse: {
            /**
             * Derniere Activite
             * Format: date-time
             */
            derniere_activite: string;
            /** Est Revoque */
            est_revoque: boolean;
            /**
             * Expire At
             * Format: date-time
             */
            expire_at: string;
            /** Expiree */
            expiree: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Ip Address */
            ip_address?: string | null;
            /** User Agent */
            user_agent?: string | null;
        };
        /**
         * SexeEnum
         * @enum {string}
         */
        SexeEnum: "M" | "F" | "AUTRE";
        /**
         * SiteSondage
         * @description Mesure en un point du sondage parodontal (6 points par dent).
         */
        SiteSondage: {
            /**
             * Profondeur
             * @description Profondeur en millimètres
             */
            profondeur: number;
            /**
             * Site
             * @description Site : MV | V | DV | ML | L | DL
             */
            site: string;
        };
        /** SocieteCreate */
        SocieteCreate: {
            /**
             * Admin Email
             * Format: email
             * @description Email de l'administrateur du cabinet
             */
            admin_email: string;
            /** Admin Nom */
            admin_nom: string;
            /**
             * Admin Password
             * @description Mot de passe initial
             */
            admin_password: string;
            /** Admin Prenom */
            admin_prenom: string;
            /** Adresse Siege */
            adresse_siege?: string | null;
            /** Email */
            email?: string | null;
            /** Logo Url */
            logo_url?: string | null;
            /**
             * Ninea
             * @description Numéro NINEA ou Registre de commerce
             */
            ninea?: string | null;
            /**
             * Nom
             * @description Nom commercial ou raison sociale
             */
            nom: string;
            /**
             * Pays
             * @default Sénégal
             */
            pays: string | null;
            /** Site Web */
            site_web?: string | null;
            /** Telephone */
            telephone?: string | null;
            /**
             * Ville
             * @default Dakar
             */
            ville: string | null;
        };
        /** SocieteResponse */
        SocieteResponse: {
            /** Actif */
            actif: boolean;
            /** Adresse Siege */
            adresse_siege?: string | null;
            /**
             * Date Creation
             * Format: date-time
             */
            date_creation: string;
            /** Email */
            email?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Logo Url */
            logo_url?: string | null;
            /** Ninea */
            ninea?: string | null;
            /** Nom */
            nom: string;
            /** Pays */
            pays: string;
            /** Site Web */
            site_web?: string | null;
            /** Telephone */
            telephone?: string | null;
            tenant_db?: components["schemas"]["TenantDBResponse"] | null;
            /** Ville */
            ville?: string | null;
        };
        /** SocieteStatutUpdate */
        SocieteStatutUpdate: {
            /**
             * Actif
             * @description true pour réactiver, false pour suspendre l'accès du cabinet
             */
            actif: boolean;
        };
        /** SocieteUpdate */
        SocieteUpdate: {
            /** Actif */
            actif?: boolean | null;
            /** Adresse Siege */
            adresse_siege?: string | null;
            /** Email */
            email?: string | null;
            /** Logo Url */
            logo_url?: string | null;
            /** Ninea */
            ninea?: string | null;
            /** Nom */
            nom?: string | null;
            /** Pays */
            pays?: string | null;
            /** Site Web */
            site_web?: string | null;
            /** Telephone */
            telephone?: string | null;
            /** Ville */
            ville?: string | null;
        };
        /** StatsGlobalesResponse */
        StatsGlobalesResponse: {
            /**
             * Croissance Mensuelle
             * @default []
             */
            croissance_mensuelle: {
                [key: string]: unknown;
            }[];
            /**
             * Inactifs 30J
             * @default []
             */
            inactifs_30j: {
                [key: string]: unknown;
            }[];
            /**
             * Par Formule
             * @default {}
             */
            par_formule: {
                [key: string]: number;
            };
            /**
             * Par Statut
             * @default {}
             */
            par_statut: {
                [key: string]: number;
            };
            /**
             * Proches Du Quota
             * @default []
             */
            proches_du_quota: {
                [key: string]: unknown;
            }[];
            /**
             * Total Cabinets
             * @default 0
             */
            total_cabinets: number;
        };
        /** StatsTenantResponse */
        StatsTenantResponse: {
            /** Releve */
            releve?: {
                [key: string]: unknown;
            } | null;
            /**
             * Serie
             * @default []
             */
            serie: {
                [key: string]: unknown;
            }[];
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
        };
        /**
         * StatutCommandeEnum
         * @description Cycle de vie d'un bon de commande fournisseur.
         *
         *     `PARTIELLEMENT_REÇUE` est un état calculé, pas saisi : il existe dès qu'au
         *     moins une ligne a été livrée sans que la commande soit soldée. Le stocks
         *     n'est crédité qu'à la réception, jamais à l'envoi — émettre une commande
         *     n'ajoute pas de matière au cabinet.
         * @enum {string}
         */
        StatutCommandeEnum: "BROUILLON" | "ENVOYEE" | "PARTIELLEMENT_REÇUE" | "RECUE" | "ANNULEE";
        /** StatutCommandeUpdate */
        StatutCommandeUpdate: {
            statut: components["schemas"]["StatutCommandeEnum"];
        };
        /**
         * StatutConsultationEnum
         * @enum {string}
         */
        StatutConsultationEnum: "PLANIFIEE" | "EN_ATTENTE" | "EN_COURS" | "TERMINEE" | "ANNULEE";
        /**
         * StatutDevisEnum
         * @description Cycle de vie d'un devis (CDC : brouillon, envoyé, accepté, refusé, expiré).
         * @enum {string}
         */
        StatutDevisEnum: "BROUILLON" | "ENVOYE" | "ACCEPTE" | "REFUSE" | "EXPIRE";
        /**
         * StatutEcheanceEnum
         * @description Vie d'une échéance. `EN_RETARD` est posé par le job de relance (RG09).
         * @enum {string}
         */
        StatutEcheanceEnum: "A_PAYER" | "PAYEE" | "EN_RETARD" | "ANNULEE";
        /**
         * StatutFactureEnum
         * @enum {string}
         */
        StatutFactureEnum: "BROUILLON" | "EMISE" | "PARTIELLEMENT_PAYEE" | "PAYEE" | "ANNULEE";
        /**
         * StatutRendezVousResponse
         * @description Rappel du cycle de vie, pour l'UI (évite de le redéfinir côté client).
         */
        StatutRendezVousResponse: {
            /** Duree Par Defaut Minutes */
            duree_par_defaut_minutes: number;
            /** Durees Possibles */
            durees_possibles: number[];
            /** Motifs Blocage */
            motifs_blocage: {
                [key: string]: unknown;
            }[];
            /** Statuts */
            statuts: {
                [key: string]: unknown;
            }[];
            /** Transitions */
            transitions: {
                [key: string]: string[];
            };
        };
        /**
         * StatutSessionCaisseEnum
         * @description Cycle de vie d'une session de caisse.
         * @enum {string}
         */
        StatutSessionCaisseEnum: "OUVERTE" | "CLOSE";
        /** SuperAdminLogin */
        SuperAdminLogin: {
            /**
             * Email
             * Format: email
             */
            email: string;
            /** Password */
            password: string;
        };
        /** SuperAdminResponse */
        SuperAdminResponse: {
            /** Actif */
            actif: boolean;
            /** Dernier Login */
            dernier_login?: string | null;
            /**
             * Email
             * Format: email
             */
            email: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nom Complet */
            nom_complet: string;
        };
        /**
         * SupportTokenResponse
         * @description Jeton d'accès support. À traiter comme un secret : il n'est pas renewable.
         */
        SupportTokenResponse: {
            /**
             * Administrateur Notifie
             * @default false
             */
            administrateur_notifie: boolean;
            /** Duree Minutes */
            duree_minutes: number;
            /**
             * Expire Le
             * Format: date-time
             */
            expire_le: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Jeton */
            jeton: string;
            /** Lecture Seule */
            lecture_seule: boolean;
        };
        /** SuppressionRequest */
        SuppressionRequest: {
            /**
             * Confirmation
             * @description Doit valoir exactement 'SUPPRIMER' : double confirmation explicite
             */
            confirmation: string;
            /**
             * Motif
             * @description Motif obligatoire (journalisé)
             */
            motif: string;
        };
        /**
         * TenantCreate
         * @description Création et provisionnement complets d'un cabinet (Phase B.4).
         */
        TenantCreate: {
            /**
             * Admin Email
             * Format: email
             * @description E-mail du premier administrateur
             */
            admin_email: string;
            /** Admin Nom */
            admin_nom: string;
            /** Admin Prenom */
            admin_prenom: string;
            /** Adresse Siege */
            adresse_siege?: string | null;
            /**
             * Devise
             * @default XOF
             */
            devise: string;
            /**
             * Fuseau Horaire
             * @default Africa/Dakar
             */
            fuseau_horaire: string;
            /**
             * Jours Essai
             * @description Durée d'essai si ESSAI
             * @default 14
             */
            jours_essai: number;
            /**
             * Langue
             * @default fr
             */
            langue: string;
            /** Logo Url */
            logo_url?: string | null;
            /** Motif */
            motif?: string | null;
            /**
             * Ninea
             * @description Numéro d'enregistrement (unique)
             */
            ninea?: string | null;
            /**
             * Nom
             * @description Nom commercial du cabinet
             */
            nom: string;
            /**
             * Pays
             * @default Sénégal
             */
            pays: string | null;
            /**
             * Plan Code
             * @description Plan souscrit ; absent = plan par défaut
             */
            plan_code?: string | null;
            /** Site Web */
            site_web?: string | null;
            /**
             * Statut Initial
             * @description ESSAI pour un cabinet en période d'essai, ACTIF sinon
             * @default ACTIF
             */
            statut_initial: string;
            /** Telephone */
            telephone?: string | null;
            /**
             * Ville
             * @default Dakar
             */
            ville: string | null;
        };
        /** TenantCreationResponse */
        TenantCreationResponse: {
            /**
             * Etapes
             * @description Étapes réellement accomplies
             */
            etapes: string[];
            /**
             * Gabarits Appliques
             * @description Gabarits utilisés et leur version
             */
            gabarits_appliques?: {
                [key: string]: unknown;
            };
            /** Invitation Admin Envoyee */
            invitation_admin_envoyee: boolean;
            tenant: components["schemas"]["TenantResponse"];
        };
        /** TenantDBResponse */
        TenantDBResponse: {
            /** Db Host */
            db_host: string;
            /** Db Name */
            db_name: string;
            /** Db Port */
            db_port: number;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Schema Version */
            schema_version: string;
            /** Statut */
            statut: string;
        };
        /** TenantDetailResponse */
        TenantDetailResponse: {
            /** Abonnement */
            abonnement?: {
                [key: string]: unknown;
            } | null;
            /** Adresse Siege */
            adresse_siege?: string | null;
            /**
             * Archivable
             * @default false
             */
            archivable: boolean;
            /** Date Creation */
            date_creation?: string | null;
            /** Date Debut Essai */
            date_debut_essai?: string | null;
            /** Date Fin Essai */
            date_fin_essai?: string | null;
            /** Db Name */
            db_name?: string | null;
            /**
             * Devise
             * @default XOF
             */
            devise: string;
            /** Email */
            email?: string | null;
            /**
             * Fuseau Horaire
             * @default Africa/Dakar
             */
            fuseau_horaire: string;
            /**
             * Langue
             * @default fr
             */
            langue: string;
            /** Logo Url */
            logo_url?: string | null;
            /** Ninea */
            ninea?: string | null;
            /** Nom */
            nom: string;
            /** Pays */
            pays?: string | null;
            /** Site Web */
            site_web?: string | null;
            /** Statut */
            statut: string;
            /** Statut Technique */
            statut_technique?: string | null;
            /** Telephone */
            telephone?: string | null;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /**
             * Transitions Possibles
             * @default []
             */
            transitions_possibles: string[];
            /** Ville */
            ville?: string | null;
        };
        /** TenantResponse */
        TenantResponse: {
            /**
             * Archivable
             * @default false
             */
            archivable: boolean;
            /** Date Creation */
            date_creation?: string | null;
            /** Date Debut Essai */
            date_debut_essai?: string | null;
            /** Date Fin Essai */
            date_fin_essai?: string | null;
            /** Db Name */
            db_name?: string | null;
            /**
             * Devise
             * @default XOF
             */
            devise: string;
            /** Email */
            email?: string | null;
            /**
             * Fuseau Horaire
             * @default Africa/Dakar
             */
            fuseau_horaire: string;
            /**
             * Langue
             * @default fr
             */
            langue: string;
            /** Nom */
            nom: string;
            /** Pays */
            pays?: string | null;
            /** Statut */
            statut: string;
            /** Statut Technique */
            statut_technique?: string | null;
            /** Telephone */
            telephone?: string | null;
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /**
             * Transitions Possibles
             * @default []
             */
            transitions_possibles: string[];
            /** Ville */
            ville?: string | null;
        };
        /** TenantUpdate */
        TenantUpdate: {
            /** Adresse Siege */
            adresse_siege?: string | null;
            /** Devise */
            devise?: string | null;
            /** Email */
            email?: string | null;
            /** Fuseau Horaire */
            fuseau_horaire?: string | null;
            /** Langue */
            langue?: string | null;
            /** Logo Url */
            logo_url?: string | null;
            /** Motif */
            motif?: string | null;
            /** Ninea */
            ninea?: string | null;
            /** Nom */
            nom?: string | null;
            /** Pays */
            pays?: string | null;
            /** Site Web */
            site_web?: string | null;
            /** Telephone */
            telephone?: string | null;
            /** Ville */
            ville?: string | null;
        };
        /** TokenResponse */
        TokenResponse: {
            /** Access Token */
            access_token: string;
            /**
             * Expires In
             * @description Durée de validité en secondes
             */
            expires_in: number;
            /** Refresh Token */
            refresh_token: string;
            /** Tenant Id */
            tenant_id?: string | null;
            /**
             * Token Type
             * @default bearer
             */
            token_type: string;
        };
        /** TransitionStatut */
        TransitionStatut: {
            /**
             * Motif
             * @description Motif OBLIGATOIRE, journalisé
             */
            motif: string;
        };
        /**
         * TypeMouvementStockEnum
         * @enum {string}
         */
        TypeMouvementStockEnum: "ENTREE" | "SORTIE_CONSULTATION" | "PERTE_PEREMPTION" | "AJUSTEMENT_INVENTAIRE";
        /**
         * TypePieceIdentiteEnum
         * @enum {string}
         */
        TypePieceIdentiteEnum: "CNI" | "PASSEPORT" | "PERMIS" | "AUTRE";
        /** UserProfileResponse */
        UserProfileResponse: {
            /** Cabinet Id */
            cabinet_id?: string | null;
            /** Cabinet Nom */
            cabinet_nom?: string | null;
            /**
             * Email
             * Format: email
             */
            email: string;
            /**
             * Features
             * @default {}
             */
            features: {
                [key: string]: boolean;
            };
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nom */
            nom: string;
            /**
             * Permissions
             * @default []
             */
            permissions: string[];
            /** Photo Url */
            photo_url?: string | null;
            /** Plan Code */
            plan_code?: string | null;
            /** Prenom */
            prenom: string;
            /**
             * Quotas
             * @default {}
             */
            quotas: {
                [key: string]: unknown;
            };
            /** Role */
            role: string;
            /** Telephone */
            telephone?: string | null;
            /** Tenant Id */
            tenant_id?: string | null;
        };
        /** UtilisateurCreate */
        UtilisateurCreate: {
            /** Cabinet Id */
            cabinet_id?: string | null;
            /** Email */
            email: string;
            /** Mot De Passe */
            mot_de_passe: string;
            /** Nom */
            nom: string;
            /** Prenom */
            prenom: string;
            /** Role */
            role: string;
            /** Telephone */
            telephone?: string | null;
        };
        /** UtilisateurDetailResponse */
        UtilisateurDetailResponse: {
            /**
             * A Profil Professionnel
             * @default false
             */
            a_profil_professionnel: boolean;
            /** Actif */
            actif: boolean;
            /** Cabinet Id */
            cabinet_id?: string | null;
            /** Cabinet Nom */
            cabinet_nom?: string | null;
            /** Created At */
            created_at?: string | null;
            /** Dernier Login */
            dernier_login?: string | null;
            /**
             * Deux Facteurs
             * @default false
             */
            deux_facteurs: boolean;
            /** Email */
            email: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nom */
            nom: string;
            /** Numero Ordre */
            numero_ordre?: string | null;
            /** Prenom */
            prenom: string;
            /** Role */
            role: string;
            /**
             * Sessions
             * @default []
             */
            sessions: components["schemas"]["SessionUtilisateurResponse"][];
            /** Telephone */
            telephone?: string | null;
        };
        /** UtilisateurPlateformeCreate */
        UtilisateurPlateformeCreate: {
            /**
             * Activer 2Fa
             * @description Générer immédiatement le secret TOTP à activer (recommandé : true)
             * @default true
             */
            activer_2fa: boolean;
            /**
             * Email
             * Format: email
             */
            email: string;
            /**
             * Mot De Passe
             * @description Mot de passe initial — doit respecter la politique de sécurité (12 caractères, majuscule, minuscule, chiffre, caractère spécial)
             */
            mot_de_passe: string;
            /** Nom */
            nom: string;
            /** Prenom */
            prenom: string;
            /**
             * Roles
             * @description Codes de rôles (platform roles) à attribuer
             */
            roles: string[];
            /** Telephone */
            telephone?: string | null;
        };
        /** UtilisateurPlateformeResponse */
        UtilisateurPlateformeResponse: {
            /**
             * Cree Le
             * Format: date-time
             */
            cree_le: string;
            /** Dernier Login */
            dernier_login?: string | null;
            /** Deux Facteurs Actif */
            deux_facteurs_actif: boolean;
            /**
             * Email
             * Format: email
             */
            email: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Modifie Le
             * Format: date-time
             */
            modifie_le: string;
            /** Motif Desactivation */
            motif_desactivation?: string | null;
            /** Nom */
            nom: string;
            /** Prenom */
            prenom: string;
            /** Roles */
            roles: string[];
            /** Statut */
            statut: string;
            /** Telephone */
            telephone?: string | null;
            /**
             * Tentatives Echouees
             * @default 0
             */
            tentatives_echouees: number;
            /** Verrouille Jusqua */
            verrouille_jusqua?: string | null;
        };
        /** UtilisateurPlateformeUpdate */
        UtilisateurPlateformeUpdate: {
            /**
             * Motif
             * @description Motif de la modification (journalisé)
             */
            motif?: string | null;
            /** Nom */
            nom?: string | null;
            /** Prenom */
            prenom?: string | null;
            /** Roles */
            roles?: string[] | null;
            /** Telephone */
            telephone?: string | null;
        };
        /** UtilisateurResponse */
        UtilisateurResponse: {
            /**
             * A Profil Professionnel
             * @default false
             */
            a_profil_professionnel: boolean;
            /** Actif */
            actif: boolean;
            /** Cabinet Id */
            cabinet_id?: string | null;
            /** Cabinet Nom */
            cabinet_nom?: string | null;
            /** Created At */
            created_at?: string | null;
            /** Dernier Login */
            dernier_login?: string | null;
            /**
             * Deux Facteurs
             * @default false
             */
            deux_facteurs: boolean;
            /** Email */
            email: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nom */
            nom: string;
            /** Numero Ordre */
            numero_ordre?: string | null;
            /** Prenom */
            prenom: string;
            /** Role */
            role: string;
            /** Telephone */
            telephone?: string | null;
        };
        /**
         * UtilisateurUpdate
         * @description Modification de profil, de rôle ou d'état. Jamais de mot de passe.
         */
        UtilisateurUpdate: {
            /** Actif */
            actif?: boolean | null;
            /** Cabinet Id */
            cabinet_id?: string | null;
            /** Nom */
            nom?: string | null;
            /** Prenom */
            prenom?: string | null;
            /** Role */
            role?: string | null;
            /** Telephone */
            telephone?: string | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, unknown>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** VerificationEmailRequest */
        VerificationEmailRequest: {
            /** Jeton */
            jeton: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_audit_logs_api_v1_audit_get: {
        parameters: {
            query?: {
                limit?: number;
                page?: number;
                /** @description Filtrer par ID d'entité */
                resource_id?: string | null;
                /** @description Filtrer par ressource (ex: Patient) */
                resource_type?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_AuditLogResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_TokenResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RefreshTokenRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_NoneType_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_me_api_v1_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_UserProfileResponse_"];
                };
            };
        };
    };
    refresh_token_api_v1_auth_refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RefreshTokenRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_TokenResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_cabinets_api_v1_cabinets_get: {
        parameters: {
            query?: {
                inclure_inactifs?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_CabinetResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_cabinet_api_v1_cabinets__cabinet_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                cabinet_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_CabinetResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_cabinet_api_v1_cabinets__cabinet_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                cabinet_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CabinetUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_CabinetResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_fauteuils_api_v1_cabinets__cabinet_id__fauteuils_get: {
        parameters: {
            query?: {
                inclure_inactifs?: boolean;
            };
            header?: never;
            path: {
                cabinet_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_FauteuilResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_rattachement_api_v1_cabinets__cabinet_id__praticiens__praticien_id__rattachement_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                cabinet_id: string;
                praticien_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_RattachementResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    rattacher_praticien_api_v1_cabinets__cabinet_id__praticiens__praticien_id__rattachement_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                cabinet_id: string;
                praticien_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RattachementCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_RattachementResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    detacher_praticien_api_v1_cabinets__cabinet_id__praticiens__praticien_id__rattachement_delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                cabinet_id: string;
                praticien_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_salles_api_v1_cabinets__cabinet_id__salles_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                cabinet_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_SalleResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_salle_api_v1_cabinets__cabinet_id__salles_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                cabinet_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SalleCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_SalleResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    supprimer_salle_api_v1_cabinets__cabinet_id__salles__salle_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                cabinet_id: string;
                salle_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_salle_api_v1_cabinets__cabinet_id__salles__salle_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                cabinet_id: string;
                salle_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SalleUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_SalleResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    paiements_hors_session_api_v1_caisse_paiements_hors_session_get: {
        parameters: {
            query: {
                /** @description Site concerné */
                cabinet_id: string;
                limit?: number;
                page?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_PaiementCaisseResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    session_courante_api_v1_caisse_session_courante_get: {
        parameters: {
            query: {
                /** @description Site concerné */
                cabinet_id: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_Union_SessionCaisseResponse__NoneType__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_sessions_api_v1_caisse_sessions_get: {
        parameters: {
            query: {
                /** @description Site dont on veut les sessions */
                cabinet_id: string;
                limit?: number;
                page?: number;
                statut?: components["schemas"]["StatutSessionCaisseEnum"] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_SessionCaisseResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ouvrir_session_api_v1_caisse_sessions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OuvertureCaisseCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_SessionCaisseResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cloturer_session_api_v1_caisse_sessions__session_id__cloture_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClotureCaisseCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_SessionCaisseResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    paiements_de_la_session_api_v1_caisse_sessions__session_id__paiements_get: {
        parameters: {
            query?: {
                limit?: number;
                page?: number;
            };
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_PaiementCaisseResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_consultations_api_v1_consultations_get: {
        parameters: {
            query?: {
                /** @description Filtrer par auteur du soin (compte authentifie) */
                auteur_id?: string | null;
                /** @description Début de la période (ISO 8601) */
                date_debut?: string | null;
                /** @description Fin de la période (ISO 8601) */
                date_fin?: string | null;
                limit?: number;
                page?: number;
                /** @description Filtrer par patient */
                patient_id?: string | null;
                /** @description Filtrer par profil praticien */
                praticien_id?: string | null;
                /** @description PLANIFIEE | EN_ATTENTE | EN_COURS | TERMINEE | ANNULEE */
                statut?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_ConsultationResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    demarrer_consultation_api_v1_consultations_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConsultationCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ConsultationResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_consultation_api_v1_consultations__consultation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                consultation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ConsultationResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_consultation_api_v1_consultations__consultation_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                consultation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConsultationUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ConsultationResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_actes_api_v1_consultations__consultation_id__actes_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                consultation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_ActeRealiseResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_acte_api_v1_consultations__consultation_id__actes_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                consultation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ActeRealiseCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ActeRealiseResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    annuler_consultation_api_v1_consultations__consultation_id__annuler_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                consultation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConsultationAnnuler"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ConsultationResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_consultation_detail_api_v1_consultations__consultation_id__detail_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                consultation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ConsultationDetailResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    terminer_consultation_api_v1_consultations__consultation_id__terminer_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                consultation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConsultationTerminer"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ConsultationDetailResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    total_consultation_api_v1_consultations__consultation_id__total_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                consultation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_dict_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_acte_api_v1_consultations_actes__acte_id__delete: {
        parameters: {
            query?: {
                /** @description Motif de la suppression (conservé en audit) */
                motif?: string | null;
            };
            header?: never;
            path: {
                acte_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_acte_api_v1_consultations_actes__acte_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                acte_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ActeRealiseUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ActeRealiseResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_devis_api_v1_devis_get: {
        parameters: {
            query?: {
                limit?: number;
                page?: number;
                patient_id?: string | null;
                /** @description Recherche par numéro de devis */
                q?: string | null;
                /** @description BROUILLON|ENVOYE|ACCEPTE|REFUSE|EXPIRE */
                statut?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_DevisResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_devis_api_v1_devis_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DevisCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_DevisResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_devis_api_v1_devis__devis_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                devis_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_DevisResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    convertir_devis_api_v1_devis__devis_id__convertir_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                devis_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_FactureResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    changer_statut_devis_api_v1_devis__devis_id__statut_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                devis_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DevisStatutUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_DevisResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    supprimer_disponibilite_api_v1_disponibilites__disponibilite_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                disponibilite_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_factures_api_v1_factures_get: {
        parameters: {
            query?: {
                /** @description AAAA-MM-JJ (date d'émission min.) */
                date_debut?: string | null;
                /** @description AAAA-MM-JJ (date d'émission max.) */
                date_fin?: string | null;
                limit?: number;
                page?: number;
                patient_id?: string | null;
                /** @description Recherche par numéro de facture */
                q?: string | null;
                /** @description BROUILLON|EMISE|PARTIELLEMENT_PAYEE|PAYEE|ANNULEE */
                statut?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_FactureResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    facturer_libre_api_v1_factures_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FactureLibreCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_FactureResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_facture_api_v1_factures__facture_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facture_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_FactureResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    annuler_facture_api_v1_factures__facture_id__annuler_post: {
        parameters: {
            query: {
                /** @description Motif de l'annulation (conservé en audit) */
                motif: string;
            };
            header?: never;
            path: {
                facture_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_FactureResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_echelonnement_api_v1_factures__facture_id__echelonnement_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facture_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PlanEchelonnementResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_echelonnement_api_v1_factures__facture_id__echelonnement_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facture_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanEchelonnementCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PlanEchelonnementResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    encaisser_api_v1_factures__facture_id__paiements_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facture_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PaiementCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PaiementResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    facturer_consultation_api_v1_factures_consultation__consultation_id__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                consultation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FactureConsultationCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_FactureResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    journal_caisse_api_v1_factures_journal_caisse_get: {
        parameters: {
            query?: {
                /** @description AAAA-MM-JJ */
                date_debut?: string | null;
                /** @description AAAA-MM-JJ */
                date_fin?: string | null;
                limit?: number;
                /** @description ESPECES|CARTE_BANCAIRE|CHEQUE|VIREMENT|MOBILE_MONEY|ASSURANCE */
                mode?: string | null;
                page?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_dict_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    supprimer_fauteuil_api_v1_fauteuils__fauteuil_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                fauteuil_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_fauteuil_api_v1_fauteuils__fauteuil_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                fauteuil_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FauteuilUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_FauteuilResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reactiver_fauteuil_api_v1_fauteuils__fauteuil_id__reactiver_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                fauteuil_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_FauteuilResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    master_login_api_v1_master_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SuperAdminLogin"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_MasterTokenResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    master_logout_api_v1_master_auth_logout_post: {
        parameters: {
            query: {
                refresh_token: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_NoneType_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    master_me_api_v1_master_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_SuperAdminResponse_"];
                };
            };
        };
    };
    master_refresh_api_v1_master_auth_refresh_post: {
        parameters: {
            query: {
                refresh_token: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_MasterTokenResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_societes_api_v1_master_societes_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_SocieteResponse__"];
                };
            };
        };
    };
    create_societe_api_v1_master_societes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SocieteCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_SocieteResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_societe_api_v1_master_societes__societe_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                societe_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_SocieteResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_societe_api_v1_master_societes__societe_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                societe_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SocieteUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_SocieteResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_societe_statut_api_v1_master_societes__societe_id__statut_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                societe_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SocieteStatutUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_SocieteResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    statistiques_api_v1_master_statistiques_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_dict_"];
                };
            };
        };
    };
    list_nomenclature_api_v1_nomenclature_actes_get: {
        parameters: {
            query?: {
                /** @description Filtrer par catégorie */
                categorie?: string | null;
                /** @description Inclure les actes retirés de la nomenclature */
                inclure_inactifs?: boolean;
                limit?: number;
                page?: number;
                /** @description Recherche par code ou libellé */
                q?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_dict_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_acte_nomenclature_api_v1_nomenclature_actes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ActeNomenclatureCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_dict_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_odontogramme_api_v1_odontogramme_patients__patient_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_OdontogrammeResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_odontogramme_api_v1_odontogramme_patients__patient_id__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OdontogrammeCreer"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_OdontogrammeResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_chartings_api_v1_odontogramme_patients__patient_id__charting_get: {
        parameters: {
            query?: {
                /** @description Filtrer par dent */
                dent_id?: string | null;
            };
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_ChartingParodontalResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_charting_api_v1_odontogramme_patients__patient_id__charting_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChartingParodontalCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ChartingParodontalResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_dent_api_v1_odontogramme_patients__patient_id__dent_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DentMiseAJour"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_OdontogrammeResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_dent_api_v1_odontogramme_patients__patient_id__dent__numero_fdi__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                numero_fdi: number;
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_DentResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_faces_api_v1_odontogramme_patients__patient_id__dent__numero_fdi__faces_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                numero_fdi: number;
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FacesMiseAJour"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_OdontogrammeResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_historique_dent_api_v1_odontogramme_patients__patient_id__dent__numero_fdi__historique_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                numero_fdi: number;
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_HistoriqueDentResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_dents_api_v1_odontogramme_patients__patient_id__dents_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DentsMiseAJourLot"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_OdontogrammeResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_historique_global_api_v1_odontogramme_patients__patient_id__historique_get: {
        parameters: {
            query?: {
                /** @description Nombre de lignes maxi */
                limit?: number;
            };
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_EtatHistoriqueResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    referentiel_etats_api_v1_odontogramme_referentiel_etats_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_dict_"];
                };
            };
        };
    };
    etat_api_v1_onboarding_etat_get: {
        parameters: {
            query: {
                /** @description Identifiant du cabinet */
                tenant_id: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_OnboardingEtatResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    inscrire_api_v1_onboarding_inscription_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InscriptionCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_InscriptionResponse_"];
                };
            };
            /** @description Inscription refusée. Message volontairement identique que l'adresse existe déjà ou non — ni de fuite d'information. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Trop de tentatives depuis cette adresse */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Inscriptions temporairement désactivées */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    verifier_email_api_v1_onboarding_verification_email_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VerificationEmailRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_dict_"];
                };
            };
            /** @description Jeton invalide, expiré ou déjà utilisé */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_ordonnances_api_v1_ordonnances_get: {
        parameters: {
            query?: {
                /** @description Filtrer par consultation */
                consultation_id?: string | null;
                limit?: number;
                page?: number;
                /** @description Filtrer par patient */
                patient_id?: string | null;
                /** @description Filtrer sur la signature : true signee, false non signee */
                signe?: boolean | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_OrdonnanceResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_ordonnance_api_v1_ordonnances_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OrdonnanceCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_OrdonnanceResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_ordonnance_api_v1_ordonnances__prescription_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                prescription_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_OrdonnanceResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_ordonnance_api_v1_ordonnances__prescription_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                prescription_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OrdonnanceUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_OrdonnanceResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ajouter_ligne_api_v1_ordonnances__prescription_id__lignes_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                prescription_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LignePrescriptionCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_OrdonnanceResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    supprimer_ligne_api_v1_ordonnances__prescription_id__lignes__ligne_id__delete: {
        parameters: {
            query?: {
                /** @description Motif de la suppression (conservé en audit) */
                motif?: string | null;
            };
            header?: never;
            path: {
                ligne_id: string;
                prescription_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_OrdonnanceResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    signer_ordonnance_api_v1_ordonnances__prescription_id__signer_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                prescription_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_OrdonnanceResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    controler_prescription_api_v1_ordonnances_controle_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ControleContreIndication"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ControleContreIndicationResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_medicaments_api_v1_ordonnances_medicaments_get: {
        parameters: {
            query?: {
                /** @description Classe thérapeutique (AINS, ANTIBIOTIQUE...) */
                classe?: string | null;
                /** @description COMPRIME, BADEROUCHE, CAROUCHE... */
                forme?: string | null;
                /** @description Inclure les médicaments retirés */
                inclure_inactifs?: boolean;
                /** @description Recherche par nom commercial ou DCI */
                q?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_MedicamentResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_medicament_api_v1_ordonnances_medicaments_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MedicamentCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_MedicamentResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_patients_api_v1_patients_get: {
        parameters: {
            query?: {
                /** @description Filtrer par date de naissance */
                date_naissance?: string | null;
                /** @description Inclure les dossiers archivés */
                include_archives?: boolean;
                limit?: number;
                /** @description Filtrer par nom */
                nom?: string | null;
                /** @description Filtrer par numéro de dossier exact */
                numero_dossier?: string | null;
                page?: number;
                /** @description Recherche libre (nom, prénom, N° dossier, tél.) */
                q?: string | null;
                /** @description Filtrer par téléphone */
                telephone?: string | null;
                /** @description Ne renvoyer que les dossiers archivés */
                uniquement_archives?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_PatientResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_patient_api_v1_patients_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PatientCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PatientResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_patient_api_v1_patients__patient_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PatientResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_patient_api_v1_patients__patient_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PatientUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PatientResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_antecedents_api_v1_patients__patient_id__antecedents_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_AntecedentMedicalResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_antecedent_api_v1_patients__patient_id__antecedents_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AntecedentMedicalCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_AntecedentMedicalResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    archive_patient_api_v1_patients__patient_id__archiver_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PatientArchive"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PatientResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_patient_dossier_api_v1_patients__patient_id__dossier_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PatientDossierCompletResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_etat_general_api_v1_patients__patient_id__etat_general_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_Union_EtatGeneralResponse__NoneType__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upsert_etat_general_api_v1_patients__patient_id__etat_general_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EtatGeneralCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_EtatGeneralResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    patch_etat_general_api_v1_patients__patient_id__etat_general_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EtatGeneralUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_EtatGeneralResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reactivate_patient_api_v1_patients__patient_id__reactiver_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PatientResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_antecedent_api_v1_patients_antecedents__antecedent_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                antecedent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AntecedentMedicalUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_AntecedentMedicalResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_acces_support_api_v1_platform_acces_support_get: {
        parameters: {
            query?: {
                seulement_actifs?: boolean;
                /** @description Filtrer par cabinet */
                tenant_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_AccesSupportResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoquer_acces_support_api_v1_platform_acces_support__acces_id__revocation_post: {
        parameters: {
            query: {
                /** @description Motif de la révocation */
                motif: string;
            };
            header?: never;
            path: {
                acces_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_AccesSupportResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_annonces_api_v1_platform_annonces_get: {
        parameters: {
            query?: {
                actives_seulement?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_AnnonceResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    publier_annonce_api_v1_platform_annonces_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnnonceCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_AnnonceResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    desactiver_annonce_api_v1_platform_annonces__annonce_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                annonce_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_AnnonceResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_audit_api_v1_platform_audit_get: {
        parameters: {
            query?: {
                acteur_email?: string | null;
                action?: string | null;
                debut?: string | null;
                fin?: string | null;
                limit?: number;
                page?: number;
                tenant_id?: string | null;
                type_cible?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_AuditEntryResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    exporter_audit_api_v1_platform_audit_export_get: {
        parameters: {
            query?: {
                acteur_email?: string | null;
                action?: string | null;
                debut?: string | null;
                fin?: string | null;
                tenant_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Fichier CSV */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/csv": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    confirmer_2fa_api_v1_platform_auth_2fa_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Challenge2FARequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PlatformTokenResponse_"];
                };
            };
            /** @description Défi invalide, expiré ou code incorrect (message indistinct) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Trop de tentatives */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    activer_2fa_api_v1_platform_auth_2fa_activation_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Activer2FARequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_Enrolement2FAResponse_"];
                };
            };
            /** @description Jeton d'enrolement invalide, expire ou deja utilise */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Code de verification invalide */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    regenerer_codes_secours_api_v1_platform_auth_2fa_codes_secours_regenerer_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegenererCodesSecoursRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_RegenererCodesSecoursResponse_"];
                };
            };
            /** @description TOTP invalide, ou compte sans second facteur actif */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Trop de tentatives (limitation de débit) */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    preparer_2fa_api_v1_platform_auth_2fa_preparation_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_Activation2FAResponse_"];
                };
            };
        };
    };
    login_api_v1_platform_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlatformLoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_LoginPlateformeResponse_"];
                };
            };
            /** @description Identifiants invalides (message volontairement indistinct) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Adresse IP hors de la liste blanche */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Trop de tentatives (limitation de débit) */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    logout_api_v1_platform_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlatformRefreshRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_NoneType_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    me_api_v1_platform_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PlatformProfilResponse_"];
                };
            };
            /** @description Non authentifié ou jeton expiré */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    changer_mot_de_passe_api_v1_platform_auth_mot_de_passe_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChangementMotDePasseRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_NoneType_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    refresh_api_v1_platform_auth_refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlatformRefreshRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PlatformTokenResponse_"];
                };
            };
            /** @description Refresh token inconnu, révoqué ou expiré */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_factures_api_v1_platform_invoices_get: {
        parameters: {
            query?: {
                limit?: number;
                page?: number;
                /** @description BROUILLON | EMISE | PAYEE | EN_RETARD | ANNULEE */
                statut?: string | null;
                tenant_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_FacturePlateformeResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_facture_api_v1_platform_invoices_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FacturePlateformeCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_FacturePlateformeResponse_"];
                };
            };
            /** @description Aucune ligne fournie */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    changer_statut_facture_api_v1_platform_invoices__facture_id__statut_post: {
        parameters: {
            query: {
                motif?: string | null;
                /** @description BROUILLON | EMISE | PAYEE | EN_RETARD | ANNULEE */
                statut: string;
            };
            header?: never;
            path: {
                facture_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_FacturePlateformeResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_permissions_api_v1_platform_permissions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_PermissionPlateformeResponse__"];
                };
            };
        };
    };
    lister_plans_api_v1_platform_plans_get: {
        parameters: {
            query?: {
                actif_seulement?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_PlanResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_plan_api_v1_platform_plans_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PlanResponse_"];
                };
            };
            /** @description Code de plan déjà utilisé */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    modifier_plan_api_v1_platform_plans__plan_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PlanResponse_"];
                };
            };
            /** @description Plan introuvable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    historique_plan_api_v1_platform_plans__plan_id__revisions_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_PlanRevisionResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_roles_api_v1_platform_roles_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_RolePlateformeResponse__"];
                };
            };
            /** @description Non authentifié */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Permission insuffisante */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    sante_api_v1_platform_sante_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_dict_"];
                };
            };
        };
    };
    stats_dashboard_api_v1_platform_stats_dashboard_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_DashboardResponse_"];
                };
            };
        };
    };
    stats_globales_api_v1_platform_stats_globales_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_StatsGlobalesResponse_"];
                };
            };
        };
    };
    stats_tenant_api_v1_platform_stats_tenants__tenant_id__get: {
        parameters: {
            query?: {
                jours?: number;
            };
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_StatsTenantResponse_"];
                };
            };
            /** @description Cabinet sans dossier plateforme */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_abonnements_api_v1_platform_subscriptions_get: {
        parameters: {
            query?: {
                /** @description ESSAI | ACTIF | SUSPENDU | EXPIRE | RESILIE */
                statut?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_AbonnementResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    detail_abonnement_api_v1_platform_subscriptions__abonnement_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                abonnement_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_AbonnementResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    changer_plan_api_v1_platform_subscriptions__abonnement_id__plan_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                abonnement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChangementPlan"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_AbonnementResponse_"];
                };
            };
            /** @description Abonnement ou plan introuvable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    historique_abonnement_api_v1_platform_subscriptions_tenant__tenant_id__historique_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_dict__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_tenants_api_v1_platform_tenants_get: {
        parameters: {
            query?: {
                /** @description true = archivés uniquement */
                archive?: boolean | null;
                /** @description Date de création minimale */
                created_from?: string | null;
                /** @description Date de création maximale */
                created_to?: string | null;
                limit?: number;
                page?: number;
                pays?: string | null;
                /** @description Filtrer par code de plan */
                plan?: string | null;
                /** @description Recherche sur nom, ville, téléphone, e-mail */
                q?: string | null;
                /** @description ESSAI | ACTIF | SUSPENDU | RESILIE */
                statut?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_TenantResponse_"];
                };
            };
            /** @description Non authentifié */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Permission insuffisante */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_tenant_api_v1_platform_tenants_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TenantCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_TenantCreationResponse_"];
                };
            };
            /** @description Non authentifié */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Permission insuffisante */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description NINEA ou e-mail administrateur déjà utilisé */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Échec du provisionnement — entièrement annulé (aucun tenant à moitié créé) */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    detail_tenant_api_v1_platform_tenants__tenant_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_TenantDetailResponse_"];
                };
            };
            /** @description Cabinet introuvable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    modifier_tenant_api_v1_platform_tenants__tenant_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TenantUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_TenantDetailResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ouvrir_acces_support_api_v1_platform_tenants__tenant_id__acces_support_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AccesSupportCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_SupportTokenResponse_"];
                };
            };
            /** @description Motif manquant ou trop court pour une élévation */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Permission `platform.support.grant` manquante */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Cabinet introuvable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Cabinet résilié : dossier inaccessible */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    archiver_tenant_api_v1_platform_tenants__tenant_id__archivage_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Archivage"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_TenantDetailResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    historique_tenant_api_v1_platform_tenants__tenant_id__historique_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_HistoriqueStatutEntry__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    quotas_tenant_api_v1_platform_tenants__tenant_id__quotas_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_QuotaResumeResponse_"];
                };
            };
            /** @description Cabinet sans dossier plateforme */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    simuler_quota_api_v1_platform_tenants__tenant_id__quotas_simulation_get: {
        parameters: {
            query: {
                consommation: number;
                /** @description utilisateurs | sites | praticiens | … */
                ressource: string;
            };
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_dict_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reactiver_tenant_api_v1_platform_tenants__tenant_id__reactivation_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TransitionStatut"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_TenantDetailResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resilier_tenant_api_v1_platform_tenants__tenant_id__resiliation_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TransitionStatut"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_TenantDetailResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    suspendre_tenant_api_v1_platform_tenants__tenant_id__suspension_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TransitionStatut"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_TenantDetailResponse_"];
                };
            };
            /** @description Permission insuffisante */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Transition non autorisée depuis l'état courant */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    matrice_transitions_api_v1_platform_tenants_transitions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_dict_"];
                };
            };
        };
    };
    lister_utilisateurs_api_v1_platform_users_get: {
        parameters: {
            query?: {
                limit?: number;
                page?: number;
                /** @description Recherche sur e-mail, prénom ou nom */
                q?: string | null;
                /** @description ACTIF | DESACTIF | VERROUILLE */
                statut?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_UtilisateurPlateformeResponse_"];
                };
            };
            /** @description Non authentifié */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Permission insuffisante */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_utilisateur_api_v1_platform_users_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UtilisateurPlateformeCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_CreationUtilisateurResponse_"];
                };
            };
            /** @description Non authentifié */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Permission insuffisante */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Adresse e-mail déjà utilisée */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Mot de passe non conforme à la politique (détail des règles) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    detail_utilisateur_api_v1_platform_users__utilisateur_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                utilisateur_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_DetailUtilisateurResponse_"];
                };
            };
            /** @description Compte introuvable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    supprimer_utilisateur_api_v1_platform_users__utilisateur_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                utilisateur_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SuppressionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Permission insuffisante */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Motif absent, confirmation incorrecte, ou dernier Super Admin */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    modifier_utilisateur_api_v1_platform_users__utilisateur_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                utilisateur_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UtilisateurPlateformeUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_UtilisateurPlateformeResponse_"];
                };
            };
            /** @description Compte introuvable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Rôle inconnu ou retrait du rôle du dernier Super Admin refusé */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    desactiver_utilisateur_api_v1_platform_users__utilisateur_id__desactivation_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                utilisateur_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DesactivationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_UtilisateurPlateformeResponse_"];
                };
            };
            /** @description Permission insuffisante */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Refusé : c'est le dernier Super Admin actif */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    reactiver_utilisateur_api_v1_platform_users__utilisateur_id__reactivation_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                utilisateur_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_UtilisateurPlateformeResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reinitialiser_acces_api_v1_platform_users__utilisateur_id__reinitialisation_acces_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                utilisateur_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReinitialisationAccesRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_Activation2FAResponse_"];
                };
            };
            /** @description Refusé : c'est le dernier Super Admin actif */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    lister_praticiens_api_v1_praticiens_get: {
        parameters: {
            query?: {
                /** @description Restreindre à un site */
                cabinet_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_PraticienResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_praticien_api_v1_praticiens_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PraticienCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PraticienResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_praticien_api_v1_praticiens__praticien_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                praticien_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PraticienResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_praticien_api_v1_praticiens__praticien_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                praticien_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PraticienUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_PraticienResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_creneaux_api_v1_praticiens__praticien_id__creneaux_get: {
        parameters: {
            query: {
                cabinet_id?: string | null;
                /** @description Date visée au format YYYY-MM-DD */
                date: string;
                duree_minutes?: number;
            };
            header?: never;
            path: {
                praticien_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_CreneauxResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_disponibilites_api_v1_praticiens__praticien_id__disponibilites_get: {
        parameters: {
            query?: {
                /** @description Filtrer par site (inclut les plages tous-sites) */
                cabinet_id?: string | null;
            };
            header?: never;
            path: {
                praticien_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_DisponibiliteResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_disponibilite_api_v1_praticiens__praticien_id__disponibilites_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                praticien_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DisponibiliteCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_DisponibiliteResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_permissions_api_v1_rbac_permissions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_dict__"];
                };
            };
        };
    };
    list_roles_api_v1_rbac_roles_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_RoleResponse__"];
                };
            };
        };
    };
    create_role_api_v1_rbac_roles_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RoleCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_RoleResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    grant_permission_api_v1_rbac_roles__role_id__permissions_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PermissionGrant"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_RoleResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_permission_api_v1_rbac_roles__role_id__permissions_delete: {
        parameters: {
            query: {
                /** @description Permission au format MODULE:ACTION */
                permission: string;
            };
            header?: never;
            path: {
                role_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_RoleResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_referentiel_disponibilites_api_v1_referentiel_disponibilites_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ReferentielJoursResponse_"];
                };
            };
        };
    };
    lister_rendez_vous_api_v1_rendez_vous_get: {
        parameters: {
            query?: {
                /** @description Inclut les rendez-vous débutant avant */
                au?: string | null;
                cabinet_id?: string | null;
                /** @description Inclut les rendez-vous finissant après */
                du?: string | null;
                fauteuil_id?: string | null;
                limit?: number;
                page?: number;
                patient_id?: string | null;
                praticien_id?: string | null;
                /** @description Filtrer par statut(s) */
                statut?: string[] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_RendezVousResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_rendez_vous_api_v1_rendez_vous_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RendezVousCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_RendezVousResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_rendez_vous_api_v1_rendez_vous__rendez_vous_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rendez_vous_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_RendezVousResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_rendez_vous_api_v1_rendez_vous__rendez_vous_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rendez_vous_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RendezVousUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_RendezVousResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    demarrer_consultation_api_v1_rendez_vous__rendez_vous_id__consultation_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rendez_vous_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    planifier_rendez_vous_api_v1_rendez_vous__rendez_vous_id__planifier_post: {
        parameters: {
            query: {
                /** @description Nouvelle date/heure de début */
                debut: string;
                duree_minutes?: number;
                fauteuil_id?: string | null;
                motif_report?: string | null;
            };
            header?: never;
            path: {
                rendez_vous_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_RendezVousResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    changer_statut_api_v1_rendez_vous__rendez_vous_id__statut_post: {
        parameters: {
            query: {
                motif?: string | null;
                /** @description Un de ('PLANIFIE', 'CONFIRME', 'EN_SALLE_ATTENTE', 'EN_CONSULTATION', 'TERMINEE', 'ANNULE', 'ABSENT') */
                statut: string;
            };
            header?: never;
            path: {
                rendez_vous_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_RendezVousResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_agenda_api_v1_rendez_vous_agenda_get: {
        parameters: {
            query: {
                cabinet_id?: string | null;
                date: string;
                praticien_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_AgendaResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_creneaux_libres_api_v1_rendez_vous_creneaux_libres_get: {
        parameters: {
            query: {
                cabinet_id?: string | null;
                /** @description Date visée au format YYYY-MM-DD */
                date: string;
                /** @description Durée du rendez-vous envisagé */
                duree_minutes?: number;
                /** @description Rendez-vous en cours de report : son créneau reste proposé. */
                exclure_rendez_vous?: string | null;
                praticien_id: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_CreneauLibre__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    bloquer_fauteuil_api_v1_rendez_vous_fauteuils_blocage_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BlocageFauteuilCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    debloquer_fauteuil_api_v1_rendez_vous_fauteuils_blocage__creneau_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                creneau_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_referentiel_api_v1_rendez_vous_referentiel_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_StatutRendezVousResponse_"];
                };
            };
        };
    };
    creer_fauteuil_api_v1_salles__salle_id__fauteuils_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                salle_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FauteuilCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_FauteuilResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_alertes_api_v1_stock_alertes_get: {
        parameters: {
            query: {
                /** @description Site à surveiller */
                cabinet_id: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_List_AlerteStockResponse__"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_articles_api_v1_stock_articles_get: {
        parameters: {
            query: {
                alerte_seuil?: boolean;
                /** @description Site dont on veut le stock */
                cabinet_id: string;
                categorie?: string | null;
                limit?: number;
                page?: number;
                peremption_proche?: boolean;
                q?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_ArticleStockResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_article_api_v1_stock_articles_post: {
        parameters: {
            query: {
                /** @description Site qui reçoit le stock initial */
                cabinet_id: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArticleStockCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ArticleStockResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    modifier_article_api_v1_stock_articles__article_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                article_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArticleStockUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ArticleStockResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_commandes_api_v1_stock_commandes_get: {
        parameters: {
            query?: {
                fournisseur_id?: string | null;
                limit?: number;
                page?: number;
                statut?: components["schemas"]["StatutCommandeEnum"] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_CommandeResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_commande_api_v1_stock_commandes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CommandeCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_CommandeResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    changer_statut_commande_api_v1_stock_commandes__commande_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                commande_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StatutCommandeUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_CommandeResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_fournisseurs_api_v1_stock_fournisseurs_get: {
        parameters: {
            query?: {
                limit?: number;
                page?: number;
                q?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_FournisseurResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_fournisseur_api_v1_stock_fournisseurs_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FournisseurCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_FournisseurResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    modifier_fournisseur_api_v1_stock_fournisseurs__fournisseur_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                fournisseur_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FournisseurUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_FournisseurResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_mouvements_api_v1_stock_mouvements_get: {
        parameters: {
            query?: {
                article_id?: string | null;
                cabinet_id?: string | null;
                limit?: number;
                page?: number;
                type_mouvement?: components["schemas"]["TypeMouvementStockEnum"] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_MouvementStockResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    enregistrer_mouvement_api_v1_stock_mouvements_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MouvementStockCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_MouvementStockResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    enregistrer_reception_api_v1_stock_receptions_post: {
        parameters: {
            query: {
                /** @description Commande réceptionnée */
                commande_id: string;
                /** @description Site qui reçoit la matière */
                site_id: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReceptionCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_ReceptionResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_utilisateurs_api_v1_utilisateurs_get: {
        parameters: {
            query?: {
                /** @description Filtrer par état du compte */
                actif?: boolean | null;
                /** @description Filtrer par site */
                cabinet_id?: string | null;
                limit?: number;
                page?: number;
                /** @description Recherche sur nom, prénom, email */
                q?: string | null;
                /** @description Filtrer par nom de rôle */
                role?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_UtilisateurResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    creer_utilisateur_api_v1_utilisateurs_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UtilisateurCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_UtilisateurResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    obtenir_utilisateur_api_v1_utilisateurs__utilisateur_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                utilisateur_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_UtilisateurDetailResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    desactiver_utilisateur_api_v1_utilisateurs__utilisateur_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                utilisateur_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_UtilisateurResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    modifier_utilisateur_api_v1_utilisateurs__utilisateur_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                utilisateur_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UtilisateurUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_UtilisateurResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reinitialiser_mot_de_passe_api_v1_utilisateurs__utilisateur_id__mot_de_passe_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                utilisateur_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["APIResponse_MotDePasseTemporaireResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lister_sessions_api_v1_utilisateurs__utilisateur_id__sessions_get: {
        parameters: {
            query?: {
                actives_seulement?: boolean;
            };
            header?: never;
            path: {
                utilisateur_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaginatedResponse_SessionUtilisateurResponse_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoquer_sessions_api_v1_utilisateurs__utilisateur_id__sessions_delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                utilisateur_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_check_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
}
