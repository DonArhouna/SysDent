"""
Points d'intégration des quotas et feature flags dans l'application CLIENTE.

`QuotaService` (dans `services/quotas.py`) est la logique. Ce module est le
**pont FastAPI** : des dépendances prêtes à `Depends(...)` que les routes
client appellent sans connaître la base plateforme.

Pourquoi un module séparé et non une dépendance dans chaque route cliente :

- Une application cliente qui oublie le quota sur UNE route de création est un
  client facturé au-delà de son contrat. Le garde-fou doit être une dépendance
  déclarative, reproductible d'un module à l'autre, pas un bloc de code recopié.
- L'application cliente ne doit RIEN importer de la couche métier plateforme
  (`services/plans.py`, `provisionning.py`…). Elle n'a besoin que de « cette
  action tient-elle dans le contrat ? ».
- Aucun `JOIN` entre les deux bases n'est possible : la vérification lit le plan
  dans `sysdent_platform`, le décompte dans la base du cabinet. Les deux
  sessions sont ouvertes indépendamment.

Usage typique dans une route cliente :

    @router.post("/praticiens", ...)
    async def creer_praticien(
        request: Request,
        db: AsyncSession = Depends(get_tenant_db),
        _qte: None = Depends(quota("praticiens", lambda db, u: compter_praticiens(db))),
    ):
        ...
"""

from typing import Awaitable, Callable, Optional

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.dependencies import get_current_tenant_id, get_tenant_db
from src.modules.platform.services.quotas import LIBELLES_RESSOURCES, QuotaService

#: Signature d'un compteur de consommation : reçoit la session du CABINET et le
#: tenant, et renvoie le nombre d'objets déjà créés.
Compteur = Callable[[AsyncSession, str], Awaitable[int]]


async def _compter_utilisateurs(db: AsyncSession, tenant_id: str) -> int:
    """Comptage des comptes du cabinet (table `utilisateurs` de SA base)."""
    from src.modules.tenants.models import Utilisateur

    return (
        await db.execute(select(func.count()).select_from(Utilisateur).where(Utilisateur.actif.is_(True)))
    ).scalar_one()


async def _compter_praticiens(db: AsyncSession, tenant_id: str) -> int:
    from src.modules.tenants.models import Praticien

    return (await db.execute(select(func.count()).select_from(Praticien))).scalar_one()


async def _compter_sites(db: AsyncSession, tenant_id: str) -> int:
    """
    Un « site » commercial = un cabinet physique. La table `cabinets` en porte
    un par site, donc le décompte est direct.
    """
    from src.modules.tenants.models import Cabinet

    return (await db.execute(select(func.count()).select_from(Cabinet))).scalar_one()


#: Compteurs par défaut. Un appelant peut passer le sien (comptage plus fin,
#: par exemple hors comptes désactivés) : la dépendance ne fait que l'appeler.
COMPTEURS: dict[str, Compteur] = {
    "utilisateurs": _compter_utilisateurs,
    "praticiens": _compter_praticiens,
    "sites": _compter_sites,
}


def _session_plateforme() -> AsyncSession:
    """
    Session plateforme éphémère.

    Ouverte et fermée dans la dépendance elle-même : la durée de vie d'une
    vérification de quota est la durée de l'appel, pas celle de la requête.
    Une session longue maintiendrait une connexion du pool ouverte pendant que
    le client travaille.
    """
    from src.core.platform_database import PlatformSessionFactory

    return PlatformSessionFactory()


def verifier_quota(
    ressource: str,
    compteur: Optional[Compteur] = None,
    ajoute: int = 1,
) -> Callable[..., Awaitable[None]]:
    """
    Fabrique une dépendance qui refuse l'action si elle dépasse le contrat.

    `ressource` doit être une clé de `LIBELLES_RESSOURCES` : c'est ce qui
    transforme un 403 technique en « Vous avez atteint la limite de 5
    praticiens de la formule Essentiel ».

    Le dépassement lève `QuotaExceededException` (HTTP 403, code
    `QUOTA_EXCEEDED`), déjà traduite par le gestionnaire d'erreurs global avec
    les trois nombres utiles. Une exception est préférable à un booléen
    retourné : un appelant qui oublie de tester le retour autorise le dépassement.
    """
    compte = compteur or COMPTEURS.get(ressource)
    if compte is None:
        raise ValueError(
            f"Ressource de quota inconnue : '{ressource}'. "
            f"Valeurs acceptées : {sorted(LIBELLES_RESSOURCES)}"
        )

    async def _dependance(
        tenant_db: AsyncSession = Depends(get_tenant_db),
        tenant_id: str = Depends(get_current_tenant_id),
    ) -> None:
        platform_db = _session_plateforme()
        try:
            consommation = await compte(tenant_db, tenant_id)
            await QuotaService.verifier(
                platform_db, tenant_id, ressource, consommation, ajoute=ajoute
            )
        finally:
            await platform_db.close()

    _dependance.__name__ = f"quota_{ressource}"
    return _dependance


def quota(ressource: str, compteur: Optional[Compteur] = None, ajoute: int = 1):
    """
    Syntaxe `Depends(quota("utilisateurs"))` pour les routes clientes.

    `get_tenant_db` est résolu automatiquement : la dépendance le déclare dans
    sa propre signature, FastAPI le résout dans le graphe de la route.
    """
    return verifier_quota(ressource, compteur, ajoute)


def exiger_feature(feature: str) -> Callable[..., Awaitable[None]]:
    """
    Dépendance refusant une fonctionnalité non incluse dans la formule.

    403 `FEATURE_NOT_INCLUDED`, avec le nom de la fonctionnalité et la formule
    courante : l'interface peut proposer une mise à niveau.
    """
    from src.core.platform_database import PlatformSessionFactory

    async def _dependance(tenant_id: str = Depends(get_current_tenant_id)) -> None:
        platform_db = PlatformSessionFactory()
        try:
            await QuotaService.exiger_feature(platform_db, tenant_id, feature)
        finally:
            await platform_db.close()

    _dependance.__name__ = f"feature_{feature}"
    return _dependance