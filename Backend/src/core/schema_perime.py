"""Schema tenant perime : detection, et reponse controlee associee.

La base d'un cabinet repond, mais plus comme le code l'attend : la connexion
succeed, puis la premiere requete echoue sur une table, une colonne ou une
fonction absente. C'est le symptome d'un cabinet en retard de migrations, et
non d'un bug : la distinction merite un traitement a part.

**Pourquoi ce module existe.** Le triage vivait dans `auth/services.py`, atteint
par le seul login. Les routes de tarification, elles, interrogent la base de la
meme facon et renvoyaient 500 : meme panne, deux traitements, et le second
n'existeait pas. Un triage qui ne s'applique qu'a une route est un triage
incomplet. Il est donc ici, ou il est appele par tous.

**Le 500 etait le symptome le plus trompeur.** Un 500 dit au client que
l'application est cassee. Ici elle ne l'est pas : elle lit une table qu'elle a
elle-meme creee par une migration qui n'a pas ete appliquee. La reponse doit
donc etre un 503 et un code stable, pour que l'interface puisse dire ce qui
se passe au lieu d'afficher une erreur generique.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Optional

import asyncpg.exceptions

from .exceptions import AppException

#: Code stable, parte du contrat avec le client. Une interface s'y abonne pour
#: afficher un message qui parle de la mise a jour du schema, et non d'une panne.
CODE_SCHEMA_EN_RETARD = "SCHEMA_EN_RETARD"

#: Message de reponse. Il dit ce qu'il faut faire, jamais ce que la base a
#: repondu : ni nom de table, ni identifiant de cabinet, ni chaine du pilote.
MESSAGE_SCHEMA_EN_RETARD = (
    "Ce module n'est pas encore disponible pour votre cabinet : une mise a jour "
    "du schema est necessaire. Contactez votre administrateur."
)

#: Erreurs qui signifient « la base repond, mais plus comme le code l'attend ».
#:
#: SQLAlchemy les encapsule dans `ProgrammingError`, qui couvre aussi une faute
#: de frappe dans une requete : rien a voir, et ca doit remonter tel quel.
SCHEMA_PERIME = (
    asyncpg.exceptions.UndefinedColumnError,
    asyncpg.exceptions.UndefinedTableError,
    asyncpg.exceptions.UndefinedFunctionError,
)

#: Les memes divergences, dites par leur code PostgreSQL.
#:
#: Un `sqlstate` est plus fiable qu'un nom de classe : il est porte par le
#: serveur, il traverse les couches sans se transformer, et il ne depend ni de
#: la version de SQLAlchemy ni de celle du pilote. On reconnait donc les deux.
#: 42703 colonne absente, 42P01 table absente, 42883 fonction absente.
SQLSTATE_SCHEMA_PERIME = frozenset({"42703", "42P01", "42883"})

#: Combien de niveaux d'encapsulation on descend. Mesure le 11/10 : l'erreur
#: asyncpg est deux niveaux sous le `ProgrammingError` attrape, pas un. Une
#: profondeur bornee evite une boucle sur une chaine circulaire.
PROFONDEUR_CHAINE = 6

#: Forme exacte du message de PostgreSQL pour un objet absent. Le serveur la
#: redige toujours ainsi, et le pilote la recopie telle quelle.
_MOT_NOM_ABSENT = re.compile(r'(?:relation|table|column|function)\s+"([^"]+)"')

#: Cabinet de la requete en cours. Renseignee par la dependance de session
#: tenant, qui est le seul endroit ou l'identifiant est connu sans le redemander.
_tenant_courant: ContextVar[Optional[str]] = ContextVar("sysdent_tenant_courant", default=None)


def marquer_tenant(tenant_id: Optional[str]) -> None:
    """Retient l'identifiant du cabinet pour le journal d'un echec de schema."""
    _tenant_courant.set(str(tenant_id) if tenant_id is not None else None)


def tenant_courant() -> Optional[str]:
    """Identifiant du cabinet de la requete en cours, s'il est connu."""
    return _tenant_courant.get()


def _divergence(exc: BaseException) -> Optional[BaseException]:
    """
    L'erreur vient-elle d'un schema perime ? Renvoie l'erreur du pilote si oui.

    **Il faut descendre la chaine entiere.** Mesure le 11/10 sur une base
    reelle dont on avait supprime une colonne, SQLAlchemy empile :

        niveau 0  sqlalchemy.exc.ProgrammingError
          .orig -> niveau 1  ...postgresql.asyncpg.ProgrammingError  sqlstate=42703
                  .orig -> niveau 2  asyncpg.exceptions.UndefinedColumnError

    Le triage d'origine s'arretait au niveau 1, ou il ne trouve qu'un
    `ProgrammingError` : il concluait « pas une divergence » et laissait
    remonter un 500. C'est exactement la panne qu'il devait empecher.
    """
    vues: set[int] = set()
    courant: Optional[BaseException] = exc
    for _ in range(PROFONDEUR_CHAINE):
        if courant is None or id(courant) in vues:
            return None
        vues.add(id(courant))

        if isinstance(courant, SCHEMA_PERIME):
            return courant
        if getattr(courant, "sqlstate", None) in SQLSTATE_SCHEMA_PERIME:
            return courant

        origine = getattr(courant, "orig", None)
        suivant = origine if isinstance(origine, BaseException) else courant.__cause__
        if suivant is None or suivant is courant:
            # On tente aussi `__context__` : une exception levee pendant le
            # traitement d'une autre peut porter la divergence.
            if courant.__context__ is not None and courant.__context__ is not courant:
                courant = courant.__context__
                continue
            return None
        courant = suivant
    return None


def est_divergence_de_schema(exc: BaseException) -> bool:
    """`exc` vient-elle d'un schema perime, ou d'une requete de code cassee ?"""
    return _divergence(exc) is not None


def element_manquant(exc: BaseException) -> Optional[str]:
    """
    La table ou la colonne absente, pour le journal du serveur uniquement.

    asyncpg nomme l'objet manquant sur l'erreur qu'il leve, mais ce nom n'est
    pas toujours present : selon la maniere dont l'erreur a ete construite, le
    champ reste vide. On relit donc le message, que PostgreSQL redacte toujours
    de la meme facon. Sans ce repli, le journal affichait `element_manquant`
    a null et ne disait rien a l'administrateur qui doit appliquer la migration.

    Cette valeur ne sort **jamais** vers le client : elle indique quelle
    migration appliquer, et la dire revelerait le schema du cabinet.
    """
    divergence = _divergence(exc)
    if divergence is None:
        return None

    nom_table = getattr(divergence, "table_name", None)
    nom_colonne = getattr(divergence, "column_name", None)
    if nom_table and nom_colonne:
        return f"{nom_table}.{nom_colonne}"
    trouve = nom_table or nom_colonne
    if trouve:
        return trouve

    message = str(divergence)
    trouve_message = _MOT_NOM_ABSENT.search(message)
    return trouve_message.group(1) if trouve_message else None


class SchemaEnRetardException(AppException):
    """Le cabinet est en retard de migrations : reponse controlee, jamais un 500.

    **La reponse ne dit rien du schema.** Ni table, ni colonne, ni identifiant de
    cabinet : c'est le journal du serveur qui porte le detail, avec l'identifiant
    du cabinet et l'element manquant, pour qu'un administrateur puisse agir.
    """

    def __init__(self) -> None:
        super().__init__(
            message=MESSAGE_SCHEMA_EN_RETARD,
            code=CODE_SCHEMA_EN_RETARD,
            status_code=503,
            details={},
        )