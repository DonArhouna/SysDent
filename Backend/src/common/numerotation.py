"""
Génération atomique des numéros d'identifiants métier (RG01, RG08).

Les compteurs vivent dans la base du cabinet (Tenant), donc deux cabinets
numérotent indépendamment et sans collision entre eux.

Atomicité : on s'appuie sur `INSERT ... ON CONFLICT DO UPDATE ... RETURNING`
qui est exécuté par PostgreSQL sous Row-Level Lock. Deux requêtes concurrentes
ne peuvent donc pas lire le même compteur : la seconde attend la fin de la
première transaction. `SELECT MAX(...) + 1` ne conviendrait pas (course entre
deux lectures sur deux transactions distinctes).
"""

import re
from datetime import date
from typing import Optional
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Format du numéro de dossier patient : PAT-2026-000001 (RG01)
PATIENT_DOSSIER_PREFIX = "PAT"
# Préfixe des numérotation de documents financiers et commerciaux.
FACTURE_PREFIX = "FAC"
PAIEMENT_RECEIPT_PREFIX = "RECU"
DEVIS_PREFIX = "DEV"
COMMANDE_PREFIX = "BC"
ORDONNANCE_PREFIX = "ORD"

_PATIENT_DOSSIER_RE = re.compile(r"^PAT-(\d{4})-(\d{6})$")
_FACTURE_RE = re.compile(r"^FAC-(\d{4})-(\d{5})$")


async def _next_counter_value(db: AsyncSession, compteur: str, year: int) -> int:
    """
    Incrémente le compteur `compteur` pour l'année `year` et retourne la valeur
    obtenue. L'upsert est atomique au niveau PostgreSQL.
    """
    stmt = text(
        """
        INSERT INTO compteurs (compteur, annee, valeur, updated_at)
        VALUES (:compteur, :annee, 1, NOW())
        ON CONFLICT (compteur, annee)
        DO UPDATE SET valeur = compteurs.valeur + 1, updated_at = NOW()
        RETURNING valeur
        """
    )
    result = await db.execute(stmt, {"compteur": compteur, "annee": year})
    return int(result.scalar_one())


async def generer_numero_dossier_patient(
    db: AsyncSession,
    date_reference: Optional[date] = None,
) -> str:
    """
    Génère le numéro de dossier unique d'un patient (RG01).

    Format : PAT-2026-000001, remis à zéro chaque année civile.

    Note : le verrou est détenu jusqu'au COMMIT. L'appelant doit donc valider
    (commit) la transaction qui suit immédiatement, sans requête métier longue
    en.files d'attente, sinon le compteur reste bloqué pour les autres.
    """
    annee = (date_reference or date.today()).year
    valeur = await _next_counter_value(db, "PATIENT_DOSSIER", annee)
    numero = f"{PATIENT_DOSSIER_PREFIX}-{annee}-{valeur:06d}"
    logger.info("numero_dossier_genere", numero=numero, annee=annee)
    return numero


async def generer_numero_facture(db: AsyncSession, date_reference: Optional[date] = None) -> str:
    """Génère un numéro de facture : FAC-2026-00001 (MLD §4.8)."""
    annee = (date_reference or date.today()).year
    valeur = await _next_counter_value(db, "FACTURE", annee)
    return f"{FACTURE_PREFIX}-{annee}-{valeur:05d}"


async def generer_numero_recu_paiement(
    db: AsyncSession, date_reference: Optional[date] = None
) -> str:
    """
    Génère le numéro de reçu de caisse (unique, base-wide du cabinet).

    Les reçus sont journaliers et non annuels : le CDC impose une numérotation
    continue par jour pour la caisse, ce qui simplifie le rapprochement en fin
    de journée. Format : RECU-20260913-0001.
    """
    jour = (date_reference or date.today()).strftime("%Y%m%d")
    valeur = await _next_counter_value(db, f"RECU_{jour}", 0)
    return f"{PAIEMENT_RECEIPT_PREFIX}-{jour}-{valeur:04d}"


async def generer_numero_devis(db: AsyncSession, date_reference: Optional[date] = None) -> str:
    """Génère un numéro de devis : DEV-2026-00001."""
    annee = (date_reference or date.today()).year
    valeur = await _next_counter_value(db, "DEVIS", annee)
    return f"{DEVIS_PREFIX}-{annee}-{valeur:05d}"


async def generer_numero_bon_commande(
    db: AsyncSession, date_reference: Optional[date] = None
) -> str:
    """Génère un numéro de bon de commande fournisseur : BC-2026-00001."""
    annee = (date_reference or date.today()).year
    valeur = await _next_counter_value(db, "COMMANDE_FOURNISSEUR", annee)
    return f"{COMMANDE_PREFIX}-{annee}-{valeur:05d}"


async def generer_numero_ordonnance(
    db: AsyncSession, date_reference: Optional[date] = None
) -> str:
    """
    Génère un numéro d'ordonnance : ORD-2026-00001.

    L'ordonnance est un acte médical signé : sa numérotation doit être
    continue et sans trou sur l'année, comme celle d'une facture.
    """
    annee = (date_reference or date.today()).year
    valeur = await _next_counter_value(db, "ORDONNANCE", annee)
    return f"{ORDONNANCE_PREFIX}-{annee}-{valeur:05d}"
