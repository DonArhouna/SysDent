import uuid
from typing import AsyncGenerator, Callable, List, Optional
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from src.core.config import settings
from src.core.database import get_master_db, tenant_db_manager
from src.core.exceptions import AuthenticationException, PermissionDeniedException, TenantNotFoundException
from src.core.security import decode_token, decode_token_scoped, decrypt_secret
from src.modules.master.models import TenantDB
from src.modules.tenants.models import PermissionRole, Role, Utilisateur

security_scheme = HTTPBearer(auto_error=False)


#: Les SEULES routes qu'un jeton support peut ouvrir (Phase D.5).
#:
#: Liste blanche, et non liste noire : toute nouvelle route de l'application
#: cliente est fermée au support par défaut. L'inverse — énumérer ce qui est
#: interdit — fait qu'un ajout de route ouvre une porte sans que personne ne le
#: voie. Ici, ouvrir une porte est un acte explicite.
#:
#: Trois routes suffisent à diagnostiquer 90 % des tickets : la configuration des
#: rôles (le compte a-t-il le bon rôle ?), le catalogue des permissions, et le
#: journal d'audit (qui a touché à quoi, et quand ?). Aucune ne contient de
#: donnée de santé.
#:
#: La clé est la ROUTE, la valeur les MÉTHODES autorisées — et non un simple
#: ensemble de chemins. `/api/v1/rbac/roles` héberge à la fois `GET` (lister) et
#: `POST` (créer un rôle) : avec un filtre par chemin seul, `POST /rbac/roles`
#: franchissait la barrière du périmètre et ne se faisait arrêter que par la
#: seconde défense, `require_permissions`. La barrière tient donc tant que la
#: route déclare une permission d'écriture — c'est-à-dire par un coup de chance,
#: pas par conception. Le couple (chemin, méthode) rend l'ouverture explicite :
#: ajouter un `POST` sur une route listée n'accorde rien tant qu'il n'est pas
#: écrit ici.
ROUTES_ACCESSIBLES_AU_SUPPORT: dict[str, frozenset[str]] = {
    "/api/v1/rbac/roles": frozenset({"GET"}),
    "/api/v1/rbac/permissions": frozenset({"GET"}),
    "/api/v1/audit": frozenset({"GET"}),
}


async def get_token_payload(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> dict:
    """
    Extrait le token JWT soit du header Authorization: Bearer, soit des cookies HttpOnly.

    Le décodage passe par `decode_token_scoped`, qui accepte deux familles :
    - `tenant`  : jeton de l'application cliente (clé `SECRET_KEY`) ;
    - `support` : jeton d'accès support encadré (clé `PLATFORM_SECRET_KEY`, Phase D).

    La claim `family` est ajoutée au payload : les gardes de permission s'en
    servent pour interdire toute écriture à un jeton support.
    """
    token = None
    if credentials:
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise AuthenticationException("Jeton d'accès manquant. Veuillez vous connecter.")

    payload = decode_token_scoped(token)
    if payload.get("type") != "access":
        raise AuthenticationException("Type de jeton invalide. Access token requis.")

    # Tout le contrôle support passe par ICI, point unique traverser par chaque
    # route tenant. Le rendre optionnel le rendrait contournable dès qu'une route
    # oublierait de le déclarer — ce qui est exactement le défaut qu'on cherche à
    # éviter.
    if payload.get("family") == settings.SUPPORT_SCOPE:
        chemin = getattr(request.scope.get("route"), "path", None) or request.url.path
        if request.method not in ROUTES_ACCESSIBLES_AU_SUPPORT.get(chemin, frozenset()):
            # Le chemin du gabarit a pu différer de l'URL réelle : on retente
            # sur l'URL exacte avant de conclure.
            chemin = request.url.path
        if request.method not in ROUTES_ACCESSIBLES_AU_SUPPORT.get(chemin, frozenset()):
            raise PermissionDeniedException(
                "Un accès support en lecture seule ne donne pas accès à cette "
                "ressource.",
                code="SUPPORT_HORS_PERIMETRE",
            )
        await _revalider_acces_support(payload)
    return payload


async def _revalider_acces_support(payload: dict) -> None:
    """
    Vérifie en base que l'accès support est toujours actif.

    La session plateforme est ouverte puis fermée immédiatement : la relecture
    ne doit pas immobiliser une connexion du pool pendant toute la requête.
    """
    from src.core.platform_database import PlatformSessionFactory
    from src.modules.platform.services.support import SupportAccessService

    session = PlatformSessionFactory()
    try:
        await SupportAccessService.verifier_acces(session, payload.get("support_access_id", ""))
    finally:
        await session.close()


async def get_current_tenant_id(
    payload: dict = Depends(get_token_payload),
) -> str:
    """
    Détermine le tenant_id DEPUIS LE JETON UNIQUEMENT.

    Le tenant n'est plus jamais accepté depuis l'en-tête `X-Tenant-ID`. Ce
    repli était une faille d'escalade : un jeton de la console master (qui
    porte `tenant_id: null` par construction) suffisait, accompagné d'un
    en-tête `X-Tenant-ID` choisi par l'appelant, à ouvrir la base de N'IMPORTE
    quel cabinet et donc à lire ses données cliniques. Aucun client n'envoyait cet
    en-tête (`grep X-Tenant-ID Frontend/src` → 0 occurrence) : le repli n'a donc
    supprimé aucun usage légitime.
    """
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise TenantNotFoundException("Aucun cabinet associé à cette session.")
    return str(tenant_id)


async def get_tenant_db(
    tenant_id: str = Depends(get_current_tenant_id),
    master_db: AsyncSession = Depends(get_master_db),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Dépendance FastAPI fournissant une session DB asynchrone pointant vers le bon Tenant.

    Résout la base du cabinet via la table Master `tenants_db` et refuse
    l'accès si le cabinet n'est pas ACTIVE (une société suspendue perd l'accès
    sans que ses données soient supprimées).
    """
    try:
        uuid_tenant = uuid.UUID(str(tenant_id))
    except ValueError:
        # Un tenant_id valide est toujours l'UUID de la société (ce que place
        # l'index `utilisateur_index`). Un identifiant arbitraire ne doit pas
        # pouvoir ouvrir une session sur une base au nom deviné.
        raise AuthenticationException("Identifiant de cabinet invalide.", code="TENANT_ID_INVALIDE")

    stmt = select(TenantDB).where(
        TenantDB.societe_id == uuid_tenant,
        TenantDB.statut == "ACTIVE",
    )
    tenant_db_config = (await master_db.execute(stmt)).scalar_one_or_none()

    if tenant_db_config is None:
        raise TenantNotFoundException(tenant_id)

    await tenant_db_manager.get_or_create_engine(
        tenant_id=str(tenant_db_config.societe_id),
        db_name=tenant_db_config.db_name,
        host=tenant_db_config.db_host,
        port=tenant_db_config.db_port,
        user=tenant_db_config.db_user,
        password=decrypt_secret(tenant_db_config.db_password),
    )
    session_factory = await tenant_db_manager.get_session_factory(str(tenant_db_config.societe_id))

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class ContexteSupport(BaseModel):
    """
    Identité d'un agent de support opérant dans l'espace d'un cabinet.

    Renvoyée par `get_actor` à la place d'un `Utilisateur` quand la requête est
    portée par un jeton support. Les handlers n'ont ainsi pas à distinguer les
 deux cas : ils reçoivent toujours quelqu'un, avec un `nom` affichable et des
    permissions.
    """

    agent_id: uuid.UUID
    email: str
    nom: str
    motif: str
    ticket: Optional[str] = None
    lecture_seule: bool = True
    permissions: List[str] = []

    @property
    def id(self) -> uuid.UUID:
        """
        Alias de `agent_id`.

        Les services du cabinet journalisent `auteur.id` sans connaître le type
        de l'auteur. Cette propriété évite de demander à chaque service
        de distinguer « un compte du cabinet » de « un agent de support ».
        """
        return self.agent_id


async def get_actor(
    payload: dict = Depends(get_token_payload),
    tenant_db: AsyncSession = Depends(get_tenant_db),
) -> object:
    """
    Acteur de la requête : `Utilisateur` du cabinet, OU contexte support.

    Un jeton support ne correspond à aucun compte de la base du cabinet — et ne
    doit pas en emprunter un : le support n'a pas les identifiants de
    l'administrateur. On expose donc un objet distinct, que les handlers
    traitent comme un auteur à journaliser.

    `tenant_db` est déclaré ici et non construit à la main : appelé en Python
    simple, `get_current_user` recevrait l'objet `Depends(...)` de sa valeur par
    défaut au lieu d'une session, et `await tenant_db.execute(...)` échouerait
    sur toutes les routes qui utilisent cette dépendance. FastAPI résout
    `get_tenant_db` une seule fois par requête et la partage avec le handler,
    donc l'acteur et les écritures du même endpoint restent dans une seule
    transaction.
    """
    if payload.get("family") == settings.SUPPORT_SCOPE:
        agent_email = payload.get("impersonated_by_email") or "support@sysdent.pro"
        return ContexteSupport(
            agent_id=uuid.UUID(str(payload["sub"])),
            email=agent_email,
            nom=f"Support SysDent ({agent_email})",
            motif=payload.get("support_reason", ""),
            ticket=payload.get("support_ticket"),
            lecture_seule=payload.get("lecture_seule", True),
            permissions=list(payload.get("permissions", [])),
        )

    return await get_current_user(payload=payload, tenant_db=tenant_db)


async def get_current_user(
    payload: dict = Depends(get_token_payload),
    tenant_db: AsyncSession = Depends(get_tenant_db),
) -> Utilisateur:
    """
    Récupère l'utilisateur connecté depuis la base du Tenant avec son Rôle et ses Permissions.

    Un jeton SUPPORT ne correspond à aucun `Utilisateur` de la base du cabinet
    (son `sub` est l'identifiant de l'agent plateforme) : `resolve_support_context`
    doit être utilisé sur ces routes, et ce chemin ne doit donc pas les laisser
    passer par un compte local arbitraire.
    """
    if payload.get("family") == settings.SUPPORT_SCOPE:
        raise AuthenticationException(
            "Un accès support ne porte pas d'identité utilisateur locale.",
            code="SUPPORT_TOKEN_NO_USER",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationException("Identifiant utilisateur absent du jeton.")

    stmt = (
        select(Utilisateur)
        .options(
            selectinload(Utilisateur.role).selectinload(Role.permission_roles).selectinload(PermissionRole.permission)
        )
        .where(Utilisateur.id == user_id, Utilisateur.actif == True)
    )
    result = await tenant_db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationException("Utilisateur introuvable ou compte désactivé.")
    return user


# Actions qu'un jeton support ne peut JAMAIS exercer sur une route tenant, quel que
# soit le compte impersonné et quelle que soit l'URL appelée. Cette liste est le
# garde-fou central : ajouter une route d'écriture côté client sans y passer par
# `require_permissions` laisserait un support en lecture obtenir l'écriture.
ACTIONS_ECRITIQUES_NE_JAMAIS_SUPPORT = frozenset(
    {
        "CREATE", "UPDATE", "DELETE", "EXPORT", "SIGN",
        "PATIENTS:CREATE", "PATIENTS:UPDATE", "PATIENTS:DELETE", "PATIENTS:EXPORT",
        "CONSULTATIONS:CREATE", "CONSULTATIONS:UPDATE", "CONSULTATIONS:DELETE",
        "CONSULTATIONS:SIGN", "ORDONNANCES:SIGN",
        "FACTURATION:CREATE", "FACTURATION:UPDATE", "FACTURATION:DELETE", "FACTURATION:EXPORT",
        "ADMIN:UPDATE", "AUDIT:EXPORT",
    }
)


def require_permissions(*required_permissions: str) -> Callable:
    """
    Garde de sécurité RBAC vérifiant si l'utilisateur possède toutes les permissions requises.

    Format attendu : "MODULE:ACTION" (ex: "PATIENTS:READ"), identique à celui que
    produit `AuthService.authenticate` en combinant `permissions.module` et
    `permissions.action`. Les rôles ADMIN_CABINET et SUPER_ADMIN contournent la
    vérification (accès complet par conception).

    Un jeton SUPPORT est ici strictement cantonné à la lecture : toute permission
    d'écriture, d'export ou de gestion des droits est refusée avant même la
    comparaison avec les permissions du jeton.
    """
    async def permission_checker(payload: dict = Depends(get_token_payload)) -> bool:
        if payload.get("family") == settings.SUPPORT_SCOPE and payload.get("lecture_seule", True):
            interdits = [
                perm
                for perm in required_permissions
                if perm in ACTIONS_ECRITIQUES_NE_JAMAIS_SUPPORT or perm.split(":")[-1] != "READ"
            ]
            if interdits:
                raise PermissionDeniedException(
                    "Un accès support est en lecture seule : "
                    f"{', '.join(interdits)} est refusé pendant une session support."
                )
            # Lecture autorisée : on vérifie tout de même que l'opération est bien
            # une lecture, pas un « READ » employé sur une route mutante.
            return True

        user_permissions = payload.get("permissions", [])
        role = payload.get("role")

        # Les administrateurs de cabinet ont tous les droits par défaut
        if role in ["SUPER_ADMIN", "ADMIN_CABINET"]:
            return True

        for perm in required_permissions:
            if perm not in user_permissions:
                raise PermissionDeniedException(
                    f"Permission requise manquante : '{perm}'."
                )
        return True

    return permission_checker


def refuse_support(*required_permissions: str) -> Callable:
    """
    Interdit explicitement le jeton support sur une route.

    Utilisé sur les actions sensibles (export de dossier, suppression, gestion
    des droits) : l'absence d'un jeton support ne suffit pas, la route doit
    refuser explicitement le cas « lecture seule » plutôt que de compter sur la
    seule liste des permissions exigées.
    """
    async def _garde(payload: dict = Depends(get_token_payload)) -> bool:
        if payload.get("family") == settings.SUPPORT_SCOPE:
            raise PermissionDeniedException(
                "Cette action n'est pas autorisée pendant un accès support."
            )
        return True

    return _garde
