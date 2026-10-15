"""
Agenda de l'équipe éditrice : rendez-vous avec les cabinets et les prospects.

Règles :

- un rendez-vous concerne **un cabinet client OU un prospect** (nom libre),
  jamais les deux, jamais aucun ;
- un agent ne peut pas avoir deux rendez-vous actifs (non annulés) qui se
  chevauchent : le serveur refuse en disant avec quoi ;
- annuler exige un motif ; un rendez-vous effectué ou annulé ne se modifie plus ;
- le contact peut être prévenu par e-mail (création, modification, annulation) ;
- chaque écriture est inscrite au journal d'audit de la console.

**Aucune donnée patient** : les rendez-vous des patients restent dans la base
de chaque cabinet.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.platform.models import RendezVousPlateforme, UtilisateurPlateforme
from src.modules.platform.services.journal import JournalService

logger = structlog.get_logger(__name__)

TYPES = ("DEMO", "INSTALLATION", "FORMATION", "SUPPORT", "COMMERCIAL", "AUTRE")
STATUTS = ("PLANIFIE", "CONFIRME", "EFFECTUE", "ANNULE")
TERMINAUX = ("EFFECTUE", "ANNULE")

LIBELLES_TYPES = {
    "DEMO": "Démonstration",
    "INSTALLATION": "Installation",
    "FORMATION": "Formation",
    "SUPPORT": "Support",
    "COMMERCIAL": "Rendez-vous commercial",
    "AUTRE": "Rendez-vous",
}

CHAMPS_MODIFIABLES = (
    "titre", "type_rdv", "debut", "duree_minutes", "tenant_id", "prospect_nom",
    "contact_nom", "contact_email", "contact_telephone", "lieu", "lien_visio", "agent_id", "notes",
)


def _fin(rdv: RendezVousPlateforme) -> datetime:
    return rdv.debut + timedelta(minutes=rdv.duree_minutes)


def _horodatage(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%d/%m/%Y à %H:%M (UTC)")


class AgendaService:
    @staticmethod
    def _verifier(rdv: RendezVousPlateforme) -> None:
        if rdv.type_rdv not in TYPES:
            raise BusinessRuleViolationException(f"Type inconnu : {rdv.type_rdv}.", code="TYPE_RDV_INCONNU")
        a_cabinet = rdv.tenant_id is not None
        a_prospect = bool((rdv.prospect_nom or "").strip())
        if a_cabinet == a_prospect:
            raise BusinessRuleViolationException(
                "Indiquez soit un cabinet client, soit le nom d'un prospect.", code="RDV_CIBLE_INVALIDE"
            )
        if not 5 <= rdv.duree_minutes <= 600:
            raise BusinessRuleViolationException("Durée entre 5 minutes et 10 heures.", code="RDV_DUREE_INVALIDE")

    @staticmethod
    async def _verifier_disponibilite(db: AsyncSession, rdv: RendezVousPlateforme) -> None:
        """Un agent, un seul rendez-vous actif à la fois."""
        if rdv.agent_id is None or rdv.statut in TERMINAUX:
            return
        fin = _fin(rdv)
        conflit = (
            await db.execute(
                select(RendezVousPlateforme).where(
                    RendezVousPlateforme.agent_id == rdv.agent_id,
                    RendezVousPlateforme.statut.notin_(TERMINAUX),
                    RendezVousPlateforme.id != rdv.id,
                    RendezVousPlateforme.debut < fin,
                    RendezVousPlateforme.debut
                    + func.make_interval(0, 0, 0, 0, 0, RendezVousPlateforme.duree_minutes)
                    > rdv.debut,
                )
            )
        ).scalars().first()
        if conflit is not None:
            raise BusinessRuleViolationException(
                f"L'agent a déjà « {conflit.titre} » le {_horodatage(conflit.debut)}.",
                code="RDV_CONFLIT_AGENT",
                details={"rendez_vous_id": str(conflit.id)},
            )

    @staticmethod
    async def _notifier(rdv: RendezVousPlateforme, evenement: str, nom_cible: Optional[str]) -> bool:
        if not rdv.contact_email:
            return False
        from src.modules.platform.services.notifications import EmailService

        return await EmailService.rendez_vous_contact(
            destinataire=rdv.contact_email,
            evenement=evenement,
            titre=rdv.titre,
            type_libelle=LIBELLES_TYPES.get(rdv.type_rdv, "Rendez-vous"),
            quand=_horodatage(rdv.debut),
            duree=rdv.duree_minutes,
            lieu=rdv.lieu,
            lien_visio=rdv.lien_visio,
            avec=nom_cible,
            motif_annulation=rdv.motif_annulation,
        )

    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        du: Optional[datetime] = None,
        au: Optional[datetime] = None,
        agent_id: Optional[uuid.UUID] = None,
        tenant_id: Optional[uuid.UUID] = None,
        statut: Optional[str] = None,
        type_rdv: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Tuple[List[RendezVousPlateforme], int]:
        conditions = []
        if du is not None:
            conditions.append(RendezVousPlateforme.debut >= du)
        if au is not None:
            conditions.append(RendezVousPlateforme.debut < au)
        if agent_id is not None:
            conditions.append(RendezVousPlateforme.agent_id == agent_id)
        if tenant_id is not None:
            conditions.append(RendezVousPlateforme.tenant_id == tenant_id)
        if statut:
            conditions.append(RendezVousPlateforme.statut == statut)
        if type_rdv:
            conditions.append(RendezVousPlateforme.type_rdv == type_rdv)
        filtre = and_(*conditions) if conditions else True
        total = (await db.execute(select(func.count()).select_from(RendezVousPlateforme).where(filtre))).scalar_one()
        lignes = (
            await db.execute(
                select(RendezVousPlateforme).where(filtre).order_by(RendezVousPlateforme.debut).limit(limit).offset(offset)
            )
        ).scalars().all()
        return list(lignes), int(total)

    @staticmethod
    async def obtenir(db: AsyncSession, rdv_id: uuid.UUID) -> RendezVousPlateforme:
        rdv = await db.get(RendezVousPlateforme, rdv_id)
        if rdv is None:
            raise EntityNotFoundException("Rendez-vous", str(rdv_id))
        return rdv

    @staticmethod
    async def creer(
        db: AsyncSession, donnees: Dict[str, Any], auteur: UtilisateurPlateforme, nom_cible: Optional[str], notifier: bool
    ) -> Tuple[RendezVousPlateforme, bool]:
        rdv = RendezVousPlateforme(**{k: donnees.get(k) for k in CHAMPS_MODIFIABLES}, statut="PLANIFIE", cree_par=auteur.email)
        if rdv.duree_minutes is None:
            rdv.duree_minutes = 60
        rdv.id = uuid.uuid4()
        AgendaService._verifier(rdv)
        await AgendaService._verifier_disponibilite(db, rdv)
        db.add(rdv)
        await JournalService.journaliser(
            db, action="PLATFORM_RDV_CREE", type_cible="RENDEZ_VOUS", cible_id=str(rdv.id),
            tenant_id=rdv.tenant_id, acteur_email=auteur.email, acteur_id=auteur.id,
            apres={"titre": rdv.titre, "type": rdv.type_rdv, "debut": rdv.debut.isoformat()},
        )
        await db.commit()
        envoye = await AgendaService._notifier(rdv, "cree", nom_cible) if notifier else False
        return rdv, envoye

    @staticmethod
    async def modifier(
        db: AsyncSession, rdv_id: uuid.UUID, changements: Dict[str, Any], auteur: UtilisateurPlateforme,
        nom_cible: Optional[str], notifier: bool,
    ) -> Tuple[RendezVousPlateforme, bool]:
        rdv = await AgendaService.obtenir(db, rdv_id)
        if rdv.statut in TERMINAUX:
            raise BusinessRuleViolationException(
                "Un rendez-vous effectué ou annulé ne se modifie plus.", code="RDV_TERMINE"
            )
        avant = {k: str(getattr(rdv, k)) for k in changements if k in CHAMPS_MODIFIABLES}
        for cle, valeur in changements.items():
            if cle in CHAMPS_MODIFIABLES:
                setattr(rdv, cle, valeur)
        # Basculer de cabinet à prospect (ou l'inverse) : l'autre champ se vide.
        if "tenant_id" in changements and changements["tenant_id"] is not None:
            rdv.prospect_nom = None
        if changements.get("prospect_nom"):
            rdv.tenant_id = None
        AgendaService._verifier(rdv)
        await AgendaService._verifier_disponibilite(db, rdv)
        await JournalService.journaliser(
            db, action="PLATFORM_RDV_MODIFIE", type_cible="RENDEZ_VOUS", cible_id=str(rdv.id),
            tenant_id=rdv.tenant_id, acteur_email=auteur.email, acteur_id=auteur.id,
            avant=avant, apres={k: str(getattr(rdv, k)) for k in avant},
        )
        await db.commit()
        horaire_change = bool({"debut", "duree_minutes", "lieu", "lien_visio"} & set(changements))
        envoye = await AgendaService._notifier(rdv, "modifie", nom_cible) if notifier and horaire_change else False
        return rdv, envoye

    @staticmethod
    async def changer_statut(
        db: AsyncSession, rdv_id: uuid.UUID, statut: str, motif: Optional[str], auteur: UtilisateurPlateforme,
        nom_cible: Optional[str], notifier: bool,
    ) -> Tuple[RendezVousPlateforme, bool]:
        if statut not in STATUTS:
            raise BusinessRuleViolationException(f"Statut inconnu : {statut}.", code="STATUT_RDV_INCONNU")
        rdv = await AgendaService.obtenir(db, rdv_id)
        if rdv.statut in TERMINAUX:
            raise BusinessRuleViolationException(
                "Un rendez-vous effectué ou annulé ne change plus de statut.", code="RDV_TERMINE"
            )
        if statut == "ANNULE" and len((motif or "").strip()) < 5:
            raise BusinessRuleViolationException("L'annulation exige un motif.", code="MOTIF_REQUIS")
        avant = rdv.statut
        rdv.statut = statut
        if statut == "ANNULE":
            rdv.motif_annulation = motif.strip()
        await JournalService.journaliser(
            db, action="PLATFORM_RDV_STATUT", type_cible="RENDEZ_VOUS", cible_id=str(rdv.id),
            tenant_id=rdv.tenant_id, acteur_email=auteur.email, acteur_id=auteur.id,
            avant={"statut": avant}, apres={"statut": statut}, motif=motif,
        )
        await db.commit()
        envoye = (
            await AgendaService._notifier(rdv, "annule", nom_cible) if notifier and statut == "ANNULE" else False
        )
        return rdv, envoye
