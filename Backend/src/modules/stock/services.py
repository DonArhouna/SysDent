"""
Stock : catalogue, mouvements, commandes fournisseurs, réceptions.

Règles qui portent l'essentiel du module :

1. **Toute variation de stock passe par un mouvement.** On n'écrit jamais
   `StockSite.quantite` directement. Le stock est la somme des mouvements : un
   inventaire physique se réconcilie, et l'écart s'explique ligne par ligne.

2. **Une sortie ne peut pas rendre le stock négatif.** On refuse le mouvement
   plutôt que d'écrire un stock négatif : un stock négatif se propage dans les
   totaux et dans les seuils d'alerte, et un seuil faux est pire qu'un refus.

3. **La réception crédite le stock immédiatement**, sans validation à deux
   mains. La sécurité vient de la traçabilité (qui, quand, quelle commande), pas
   d'un arrêt de l'écriture : dans un cabinet d'une ou deux personnes, la double
   validation empêche la réception et le stock devient faux.

4. **On ne peut pas recevoir plus que ce qui a été commandé.** La règle est
   aussi une contrainte de base (`ck_ligne_commande_quantite_coherente`) : une
   règle vérifiée uniquement en application finit toujours par être contournée
   par un script de reprise.

5. **Le stock est réparti par site.** Le total d'un article est la somme de ses
   sites ; c'est ce qui permet de savoir où chercher une ampoule en urgence.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import (
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from src.modules.tenants.models import (
    ArticleStock,
    Cabinet,
    CommandeFournisseur,
    Fournisseur,
    LigneCommande,
    LigneReception,
    LotStock,
    MouvementStock,
    ReceptionFournisseur,
    StockSite,
    StatutCommandeEnum,
    TypeMouvementStockEnum,
    Utilisateur,
)

#: Nombre de jours avant péremption qui déclenche une alerte.
JOURS_AVANT_ALERTE_PEREMPTION = 30


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# NUMÉROTATION
# ==============================================================================


async def _prochain_numero(db: AsyncSession, modele, prefixe: str) -> str:
    """
    Numéro séquentiel lisible : `CMD-2026-00001`, `REC-2026-00001`.

    Le format année-séquence permet de lire un bon de commande sans le chercher,
    et le tri chronologique reste naturel. La séquence n'est pas atomique en
    base : deux commandes créées dans la même milliseconde obtiendraient la même.
    En pratique une réception est une action humaine ; la contrainte d'unicité
    reste le filet de sécurité si deux personnes cliquent ensemble.

    On prend le modèle et non la colonne : `select_from()` attend une table ou
    une sous-requête, et lui passer `Modele.colonne` fait échouer la requête
    avec un `ArgumentError`. Le FROM est déduit de la clause WHERE.
    """
    annee = date.today().year
    prefixe_annee = f"{prefixe}-{annee}-"
    total = await db.scalar(
        select(func.count())
        .select_from(modele)
        .where(modele.numero.like(f"{prefixe_annee}%"))
    )
    return f"{prefixe_annee}{(total or 0) + 1:05d}"


# ==============================================================================
# CATALOGUE ARTICLES
# ==============================================================================


class ArticleStockService:
    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        cabinet_id: uuid.UUID,
        q: Optional[str] = None,
        categorie: Optional[str] = None,
        alerte_seuil: bool = False,
        peremption_proche: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ArticleStock], int]:
        conditions = [ArticleStock.actif.is_(True)]
        if categorie:
            conditions.append(ArticleStock.categorie == categorie)
        if q:
            motif = f"%{q.strip()}%"
            conditions.append(
                ArticleStock.designation.ilike(motif) | ArticleStock.code.ilike(motif)
            )

        stmt = select(ArticleStock)
        if conditions:
            stmt = stmt.where(*conditions)

        total = int(await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)

        rows = (
            (
                await db.execute(
                    stmt.options(selectinload(ArticleStock.stocks_sites))
                    .order_by(ArticleStock.designation)
                    .offset(offset)
                    .limit(limit)
                )
            )
            .unique()
            .scalars()
            .all()
        )
        articles = list(rows)

        if alerte_seuil or peremption_proche:
            articles = [
                a
                for a in articles
                if (alerte_seuil and ArticleStockService._sous_seuil(a))
                or (
                    peremption_proche
                    and ArticleStockService._peremption_proche(a)
                )
            ]

        return articles, total

    @staticmethod
    def _quantite_totale(article: ArticleStock) -> int:
        return sum(s.quantite for s in article.stocks_sites or [])

    @staticmethod
    def _sous_seuil(article: ArticleStock) -> bool:
        return ArticleStockService._quantite_totale(article) <= (article.seuil_alerte or 0)

    @staticmethod
    def _peremption_proche(article: ArticleStock) -> bool:
        if not article.date_peremption:
            return False
        reste = (article.date_peremption - date.today()).days
        return reste <= JOURS_AVANT_ALERTE_PEREMPTION

    @staticmethod
    async def obtenir(db: AsyncSession, article_id: uuid.UUID) -> ArticleStock:
        article = (
            await db.execute(
                select(ArticleStock)
                .options(selectinload(ArticleStock.stocks_sites))
                .where(ArticleStock.id == article_id)
            )
        ).unique().scalar_one_or_none()
        if article is None:
            raise EntityNotFoundException("Article de stock", article_id)
        return article

    @staticmethod
    async def creer(
        db: AsyncSession,
        *,
        data,
        cabinet_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
    ) -> ArticleStock:
        """
        Crée un article et l'installe dans le stock d'un site.

        La quantité initiale passe par un mouvement `ENTREE` plutôt que par une
        écriture directe : le stock d'un article créé doit pouvoir s'expliquer
        comme n'importe quelle autre entrée.
        """
        existant = (
            await db.execute(select(ArticleStock).where(ArticleStock.code == data.code))
        ).scalar_one_or_none()
        if existant is not None:
            raise BusinessRuleViolationException(
                f"Un article porte déjà le code « {data.code} ».",
                code="CODE_ARTICLE_DOUBLON",
            )

        article = ArticleStock(
            code=data.code,
            designation=data.designation,
            categorie=data.categorie,
            unite=data.unite,
            seuil_alerte=data.seuil_alerte or 0,
            prix_achat=data.prix_achat or Decimal(0),
            date_peremption=data.date_peremption,
            emplacement=data.emplacement,
            gere_par_lot=data.gere_par_lot,
            actif=True,
        )
        db.add(article)
        await db.flush()

        quantite_initiale = data.quantite_stock or 0
        if quantite_initiale > 0:
            # Import local : le service de mouvement est défini plus bas dans ce
            # fichier, et l'import de module créerait un cycle.
            from src.modules.stock.services import MouvementStockService

            await MouvementStockService.enregistrer(
                db,
                article=article,
                cabinet_id=cabinet_id,
                type_mouvement=TypeMouvementStockEnum.ENTREE,
                quantite=quantite_initiale,
                motif=data.motif_initial or "Stock initial à la création de l'article",
                auteur=auteur,
            )
        await db.commit()
        return await ArticleStockService.obtenir(db, article.id)

    @staticmethod
    async def modifier(db: AsyncSession, article_id: uuid.UUID, *, data) -> ArticleStock:
        """
        Modifie la fiche d'un article.

        Le seuil, le prix et le descriptif peuvent changer. La quantité et la
        date de péremption non : ce sont des faits de stock, pas des
        propriétés de la fiche. Elles passent par un mouvement.
        """
        article = await ArticleStockService.obtenir(db, article_id)
        for champ in (
            "designation",
            "categorie",
            "unite",
            "seuil_alerte",
            "prix_achat",
            "emplacement",
            "gere_par_lot",
            "actif",
        ):
            valeur = getattr(data, champ, None)
            if valeur is not None:
                setattr(article, champ, valeur)

        # Un code en doublon ailleurs rendrait la traçabilité ambiguë.
        nouveau_code = getattr(data, "code", None)
        if nouveau_code and nouveau_code != article.code:
            conflit = (
                await db.execute(
                    select(ArticleStock).where(
                        ArticleStock.code == nouveau_code, ArticleStock.id != article_id
                    )
                )
            ).scalar_one_or_none()
            if conflit is not None:
                raise BusinessRuleViolationException(
                    f"Un autre article porte déjà le code « {nouveau_code} ».",
                    code="CODE_ARTICLE_DOUBLON",
                )
            article.code = nouveau_code

        await db.commit()
        return await ArticleStockService.obtenir(db, article_id)


# ==============================================================================
# MOUVEMENTS — le seul point d'écriture du stock
# ==============================================================================


class MouvementStockService:
    #: Types de mouvement qui diminuent le stock.
    SORTIES = {
        TypeMouvementStockEnum.SORTIE_CONSULTATION,
        TypeMouvementStockEnum.PERTE_PEREMPTION,
    }

    @staticmethod
    async def enregistrer(
        db: AsyncSession,
        *,
        article: ArticleStock,
        cabinet_id: uuid.UUID,
        type_mouvement: TypeMouvementStockEnum,
        quantite: int,
        motif: Optional[str] = None,
        auteur: Optional[Utilisateur] = None,
        lot_id: Optional[uuid.UUID] = None,
        commande_id: Optional[uuid.UUID] = None,
    ) -> MouvementStock:
        """
        Enregistre un mouvement et met à jour le stock du site, dans la même
        transaction. Either les deux passent, or neither ne le fait.
        """
        if quantite <= 0:
            raise BusinessRuleViolationException(
                "La quantité d'un mouvement doit être strictement positive.",
                code="QUANTITE_MOUVEMENT_INVALIDE",
            )

        # Les sorties à but de traçabilité (perte, péremption) exigent un motif :
        # sans motif, une quantité disparue est inexpliquée.
        if type_mouvement is TypeMouvementStockEnum.PERTE_PEREMPTION and not motif:
            raise BusinessRuleViolationException(
                "Une sortie pour péremption doit être motivée.",
                code="MOTIF_OBLIGATOIRE",
            )

        stock_site = await MouvementStockService._stock_site(db, article.id, cabinet_id)
        stock_avant = stock_site.quantite if stock_site else 0

        signe = -1 if type_mouvement in MouvementStockService.SORTIES else 1
        stock_apres = stock_avant + signe * quantite

        if stock_apres < 0:
            raise BusinessRuleViolationException(
                f"Stock insuffisant : {stock_avant} disponible(s) pour "
                f"« {article.designation} », {quantite} demandée(s).",
                code="STOCK_INSUFFISANT",
                details={
                    "article_id": str(article.id),
                    "designation": article.designation,
                    "stock_disponible": stock_avant,
                    "quantite_demandee": quantite,
                },
            )

        if stock_site is None:
            stock_site = StockSite(article_id=article.id, cabinet_id=cabinet_id, quantite=0)
            db.add(stock_site)
        stock_site.quantite = stock_apres

        if lot_id is not None:
            await MouvementStockService._maj_lot(db, lot_id, signe * quantite)

        mouvement = MouvementStock(
            article_id=article.id,
            cabinet_id=cabinet_id,
            lot_id=lot_id,
            type_mouvement=type_mouvement,
            quantite=quantite,
            stock_avant=stock_avant,
            stock_apres=stock_apres,
            motif=motif,
            auteur_id=auteur.id if auteur else None,
            auteur_email=auteur.email if auteur else None,
            commande_id=commande_id,
            date_mouvement=_maintenant(),
        )
        db.add(mouvement)
        await db.flush()
        return mouvement

    @staticmethod
    async def _stock_site(
        db: AsyncSession, article_id: uuid.UUID, cabinet_id: uuid.UUID
    ) -> Optional[StockSite]:
        return (
            await db.execute(
                select(StockSite).where(
                    StockSite.article_id == article_id, StockSite.cabinet_id == cabinet_id
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def _maj_lot(db: AsyncSession, lot_id: uuid.UUID, variation: int) -> None:
        lot = (
            await db.execute(select(LotStock).where(LotStock.id == lot_id))
        ).scalar_one_or_none()
        if lot is None:
            raise EntityNotFoundException("Lot de stock", lot_id)
        lot.quantite_restante += variation
        if lot.quantite_restante < 0:
            raise BusinessRuleViolationException(
                f"Le lot « {lot.code_lot} » ne contient plus que "
                f"{lot.quantite_restante + abs(variation)} unité(s).",
                code="LOT_INSUFFISANT",
            )

    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        article_id: Optional[uuid.UUID] = None,
        cabinet_id: Optional[uuid.UUID] = None,
        type_mouvement: Optional[TypeMouvementStockEnum] = None,
        limit: int = 50,
    ) -> List[MouvementStock]:
        stmt = select(MouvementStock).options(
            selectinload(MouvementStock.article),
            selectinload(MouvementStock.auteur),
        )
        if article_id:
            stmt = stmt.where(MouvementStock.article_id == article_id)
        if cabinet_id:
            stmt = stmt.where(MouvementStock.cabinet_id == cabinet_id)
        if type_mouvement:
            stmt = stmt.where(MouvementStock.type_mouvement == type_mouvement)
        return list(
            (await db.execute(stmt.order_by(MouvementStock.date_mouvement.desc()).limit(limit)))
            .unique()
            .scalars()
            .all()
        )


# ==============================================================================
# FOURNISSEURS
# ==============================================================================


class FournisseurService:
    @staticmethod
    async def lister(db: AsyncSession, *, q: Optional[str] = None) -> List[Fournisseur]:
        stmt = select(Fournisseur)
        if q:
            motif = f"%{q.strip()}%"
            stmt = stmt.where(Fournisseur.nom.ilike(motif))
        return list((await db.execute(stmt.order_by(Fournisseur.nom))).scalars().all())

    @staticmethod
    async def obtenir(db: AsyncSession, fournisseur_id: uuid.UUID) -> Fournisseur:
        fournisseur = (
            await db.execute(
                select(Fournisseur).where(Fournisseur.id == fournisseur_id)
            )
        ).scalar_one_or_none()
        if fournisseur is None:
            raise EntityNotFoundException("Fournisseur", fournisseur_id)
        return fournisseur

    @staticmethod
    async def creer(db: AsyncSession, *, data) -> Fournisseur:
        fournisseur = Fournisseur(
            nom=data.nom,
            contact=data.contact,
            telephone=data.telephone,
            email=data.email,
            adresse=data.adresse,
            notes=data.notes,
            actif=True,
        )
        db.add(fournisseur)
        await db.commit()
        return fournisseur

    @staticmethod
    async def modifier(db: AsyncSession, fournisseur_id: uuid.UUID, *, data) -> Fournisseur:
        fournisseur = await FournisseurService.obtenir(db, fournisseur_id)
        for champ in ("nom", "contact", "telephone", "email", "adresse", "notes", "actif"):
            valeur = getattr(data, champ, None)
            if valeur is not None:
                setattr(fournisseur, champ, valeur)
        await db.commit()
        return await FournisseurService.obtenir(db, fournisseur_id)


# ==============================================================================
# COMMANDES FOURNISSEUR
# ==============================================================================


class CommandeFournisseurService:
    #: Transitions autorisées. Toute autre est refusée.
    TRANSITIONS: Dict[StatutCommandeEnum, Sequence[StatutCommandeEnum]] = {
        StatutCommandeEnum.BROUILLON: (
            StatutCommandeEnum.ENVOYEE,
            StatutCommandeEnum.ANNULEE,
        ),
        StatutCommandeEnum.ENVOYEE: (
            StatutCommandeEnum.RECUE,
            StatutCommandeEnum.PARTIELLEMENT_REÇUE,
            StatutCommandeEnum.ANNULEE,
        ),
        StatutCommandeEnum.PARTIELLEMENT_REÇUE: (
            StatutCommandeEnum.RECUE,
        ),
        StatutCommandeEnum.RECUE: (),
        StatutCommandeEnum.ANNULEE: (),
    }

    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        statut: Optional[StatutCommandeEnum] = None,
        fournisseur_id: Optional[uuid.UUID] = None,
        limit: int = 50,
    ) -> List[CommandeFournisseur]:
        stmt = select(CommandeFournisseur).options(
            selectinload(CommandeFournisseur.fournisseur),
            selectinload(CommandeFournisseur.lignes).selectinload(LigneCommande.article),
        )
        if statut:
            stmt = stmt.where(CommandeFournisseur.statut == statut)
        if fournisseur_id:
            stmt = stmt.where(CommandeFournisseur.fournisseur_id == fournisseur_id)
        return list(
            (
                await db.execute(stmt.order_by(CommandeFournisseur.date_commande.desc()).limit(limit))
            )
            .unique()
            .scalars()
            .all()
        )

    @staticmethod
    async def obtenir(db: AsyncSession, commande_id: uuid.UUID) -> CommandeFournisseur:
        commande = (
            await db.execute(
                select(CommandeFournisseur)
                .options(
                    selectinload(CommandeFournisseur.fournisseur),
                    selectinload(CommandeFournisseur.lignes).selectinload(LigneCommande.article),
                )
                .where(CommandeFournisseur.id == commande_id)
            )
        ).unique().scalar_one_or_none()
        if commande is None:
            raise EntityNotFoundException("Commande fournisseur", commande_id)
        return commande

    @staticmethod
    async def creer(
        db: AsyncSession,
        *,
        data,
        auteur: Optional[Utilisateur] = None,
    ) -> CommandeFournisseur:
        """
        Crée un bon de commande en brouillon.

        Émettre une commande n'ajoute rien au stock : la matière n'arrive qu'à la
        réception. Sans cette séparation, le stock annoncerait des ampoules que
        le cabinet n'a pas.
        """
        if not data.lignes:
            raise BusinessRuleViolationException(
                "Une commande doit contenir au moins une ligne.",
                code="COMMANDE_SANS_LIGNE",
            )

        await FournisseurService.obtenir(db, data.fournisseur_id)

        commande = CommandeFournisseur(
            numero=await _prochain_numero(db, CommandeFournisseur, "CMD"),
            fournisseur_id=data.fournisseur_id,
            statut=StatutCommandeEnum.BROUILLON,
            date_commande=date.today(),
            notes=data.notes,
            auteur_id=auteur.id if auteur else None,
            auteur_email=auteur.email if auteur else None,
        )
        db.add(commande)
        await db.flush()

        for ligne in data.lignes:
            if ligne.quantite <= 0:
                raise BusinessRuleViolationException(
                    "La quantité commandée doit être strictement positive.",
                    code="QUANTITE_COMMANDE_INVALIDE",
                )
            article = await ArticleStockService.obtenir(db, ligne.article_id)
            db.add(
                LigneCommande(
                    commande_id=commande.id,
                    article_id=article.id,
                    quantite_commandee=ligne.quantite,
                    quantite_recue=0,
                    prix_unitaire=ligne.prix_unitaire
                    if ligne.prix_unitaire is not None
                    else article.prix_achat,
                )
            )

        await db.commit()
        return await CommandeFournisseurService.obtenir(db, commande.id)

    @staticmethod
    async def changer_statut(
        db: AsyncSession, commande_id: uuid.UUID, nouveau: StatutCommandeEnum
    ) -> CommandeFournisseur:
        commande = await CommandeFournisseurService.obtenir(db, commande_id)
        autorisees = CommandeFournisseurService.TRANSITIONS.get(commande.statut, ())
        if nouveau not in autorisees:
            raise BusinessRuleViolationException(
                f"Une commande {commande.statut.value.lower().replace('_', ' ')} "
                f"ne peut pas passer à {nouveau.value.lower().replace('_', ' ')}.",
                code="TRANSITION_STATUT_INTERDITE",
                details={
                    "statut_actuel": commande.statut.value,
                    "statut_cible": nouveau.value,
                    "transitions_autorisees": [s.value for s in autorisees],
                },
            )
        commande.statut = nouveau
        await db.commit()
        return await CommandeFournisseurService.obtenir(db, commande_id)

    @staticmethod
    async def annuler(db: AsyncSession, commande_id: uuid.UUID) -> CommandeFournisseur:
        commande = await CommandeFournisseurService.obtenir(db, commande_id)
        if commande.statut is StatutCommandeEnum.RECUE:
            raise BusinessRuleViolationException(
                "Une commande réceptionnée ne peut plus être annulée : "
                "la matière est entrée en stock.",
                code="COMMANDE_DEJA_REÇUE",
            )
        return await CommandeFournisseurService.changer_statut(
            db, commande_id, StatutCommandeEnum.ANNULEE
        )


# ==============================================================================
# RÉCEPTION — crédite le stock automatiquement
# ==============================================================================


class ReceptionService:
    @staticmethod
    async def enregistrer(
        db: AsyncSession,
        *,
        commande_id: uuid.UUID,
        lignes: Sequence,
        site_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
        notes: Optional[str] = None,
    ) -> ReceptionFournisseur:
        """
        Enregistre une réception et crédite le stock, dans une seule transaction.

        Ce qui est reçu est crédité immédiatement, sans validation à deux mains :
        la traçabilité (qui, quand, quelle commande) remplace le contrôle, qui
        dans un cabinet d'une ou deux personnes empêcherait la réception.

        Tout se joue à la atomicité : si le crédit d'une ligne échoue, aucune
        ligne n'est créditée. Un stock à moitié crédité est pire qu'un stock
        intact, parce qu'il est faux *et* qu'on le croit juste.
        """
        commande = await CommandeFournisseurService.obtenir(db, commande_id)

        if commande.statut is StatutCommandeEnum.BROUILLON:
            raise BusinessRuleViolationException(
                "Une commande en brouillon ne peut pas être réceptionnée : "
                "envoyez-la d'abord au fournisseur.",
                code="COMMANDE_EN_BROUILLON",
            )
        if commande.statut in (StatutCommandeEnum.RECUE, StatutCommandeEnum.ANNULEE):
            raise BusinessRuleViolationException(
                f"Une commande {commande.statut.value.lower().replace('_', ' ')} "
                "ne peut pas être réceptionnée.",
                code="COMMANDE_NON_RECEPTABLE",
            )
        if not lignes:
            raise BusinessRuleViolationException(
                "Une réception doit comporter au moins une ligne.",
                code="RECEPTION_SANS_LIGNE",
            )

        lignes_par_id = {l.id: l for l in commande.lignes}
        Reception = ReceptionFournisseur(
            numero=await _prochain_numero(db, ReceptionFournisseur, "REC"),
            commande_id=commande.id,
            date_reception=date.today(),
            notes=notes,
            auteur_id=auteur.id if auteur else None,
            auteur_email=auteur.email if auteur else None,
        )
        db.add(Reception)
        await db.flush()

        articles: Dict[uuid.UUID, Any] = {}

        for entree in lignes:
            ligne = lignes_par_id.get(entree.ligne_commande_id)
            if ligne is None:
                raise BusinessRuleViolationException(
                    "La ligne réceptionnée n'appartient pas à cette commande.",
                    code="LIGNE_HORS_COMMANDE",
                )

            restant = ligne.quantite_commandee - ligne.quantite_recue
            if entree.quantite_recue > restant:
                raise BusinessRuleViolationException(
                    f"Réception de {entree.quantite_recue} alors qu'il ne reste que "
                    f"{restant} à livrer sur « {ligne.article.designation} ».",
                    code="RECEPTION_SUPERIEURE_A_COMMANDE",
                    details={
                        "ligne_id": str(ligne.id),
                        "quantite_commandee": ligne.quantite_commandee,
                        "deja_recu": ligne.quantite_recue,
                        "quantite_recue": entree.quantite_recue,
                    },
                )

            article = ligne.article
            articles[article.id] = article

            lot_id = None
            if article.gere_par_lot:
                lot = LotStock(
                    article_id=article.id,
                    cabinet_id=site_id,
                    code_lot=entree.lot_code
                    or f"AUTO-{commande.numero}-{ligne.id.hex[:6].upper()}",
                    date_peremption=entree.date_peremption or article.date_peremption,
                    quantite_initiale=entree.quantite_recue,
                    quantite_restante=0,
                )
                db.add(lot)
                await db.flush()
                lot_id = lot.id

            await MouvementStockService.enregistrer(
                db,
                article=article,
                cabinet_id=site_id,
                type_mouvement=TypeMouvementStockEnum.ENTREE,
                quantite=entree.quantite_recue,
                motif=f"Réception de la commande {commande.numero}",
                auteur=auteur,
                lot_id=lot_id,
                commande_id=commande.id,
            )

            db.add(
                LigneReception(
                    reception_id=Reception.id,
                    ligne_commande_id=ligne.id,
                    quantite_recue=entree.quantite_recue,
                    lot_code=entree.lot_code,
                    date_peremption=entree.date_peremption,
                )
            )
            ligne.quantite_recue += entree.quantite_recue

        # Le statut de la commande se déduit de ce qui a été livré, jamais de ce
        # que l'utilisateur a coché.
        toutes_livrees = all(
            l.quantite_recue >= l.quantite_commandee for l in commande.lignes
        )
        une_livree = any(l.quantite_recue > 0 for l in commande.lignes)
        commande.statut = (
            StatutCommandeEnum.RECUE
            if toutes_livrees
            else StatutCommandeEnum.PARTIELLEMENT_REÇUE
            if une_livree
            else commande.statut
        )

        await db.commit()

        # Après le commit, l'objet est expiré : lire `reception.lignes`
        # déclencherait un lazy-load interdit (MissingGreenlet). On relit donc
        # la réception avec ses lignes, comme on le fait pour la commande.
        return (
            await db.execute(
                select(ReceptionFournisseur)
                .options(selectinload(ReceptionFournisseur.lignes))
                .where(ReceptionFournisseur.id == Reception.id)
            )
        ).unique().scalar_one()


# ==============================================================================
# ALERTES
# ==============================================================================


class AlerteStockService:
    @staticmethod
    async def lister(
        db: AsyncSession, *, cabinet_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """
        Alertes calculées à la demande, non stockées.

        Une alerte stockée vieillit : si l'article est racheté et que personne ne
        recharge la table, le cabinet continue de voir « sous le seuil ». Le
        calcul est fait à chaque appel à partir de l'état réel, ce qui coûte
        un balayage du catalogue et garantit une alerte juste.
        """
        articles, _ = await ArticleStockService.lister(db, cabinet_id=cabinet_id, limit=1000)
        alertes: List[Dict[str, Any]] = []
        for article in articles:
            if ArticleStockService._sous_seuil(article):
                alertes.append(
                    {
                        "article_id": str(article.id),
                        "designation": article.designation,
                        "code": article.code,
                        "type": "SEUIL_MINIMUM",
                        "niveau": "URGENT"
                        if ArticleStockService._quantite_totale(article) == 0
                        else "AVERTISSEMENT",
                        "stock_actuel": ArticleStockService._quantite_totale(article),
                        "seuil": article.seuil_alerte,
                        "unite": article.unite,
                        "message": (
                            f"« {article.designation} » : "
                            f"{ArticleStockService._quantite_totale(article)} {article.unite}, "
                            f"seuil {article.seuil_alerte}."
                        ),
                    }
                )
            reste = (
                (article.date_peremption - date.today()).days
                if article.date_peremption
                else None
            )
            if reste is not None and reste <= JOURS_AVANT_ALERTE_PEREMPTION:
                alertes.append(
                    {
                        "article_id": str(article.id),
                        "designation": article.designation,
                        "code": article.code,
                        "type": "PEREMPTION_PROCHE" if reste >= 0 else "PERIM_E",
                        "niveau": "URGENT" if reste < 0 else "AVERTISSEMENT",
                        "stock_actuel": ArticleStockService._quantite_totale(article),
                        "date_peremption": article.date_peremption.isoformat(),
                        "jours_restants": reste,
                        "unite": article.unite,
                        "message": (
                            f"« {article.designation} » : "
                            + (
                                f"périmé depuis {-reste} jour(s)."
                                if reste < 0
                                else f"périme dans {reste} jour(s)."
                            )
                        ),
                    }
                )
        return alertes
