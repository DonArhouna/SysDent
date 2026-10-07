"""
Clôture de caisse.

Une session de caisse est la journée de travail d'un caissier : il ouvre le
tiroir en annonçant les espèces dont il dispose, encaisse, puis clôture en
annonçant ce qu'il a compté.

Ce que le journal de caisse n'apportait pas :

- une **borne temporelle** qui rend le rapport de journée reproductible ;
- des **totaux par mode figés** à la clôture — un paiement saisi après coup ne
  réécrit pas une journée close, sinon le chiffre du mois change sous les yeux
  du comptable et personne ne sait ce qui a été constaté ;
- un **écart de caisse** annoncé et motivé, qui est la signature de la clôture.

Le montant d'espèces attendu au tiroir est la somme de deux choses :

    attendu = dépôt d'ouverture + encaissements en espèces de la session

Un écart n'est pas une faute : c'est un fait. Un caissier qui déclare 47 000
pour 47 500 attendus n'a pas forcément volé — il a peut-être rendu de la monnaie,
ou mal compté. Ce qui compte est que l'écart soit **écrit, motivé et signé**,
pas qu'il soit nul.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.tenants.models import (
    Facture,
    ModePaiementEnum,
    Paiement,
    SessionCaisse,
    StatutSessionCaisseEnum,
    Utilisateur,
)

ZERO = Decimal("0.00")


def _quantize(valeur: Decimal) -> Decimal:
    return Decimal(valeur).quantize(Decimal("0.01"))


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class CaisseService:
    # Mode de paiement -> colonne de total figé à la clôture.
    COLONNES_TOTAL: Dict[ModePaiementEnum, str] = {
        ModePaiementEnum.ESPECES: "total_especes",
        ModePaiementEnum.CARTE_BANCAIRE: "total_carte",
        ModePaiementEnum.VIREMENT: "total_virement",
        ModePaiementEnum.MOBILE_MONEY: "total_mobile_money",
        ModePaiementEnum.CHEQUE: "total_cheque",
        ModePaiementEnum.ASSURANCE: "total_assurance",
    }

    # ------------------------------------------------------------------ ouverture

    @staticmethod
    async def session_ouverte(
        db: AsyncSession, cabinet_id: uuid.UUID
    ) -> Optional[SessionCaisse]:
        return (
            await db.execute(
                select(SessionCaisse).where(
                    SessionCaisse.cabinet_id == cabinet_id,
                    SessionCaisse.statut == StatutSessionCaisseEnum.OUVERTE,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def exiger_session_ouverte(
        db: AsyncSession, cabinet_id: uuid.UUID
    ) -> SessionCaisse:
        """
        Rend la session ouverte, ou refuse l'encaissement.

        Refuser est un choix : une caisse qui accepte de l'argent hors de toute
        session produit un rapport journalier faux, et rien dans l'écran ne le
        signale. Mieux vaut un encaissement bloqué avec un message qui explique
        quoi faire qu'une somme d'argent introuvable le soir.
        """
        session = await CaisseService.session_ouverte(db, cabinet_id)
        if session is None:
            raise BusinessRuleViolationException(
                "Aucune session de caisse n'est ouverte : ouvrez la caisse "
                "avant d'encaisser.",
                code="AUCUNE_SESSION_CAISSE",
            )
        return session

    @staticmethod
    async def ouvrir(
        db: AsyncSession,
        *,
        cabinet_id: uuid.UUID,
        ouverture_especes: Decimal = ZERO,
        auteur: Optional[Utilisateur] = None,
        notes: Optional[str] = None,
    ) -> SessionCaisse:
        """Ouvre la session du jour, avec le dépôt d'espèces du tiroir."""
        if (await CaisseService.session_ouverte(db, cabinet_id)) is not None:
            raise BusinessRuleViolationException(
                "Une session de caisse est déjà ouverte. Clôturez-la avant d'en ouvrir une autre.",
                code="SESSION_DEJA_OUVERTE",
            )

        total = await db.scalar(select(func.count()).select_from(SessionCaisse)) or 0
        session = SessionCaisse(
            numero=f"Z-{datetime.now().year}-{(total + 1):05d}",
            cabinet_id=cabinet_id,
            statut=StatutSessionCaisseEnum.OUVERTE,
            ouverture_especes=_quantize(ouverture_especes),
            ouverte_par_id=auteur.id if auteur else None,
            ouverte_par_email=auteur.email if auteur else None,
            notes=notes,
        )
        db.add(session)
        try:
            await db.commit()
        except IntegrityError:
            # L'index unique partiel refuse deux sessions ouvertes pour un même
            # cabinet. On ne laisse pas remonter une erreur d'infrastructure
            # brute : c'est une règle métier, elle a son message.
            await db.rollback()
            raise BusinessRuleViolationException(
                "Une session de caisse est déjà ouverte pour ce cabinet.",
                code="SESSION_DEJA_OUVERTE",
            )
        return await CaisseService.obtenir(db, session.id)

    # ------------------------------------------------------------------ clôture

    @staticmethod
    async def cloturer(
        db: AsyncSession,
        session_id: uuid.UUID,
        *,
        especes_comptees: Decimal,
        auteur: Optional[Utilisateur] = None,
        motif_ecart: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> SessionCaisse:
        """
        Clôture la session : fige les totaux par mode et calcule l'écart.

        Les totaux sont **recopiés dans la session** et non recalculés à la
        lecture. Un paiement enregistré plus tard sur cette journée ne les
        modifiera pas : le rapport reste ce qui a été constaté au moment de la
        clôture, et c'est le seul rapport qui vaille comme pièce comptable.
        """
        session = await CaisseService.obtenir(db, session_id)

        if session.statut is not StatutSessionCaisseEnum.OUVERTE:
            raise BusinessRuleViolationException(
                f"La session {session.numero} est déjà close.",
                code="SESSION_DEJA_CLOSE",
            )

        lignes = (
            await db.execute(
                select(Paiement.mode, func.sum(Paiement.montant), func.count())
                .where(Paiement.session_caisse_id == session.id)
                .group_by(Paiement.mode)
            )
        ).all()

        totaux: Dict[str, Decimal] = {c: ZERO for c in CaisseService.COLONNES_TOTAL.values()}
        nb = 0
        for mode, somme, effectif in lignes:
            colonne = CaisseService.COLONNES_TOTAL.get(mode)
            if colonne is None:
                # Un mode du catalogue sans colonne de total produirait un
                # rapport de journée faux **sans aucun signal** : c'est le pire
                # défaut comptable qui soit. On refuse la clôture plutot que de
                # déclarer un total qui ment.
                raise BusinessRuleViolationException(
                    f"Le mode de paiement {mode.value} n'est pas pris en charge "
                    "par la clôture de caisse.",
                    code="MODE_PAIEMENT_NON_CLOTURABLE",
                    details={"mode": mode.value},
                )
            totaux[colonne] = _quantize(somme or ZERO)
            nb += int(effectif or 0)

        comptees = _quantize(especes_comptees)
        if comptees < ZERO:
            raise BusinessRuleViolationException(
                "Le comptage d'espèces ne peut pas être négatif.",
                code="COMPTEAGE_NEGATIF",
            )

        attendues = _quantize(session.ouverture_especes + totaux["total_especes"])

        session.total_especes = totaux["total_especes"]
        session.total_carte = totaux["total_carte"]
        session.total_virement = totaux["total_virement"]
        session.total_mobile_money = totaux["total_mobile_money"]
        session.total_cheque = totaux["total_cheque"]
        session.total_assurance = totaux["total_assurance"]
        session.nb_paiements = nb
        session.especes_comptees = comptees
        session.ecart_especes = _quantize(comptees - attendues)
        session.close_le = _maintenant()
        session.close_par_id = auteur.id if auteur else None
        session.close_par_email = auteur.email if auteur else None
        session.statut = StatutSessionCaisseEnum.CLOSE
        if motif_ecart:
            session.motif_ecart = motif_ecart.strip() or None
        if notes:
            session.notes = notes.strip() or None

        await db.commit()
        return await CaisseService.obtenir(db, session_id)

    # ------------------------------------------------------------------ lecture

    @staticmethod
    async def obtenir(db: AsyncSession, session_id: uuid.UUID) -> SessionCaisse:
        session = (
            await db.execute(
                select(SessionCaisse).where(SessionCaisse.id == session_id)
            )
        ).scalar_one_or_none()
        if session is None:
            raise EntityNotFoundException("Session de caisse", session_id)
        return session

    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        cabinet_id: Optional[uuid.UUID] = None,
        statut: Optional[StatutSessionCaisseEnum] = None,
        limit: int = 50,
    ) -> List[SessionCaisse]:
        stmt = select(SessionCaisse)
        if cabinet_id:
            stmt = stmt.where(SessionCaisse.cabinet_id == cabinet_id)
        if statut:
            stmt = stmt.where(SessionCaisse.statut == statut)
        return list(
            (
                await db.execute(
                    stmt.order_by(SessionCaisse.ouverte_le.desc()).limit(limit)
                )
            ).scalars()
            .all()
        )

    @staticmethod
    async def paiements(
        db: AsyncSession, session_id: uuid.UUID, *, limit: int = 100
    ) -> List[Paiement]:
        return list(
            (
                await db.execute(
                    select(Paiement)
                    .where(Paiement.session_caisse_id == session_id)
                    .order_by(Paiement.date_paiement.desc())
                    .limit(limit)
                )
            )
            .unique()
            .scalars()
            .all()
        )

    @staticmethod
    async def paiements_hors_session(
        db: AsyncSession, *, cabinet_id: uuid.UUID, limit: int = 100
    ) -> List[Paiement]:
        """
        Encaissements faits sans session ouverte, sur un site donné.

        Ils existent pour les paiements antérieurs au déploiement des sessions,
        et parce qu'une base peut avoir été alimentée autrement. Les lister
        n'est pas les cacher : un montant qui n'entre dans aucune clôture est un
        montant dont personne ne répond.

        Le site passe par la facture : `paiements` ne porte pas de `cabinet_id`.
        Un cabinet multi-sites ne doit pas voir les encaissements orphelins de
        ses autres sites.
        """
        return list(
            (
                await db.execute(
                    select(Paiement)
                    .join(Facture, Paiement.facture_id == Facture.id)
                    .where(
                        Paiement.session_caisse_id.is_(None),
                        Facture.cabinet_id == cabinet_id,
                    )
                    .order_by(Paiement.date_paiement.desc())
                    .limit(limit)
                )
            )
            .unique()
            .scalars()
            .all()
        )
