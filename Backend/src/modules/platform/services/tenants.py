"""
Cycle de vie des cabinets (Phase B.1, B.2, B.3).

## Machine à états

        ┌──────────────┐   activation    ┌───────────┐
        │ ESSAI        │ ───────────────► │ ACTIF     │
        │ (onboarding) │                  │           │
        └──────┬───────┘                  └─────┬─────┘
               │                                │
       expiration essai                 suspension
               │                                │
               ▼                                ▼
        ┌──────────────┐  réactivation  ┌────────────┐
        │ SUSPENDU     │ ◄───────────── │ SUSPENDU   │
        └──────┬───────┘                └─────┬──────┘
               │                              │
               │ résiliation                  │ résiliation
               ▼                              ▼
        ┌────────────────────────────────────────────┐
        │ RESILIE  (terminal)                        │
        └────────────────────────────────────────────┘

Deux décisions de conception :

- **Motif obligatoire sur toute transition.** Une suspension sans raison écrite
  est impossible à contester plus tard, pour le client comme pour l'éditeur.
  L'historique est horodaté et contient l'avant, l'après, l'auteur et l'IP.
- **Les effets sur l'application cliente sont posés par la même fonction que le
  statut.** Écrire `SUSPENDU` dans la base plateforme sans poser
  `tenants_db.statut = 'SUSPENDED'` côté master laisserait le cabinet se
  connecter : les deux leviers sont actionnés ensemble, ou pas du tout.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    BusinessRuleViolationException,
    EntityNotFoundException,
    InvalidTransitionException,
)
from src.modules.master.models import Societe, TenantDB
from src.modules.platform.models import (
    StatutTenant,
    StatutTenantHistorique,
    TenantPlateforme,
)

logger = structlog.get_logger(__name__)

#: Transitions autorisées. Source unique : un endpoint qui n'est pas dans cette
#: table ne doit pas exister.
TRANSITIONS_AUTORISEES: Dict[StatutTenant, List[StatutTenant]] = {
    StatutTenant.ESSAI: [StatutTenant.ACTIF, StatutTenant.SUSPENDU],
    StatutTenant.ACTIF: [StatutTenant.SUSPENDU, StatutTenant.RESILIE],
    StatutTenant.SUSPENDU: [StatutTenant.ACTIF, StatutTenant.RESILIE],
    StatutTenant.RESILIE: [],
}

#: Effet de chaque statut sur la capacité du cabinet à servir ses utilisateurs.
#: `tenants_db.statut` est le levier technique réellement lu par
#: `get_tenant_db()` et par la résolution du login tenant.
STATUT_TECHNIQUE_MASTER: Dict[StatutTenant, str] = {
    StatutTenant.ESSAI: "ACTIVE",
    StatutTenant.ACTIF: "ACTIVE",
    StatutTenant.SUSPENDU: "SUSPENDED",
    StatutTenant.RESILIE: "ARCHIVED",
}


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def transitions_possibles(statut: StatutTenant) -> List[str]:
    return [s.value for s in TRANSITIONS_AUTORISEES.get(statut, [])]


async def _charger_identites(
    master_db: AsyncSession, dossiers: List[TenantPlateforme]
) -> Tuple[Dict[uuid.UUID, Societe], Dict[uuid.UUID, TenantDB]]:
    """
    Charge, depuis la base MASTER, les identité et dossier de connexion des
    cabinets listés. Deux requêtes groupées, jamais une par cabinet : à 200
    tenants, une requête par tenant ferait 200 allers-retours pour un écran de
    liste.
    """
    identites: Dict[uuid.UUID, Societe] = {}
    dossiers_db: Dict[uuid.UUID, TenantDB] = {}
    ids = [d.tenant_id for d in dossiers]
    if not ids:
        return identites, dossiers_db

    for societe in (await master_db.execute(select(Societe).where(Societe.id.in_(ids)))).scalars():
        identites[societe.id] = societe
    for tenant_db in (
        await master_db.execute(select(TenantDB).where(TenantDB.societe_id.in_(ids)))
    ).scalars():
        dossiers_db[tenant_db.societe_id] = tenant_db
    return identites, dossiers_db


class TenantService:
    # ─────────────────────────────────────────────────────────────────────────
    # Lecture
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def _charger_dossier(platform_db: AsyncSession, tenant_id: uuid.UUID) -> TenantPlateforme:
        dossier = (
            await platform_db.execute(
                select(TenantPlateforme).where(TenantPlateforme.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if dossier is None:
            raise EntityNotFoundException("Cabinet", tenant_id)
        return dossier

    @staticmethod
    async def exiger_dossier(platform_db: AsyncSession, tenant_id: uuid.UUID) -> TenantPlateforme:
        """
        Charge un dossier de cabinet ou lève 404.

        Exposée séparément de `_charger_dossier` : les routes d'un autre module
        (supervision) ont besoin de « vérifier que ce cabinet existe » sans
        passer par le registre paginé, qui ouvrirait une session master pour rien.
        """
        return await TenantService._charger_dossier(platform_db, tenant_id)

    @staticmethod
    async def lister(
        platform_db: AsyncSession,
        master_db: AsyncSession,
        *,
        recherche: Optional[str] = None,
        statut: Optional[str] = None,
        plan_code: Optional[str] = None,
        pays: Optional[str] = None,
        archive: Optional[bool] = None,
        created_from: Optional[date] = None,
        created_to: Optional[date] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Registre paginé des cabinets.

        Croise deux bases : le dossier métier (plateforme) et l'identité
        (master). Le nom affiché est celui de `societes`, qui reste la source de
        vérité unique pour « qui est ce cabinet ».
        """
        # ⚠️ AUCUN JOIN POSSIBLE ICI.
        # `TenantPlateforme` est dans la base PLATEFORME, `Societe` et `TenantDB`
        # dans la base MASTER. Un `select(A).join(B)` produirait UNE seule requête
        # SQL exécutée sur la connexion plateforme, où la table `societes`
        # n'existe pas : erreur « relation societes does not exist ». C'est la
        # contrepartie assumée de la décision D1 (bases séparées) : la référence
        # entre deux bases est applicative, donc on fait deux requêtes et on
        # fusionne en mémoire.
        stmt = select(TenantPlateforme)

        if statut:
            stmt = stmt.where(TenantPlateforme.statut_metier == statut)
        if pays:
            stmt = stmt.where(TenantPlateforme.pays == pays)
        if archive is not None:
            stmt = stmt.where(TenantPlateforme.archivable.is_(archive))

        dossiers = list((await platform_db.execute(stmt)).scalars().all())
        societes, dossiers_db = await _charger_identites(master_db, dossiers)

        if recherche:
            motif = recherche.strip().lower()
            filtres = []
            for dossier in dossiers:
                societe = societes.get(dossier.tenant_id)
                if societe is None:
                    continue
                if motif in (societe.nom or "").lower() or motif in (societe.ville or "").lower():
                    filtres.append(dossier)
                elif motif and motif in (societe.telephone or "").lower():
                    filtres.append(dossier)
                elif motif and motif in (societe.email or "").lower():
                    filtres.append(dossier)
            dossiers = filtres

        if created_from:
            dossiers = [
                d for d in dossiers
                if d in societes and societes[d.tenant_id].created_at
                and societes[d.tenant_id].created_at.date() >= created_from
            ]
        if created_to:
            dossiers = [
                d for d in dossiers
                if d in societes and societes[d.tenant_id].created_at
                and societes[d.tenant_id].created_at.date() <= created_to
            ]

        # Tri par date de création décroissante (source : table master).
        dossiers.sort(
            key=lambda d: societes[d.tenant_id].created_at if d.tenant_id in societes else d.created_at,
            reverse=True,
        )

        if plan_code:
            from src.modules.platform.services.plans import AbonnementService

            retenus: List[TenantPlateforme] = []
            for dossier in dossiers:
                abonnement = await AbonnementService.pour_tenant(platform_db, dossier.tenant_id)
                if abonnement and (abonnement.plan_fige or {}).get("code") == plan_code:
                    retenus.append(dossier)
            dossiers = retenus

        dossiers = dossiers[offset : offset + limit]
        return [
            _vers_ligne(d, societes.get(d.tenant_id), dossiers_db.get(d.tenant_id))
            for d in dossiers
            if d.tenant_id in societes
        ]

    @staticmethod
    async def compter(
        platform_db: AsyncSession,
        master_db: AsyncSession,
        *,
        recherche: Optional[str] = None,
        statut: Optional[str] = None,
        archive: Optional[bool] = None,
    ) -> int:
        # Même contrainte que `lister` : aucun JOIN entre les deux bases.
        # Le décompte se fait donc en mémoire sur les dossiers filtrés.
        elements = await TenantService.lister(
            platform_db,
            master_db,
            recherche=recherche,
            statut=statut,
            archive=archive,
            limit=1_000_000,
            offset=0,
        )
        return len(elements)

    @staticmethod
    async def detail(
        platform_db: AsyncSession, master_db: AsyncSession, tenant_id: uuid.UUID
    ) -> Dict[str, Any]:
        dossier = await TenantService._charger_dossier(platform_db, tenant_id)
        societe = (
            await master_db.execute(select(Societe).where(Societe.id == tenant_id))
        ).scalar_one_or_none()
        if societe is None:
            raise EntityNotFoundException("Cabinet", tenant_id)
        tenant_db = (
            await master_db.execute(select(TenantDB).where(TenantDB.societe_id == tenant_id))
        ).scalar_one_or_none()

        from src.modules.platform.services.plans import AbonnementService

        abonnement = await AbonnementService.pour_tenant(platform_db, tenant_id)

        ligne = _vers_ligne(dossier, societe, tenant_db)
        ligne["adresse_siege"] = societe.adresse_siege
        ligne["site_web"] = societe.site_web
        ligne["logo_url"] = societe.logo_url
        ligne["ninea"] = societe.ninea
        ligne["abonnement"] = (
            {
                "id": str(abonnement.id),
                "numero": abonnement.numero_abonnement,
                "statut": abonnement.statut.value,
                "plan": (abonnement.plan_fige or {}).get("code"),
                "date_debut": abonnement.date_debut.isoformat(),
                "date_fin_essai": (
                    abonnement.date_fin_essai.isoformat() if abonnement.date_fin_essai else None
                ),
            }
            if abonnement
            else None
        )
        return ligne

    # ─────────────────────────────────────────────────────────────────────────
    # Modification
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def modifier(
        platform_db: AsyncSession,
        master_db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        nom: Optional[str] = None,
        ninea: Optional[str] = None,
        adresse_siege: Optional[str] = None,
        ville: Optional[str] = None,
        telephone: Optional[str] = None,
        email: Optional[str] = None,
        site_web: Optional[str] = None,
        pays: Optional[str] = None,
        langue: Optional[str] = None,
        fuseau_horaire: Optional[str] = None,
        devise: Optional[str] = None,
        logo_url: Optional[str] = None,
        auteur: str = "système",
        motif: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        dossier = await TenantService._charger_dossier(platform_db, tenant_id)
        societe = (
            await master_db.execute(select(Societe).where(Societe.id == tenant_id))
        ).scalar_one_or_none()
        if societe is None:
            raise EntityNotFoundException("Cabinet", tenant_id)

        avant = _vers_ligne(dossier, societe, None)
        champs_societe = {
            "nom": nom,
            "ninea": ninea,
            "adresse_siege": adresse_siege,
            "ville": ville,
            "telephone": telephone,
            "email": email,
            "site_web": site_web,
            "logo_url": logo_url,
        }
        for champ, valeur in champs_societe.items():
            if valeur is not None:
                setattr(societe, champ, str(valeur) if champ == "email" else valeur)

        champs_dossier = {"pays": pays, "langue": langue, "fuseau_horaire": fuseau_horaire, "devise": devise}
        for champ, valeur in champs_dossier.items():
            if valeur is not None:
                setattr(dossier, champ, valeur)

        await platform_db.flush()
        await master_db.flush()

        from src.modules.platform.services.journal import JournalService

        await JournalService.journaliser(
            platform_db,
            action="PLATFORM_TENANT_MODIFIE",
            type_cible="TENANT",
            cible_id=str(tenant_id),
            tenant_id=tenant_id,
            acteur_email=auteur,
            avant={k: v for k, v in avant.items() if k in ("nom", "ville", "telephone", "email", "devise", "langue")},
            apres={
                k: v
                for k, v in _vers_ligne(dossier, societe, None).items()
                if k in ("nom", "ville", "telephone", "email", "devise", "langue")
            },
            motif=motif,
            ip_address=client_ip,
        )
        return await TenantService.detail(platform_db, master_db, tenant_id)

    # ─────────────────────────────────────────────────────────────────────────
    # Machine à états
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def changer_statut(
        platform_db: AsyncSession,
        master_db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        cible: StatutTenant,
        motif: str,
        auteur: str,
        client_ip: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fait passer un cabinet d'un statut à l'autre, avec motif obligatoire.

        Pose le statut métier (base plateforme) ET le statut technique
        (base master, `tenants_db.statut`) : c'est ce second levier que lisent
        réellement `get_tenant_db()` et la résolution du login client, donc
        l'oublier laisserait le cabinet connecté.
        """
        dossier = await TenantService._charger_dossier(platform_db, tenant_id)
        actuel = dossier.statut_metier

        if actuel == cible:
            raise InvalidTransitionException(
                actuel.value,
                cible.value,
                "le cabinet est déjà dans cet état",
                transitions_possibles(actuel),
            )

        autorisees = TRANSITIONS_AUTORISEES.get(actuel, [])
        if cible not in autorisees:
            raison = (
                f"depuis l'état terminal '{actuel.value}', aucune transition n'est possible"
                if not autorisees
                else f"transitions possibles : {', '.join(transitions_possibles(actuel))}"
            )
            raise InvalidTransitionException(
                actuel.value, cible.value, raison, transitions_possibles(actuel)
            )

        # Lever technique
        tenant_db = (
            await master_db.execute(select(TenantDB).where(TenantDB.societe_id == tenant_id))
        ).scalar_one_or_none()
        if tenant_db is None:
            raise EntityNotFoundException("Dossier de base du cabinet", tenant_id)

        dossier.statut_metier = cible
        dossier.motif_statut = motif
        maintenant = _maintenant()
        if cible == StatutTenant.ACTIF:
            dossier.date_activation = maintenant
            dossier.date_suspension = None
        elif cible == StatutTenant.SUSPENDU:
            dossier.date_suspension = maintenant
        elif cible == StatutTenant.RESILIE:
            dossier.date_resiliation = maintenant

        tenant_db.statut = STATUT_TECHNIQUE_MASTER[cible]

        platform_db.add(
            StatutTenantHistorique(
                tenant_id=tenant_id,
                statut_precedent=actuel.value,
                statut_nouveau=cible.value,
                motif=motif,
                auteur_email=auteur,
                ip_address=client_ip,
                request_id=request_id,
            )
        )

        from src.modules.platform.services.journal import JournalService

        await JournalService.journaliser(
            platform_db,
            action=f"PLATFORM_TENANT_{cible.value}",
            type_cible="TENANT",
            cible_id=str(tenant_id),
            tenant_id=tenant_id,
            acteur_email=auteur,
            avant={"statut": actuel.value},
            apres={"statut": cible.value, "statut_technique": tenant_db.statut},
            motif=motif,
            ip_address=client_ip,
            request_id=request_id,
        )

        await platform_db.flush()
        await master_db.flush()

        # Une résiliation ou une suspension doit couper l'accès immédiatement :
        # les sessions ouvertes portent un jeton déjà valide.
        if cible in (StatutTenant.SUSPENDU, StatutTenant.RESILIE):
            await TenantService._revoquer_sessions_tenants(tenant_id)

        logger.info(
            "tenant_statut_change",
            tenant_id=str(tenant_id),
            avant=actuel.value,
            apres=cible.value,
            motif=motif,
            auteur=auteur,
        )
        return await TenantService.detail(platform_db, master_db, tenant_id)

    @staticmethod
    async def _revoquer_sessions_tenants(tenant_id: uuid.UUID) -> None:
        """
        Marque révoquées les sessions ouvertes dans la base du cabinet.

        Suspendre un cabinet sans couper ses sessions laisserait un utilisateur
        connecté jusqu'à l'expiration de son jeton — jusqu'à 15 minutes d'accès
        à des données de santé sur un compte qu'on vient de suspendre.
        """
        from src.core.database import tenant_db_manager
        from src.modules.tenants.models import SessionUser

        sessions: List[Any] = []
        try:
            factory = await tenant_db_manager.get_session_factory(str(tenant_id))
        except Exception:  # noqa: BLE001 - la base peut être injoignable
            logger.warning("sessions_tenant_non_revoquees", tenant_id=str(tenant_id))
            return
        async with factory() as session:
            sessions = list(
                (
                    await session.execute(
                        select(SessionUser).where(SessionUser.est_revoque.is_(False))
                    )
                ).scalars().all()
            )
            for entree in sessions:
                entree.est_revoque = True
            await session.commit()
        logger.info(
            "sessions_tenant_revoquees", tenant_id=str(tenant_id), nombre=len(sessions)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Archivage
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def archiver(
        platform_db: AsyncSession,
        master_db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        archiver: bool,
        motif: str,
        auteur: str,
        client_ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Archivage LOGIQUE : le cabinet disparaît du registre actif mais toutes
        ses données restent. Aucun tenant n'est supprimé par cette opération —
        la suppression définitive est une autre route, avec ses propres verrous.
        """
        dossier = await TenantService._charger_dossier(platform_db, tenant_id)
        avant = dossier.archivable
        dossier.archivable = archiver

        from src.modules.platform.services.journal import JournalService

        await JournalService.journaliser(
            platform_db,
            action="PLATFORM_TENANT_ARCHIVE" if archiver else "PLATFORM_TENANT_DESHARCHIVE",
            type_cible="TENANT",
            cible_id=str(tenant_id),
            tenant_id=tenant_id,
            acteur_email=auteur,
            avant={"archivable": avant},
            apres={"archivable": archiver},
            motif=motif,
            ip_address=client_ip,
        )
        await platform_db.flush()
        return await TenantService.detail(platform_db, master_db, tenant_id)

    # ─────────────────────────────────────────────────────────────────────────
    # Historique
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def historique(
        platform_db: AsyncSession, tenant_id: uuid.UUID, limit: int = 50
    ) -> List[StatutTenantHistorique]:
        stmt = (
            select(StatutTenantHistorique)
            .where(StatutTenantHistorique.tenant_id == tenant_id)
            .order_by(StatutTenantHistorique.timestamp.desc())
            .limit(limit)
        )
        return list((await platform_db.execute(stmt)).scalars().all())

    # ─────────────────────────────────────────────────────────────────────────
    # Expiration d'essai (job planifié, Phase F.2)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def expirer_essais(
        platform_db: AsyncSession, master_db: AsyncSession, action: str = "suspend"
    ) -> List[uuid.UUID]:
        """
        Bascule les cabinets dont l'essai est terminé.

        La règle est configurable (`ONBOARDING_ESSAI_EXPIRE_ACTION`) parce que les
        deux contrôles ont des conséquences opposées : suspendre laisse les
        données intactes et récupérables, résilier ferme le dossier. On ne peut
        pas choisir à la place du client.
        """
        aujourdhui = date.today()
        stmt = select(TenantPlateforme).where(
            TenantPlateforme.statut_metier == StatutTenant.ESSAI,
            TenantPlateforme.date_fin_essai.is_not(None),
            TenantPlateforme.date_fin_essai < aujourdhui,
        )
        dossiers = (await platform_db.execute(stmt)).scalars().all()

        traites: List[uuid.UUID] = []
        for dossier in dossiers:
            cible = (
                StatutTenant.SUSPENDU if action == "suspend" else StatutTenant.RESILIE
            )
            motif = (
                "Période d'essai terminée — accès suspendu"
                if cible == StatutTenant.SUSPENDU
                else "Période d'essai terminée — dossier clôturé"
            )
            try:
                await TenantService.changer_statut(
                    platform_db,
                    master_db,
                    dossier.tenant_id,
                    cible=cible,
                    motif=motif,
                    auteur="job:expiration-essai",
                )
                traites.append(dossier.tenant_id)
            except InvalidTransitionException:
                logger.info(
                    "essai_expiration_ignoree",
                    tenant_id=str(dossier.tenant_id),
                    statut=dossier.statut_metier.value,
                )
        return traites


def _vers_ligne(
    dossier: Optional[TenantPlateforme], societe: Societe, tenant_db: Optional[TenantDB]
) -> Dict[str, Any]:
    """Projection commune au registre et au détail."""
    return {
        "tenant_id": str(societe.id),
        "nom": societe.nom,
        "ville": societe.ville,
        "pays": dossier.pays if dossier else societe.pays,
        "telephone": societe.telephone,
        "email": societe.email,
        "statut": dossier.statut_metier.value if dossier else "INCONNU",
        "statut_technique": tenant_db.statut if tenant_db else None,
        "archivable": dossier.archivable if dossier else False,
        "langue": dossier.langue if dossier else "fr",
        "devise": dossier.devise if dossier else "XOF",
        "fuseau_horaire": dossier.fuseau_horaire if dossier else "Africa/Dakar",
        "date_creation": societe.created_at.isoformat() if societe.created_at else None,
        "date_debut_essai": (
            dossier.date_debut_essai.isoformat() if dossier and dossier.date_debut_essai else None
        ),
        "date_fin_essai": (
            dossier.date_fin_essai.isoformat() if dossier and dossier.date_fin_essai else None
        ),
        "db_name": tenant_db.db_name if tenant_db else None,
        "transitions_possibles": transitions_possibles(dossier.statut_metier) if dossier else [],
    }