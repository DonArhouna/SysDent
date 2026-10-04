import { cn } from '@/lib/utils'
import type { DentOdontogramme, EtatReferentiel } from '../types'

interface OdontogrammeSvgProps {
  dents: DentOdontogramme[]
  referentielEtats: EtatReferentiel[]
  dentSelectionneeFdi?: number | null
  onSelectDent: (dent: DentOdontogramme) => void
  typeOdontogramme: 'ADULTE' | 'ENFANT' | 'MIXTE'
}

/**
 * Palette de repli des états cliniques.
 *
 * Ces teintes relèvent d'une convention du schéma dentaire, pas d'un choix
 * décoratif : on les déclare donc via les tokens sémantiques du thème (un seul
 * jeu clair/sombre, bascule instantaneous) plutôt que des hex en dur dans le
 * JSX. La couleur de référence reste celle du backend
 * (`EtatReferentiel.couleur`) ; ces valeurs ne servent que si elle manque.
 */
const COULEUR_CARIE = 'hsl(var(--danger))'
const COULEUR_SOIGNEE = 'hsl(var(--accent-blue))'
const COULEUR_COURONNE = 'hsl(var(--warning))'
/** Dent saine : vert sémantique. */
const COULEUR_SAINE = 'hsl(var(--success))'
/** Croix de dent absente : gris neutre du thème. */
const COULEUR_ABSENTE = 'hsl(var(--muted-foreground))'

// Numéros FDI par quadrant
const QUADRANTS_ADULTE = {
  q1: [18, 17, 16, 15, 14, 13, 12, 11], // Supérieur Droit
  q2: [21, 22, 23, 24, 25, 26, 27, 28], // Supérieur Gauche
  q4: [48, 47, 46, 45, 44, 43, 42, 41], // Inférieur Droit
  q3: [31, 32, 33, 34, 35, 36, 37, 38], // Inférieur Gauche
}

const QUADRANTS_ENFANT = {
  q1: [55, 54, 53, 52, 51],
  q2: [61, 62, 63, 64, 65],
  q4: [85, 84, 83, 82, 81],
  q3: [71, 72, 73, 74, 75],
}

/**
 * Composant individuel représentant une dent avec ses 5 faces géométriques.
 * Faces :
 * - Haut : Vestibulaire (ou Linguale selon arcade)
 * - Bas : Palatine/Linguale
 * - Gauche : Mésiale ou Distale
 * - Droite : Distale ou Mésiale
 * - Centre : Occlusale / Incisive
 */
function DentItem({
  dent,
  isSelected,
  couleurGlobale,
  onClick,
}: {
  dent?: DentOdontogramme
  isSelected: boolean
  couleurGlobale: string
  onClick: () => void
}) {
  if (!dent) return null

  // Couleur des 5 faces si renseignées, sinon couleur globale
  const getCouleurFace = (faceNom: string) => {
    const f = dent.faces.find(
      (fc) => fc.face === faceNom || fc.face_courte === faceNom.charAt(0),
    )
    if (f && f.etat !== 'SAINE') {
      if (f.etat.includes('CARIE')) return COULEUR_CARIE
      if (f.etat.includes('SOIGNEE') || f.etat.includes('OBTUR')) return COULEUR_SOIGNEE
      if (f.etat.includes('COURONNE')) return COULEUR_COURONNE
    }
    return couleurGlobale
  }

  const cCentre = getCouleurFace('OCCLUSALE')
  const cHaut = getCouleurFace('VESTIBULAIRE')
  const cBas = getCouleurFace('LINGUALE')
  const cGauche = getCouleurFace('MESIALE')
  const cDroite = getCouleurFace('DISTALE')

  const estAbsent = dent.etat_actuel.includes('ABSENTE')

  return (
    <div
      onClick={onClick}
      role="button"
      tabIndex={0}
      title={`Dent ${dent.numero_fdi} : ${dent.etat_libelle ?? dent.etat_actuel}`}
      className={cn(
        'group relative flex flex-col items-center p-1 rounded-xl transition-all duration-150 cursor-pointer select-none',
        isSelected
          ? 'bg-primary/15 ring-2 ring-primary scale-105 shadow-md'
          : 'hover:bg-muted/70 hover:scale-102',
        estAbsent && 'opacity-40 grayscale',
      )}
    >
      {/* Numéro FDI au dessus */}
      <span
        className={cn(
          'text-[11px] font-bold font-mono leading-none mb-1',
          isSelected ? 'text-primary font-black' : 'text-muted-foreground',
          dent.a_alerte && 'text-danger font-black animate-pulse',
        )}
      >
        {dent.numero_fdi}
      </span>

      {/* SVG géométrique de la dent à 5 facettes */}
      <svg
        viewBox="0 0 50 50"
        className="w-8 h-8 sm:w-10 sm:h-10 transition-transform drop-shadow-2xs"
        aria-hidden="true"
      >
        {/* Face Haut (Vestibulaire) */}
        <polygon
          points="5,5 45,5 35,15 15,15"
          fill={cHaut}
          stroke="currentColor"
          strokeWidth="1.2"
          className="transition-colors group-hover:brightness-95"
        />

        {/* Face Bas (Linguale / Palatine) */}
        <polygon
          points="15,35 35,35 45,45 5,45"
          fill={cBas}
          stroke="currentColor"
          strokeWidth="1.2"
          className="transition-colors group-hover:brightness-95"
        />

        {/* Face Gauche (Mésiale) */}
        <polygon
          points="5,5 15,15 15,35 5,45"
          fill={cGauche}
          stroke="currentColor"
          strokeWidth="1.2"
          className="transition-colors group-hover:brightness-95"
        />

        {/* Face Droite (Distale) */}
        <polygon
          points="45,5 45,45 35,35 35,15"
          fill={cDroite}
          stroke="currentColor"
          strokeWidth="1.2"
          className="transition-colors group-hover:brightness-95"
        />

        {/* Face Centre (Occlusale) */}
        <rect
          x="15"
          y="15"
          width="20"
          height="20"
          fill={cCentre}
          stroke="currentColor"
          strokeWidth="1.2"
          className="transition-colors group-hover:brightness-95"
        />

        {/* Croix si dent absente */}
        {estAbsent && (
          <line
            x1="5"
            y1="5"
            x2="45"
            y2="45"
            stroke={COULEUR_ABSENTE}
            strokeWidth="3"
            strokeLinecap="round"
          />
        )}
      </svg>

      {/* Point indicateur si alerte clinique */}
      {dent.a_alerte && (
        <span
          className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5 rounded-full bg-danger ring-2 ring-card animate-ping"
          aria-label="Alerte sur cette dent"
        />
      )}
      {dent.a_alerte && (
        <span className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5 rounded-full bg-danger ring-2 ring-card" />
      )}
    </div>
  )
}

export function OdontogrammeSvg({
  dents,
  referentielEtats,
  dentSelectionneeFdi,
  onSelectDent,
  typeOdontogramme,
}: OdontogrammeSvgProps) {
  // Mapping couleur par état
  const couleurMap = new Map<string, string>()
  referentielEtats.forEach((e) => couleurMap.set(e.code, e.couleur))

  const dentParFdi = new Map<number, DentOdontogramme>()
  dents.forEach((d) => dentParFdi.set(d.numero_fdi, d))

  const getCouleur = (etat: string) => couleurMap.get(etat) ?? COULEUR_SAINE

  const quadrants = typeOdontogramme === 'ENFANT' ? QUADRANTS_ENFANT : QUADRANTS_ADULTE

  return (
    <div className="w-full select-none space-y-6">
      {/* ================= ARCADE MAXILLAIRE (HAUT) ================= */}
      <div className="rounded-2xl border border-border bg-card p-4 sm:p-6 shadow-xs">
        <div className="flex items-center justify-between mb-3 border-b border-border pb-2">
          <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Arcade Maxillaire (Supérieure)
          </span>
          <span className="text-[11px] text-muted-foreground">Quadrant 1 (Droit) • Quadrant 2 (Gauche)</span>
        </div>

        <div className="flex items-center justify-center gap-1 sm:gap-2 overflow-x-auto py-2">
          {/* Quadrant 1 (18 à 11 ou 55 à 51) */}
          <div className="flex items-center gap-1 sm:gap-1.5 border-r-2 border-primary/30 pr-2 sm:pr-3">
            {quadrants.q1.map((fdi) => {
              const d = dentParFdi.get(fdi)
              return (
                <DentItem
                  key={fdi}
                  dent={d}
                  isSelected={dentSelectionneeFdi === fdi}
                  couleurGlobale={d ? getCouleur(d.etat_actuel) : COULEUR_SAINE}
                  onClick={() => d && onSelectDent(d)}
                />
              )
            })}
          </div>

          {/* Quadrant 2 (21 à 28 ou 61 à 65) */}
          <div className="flex items-center gap-1 sm:gap-1.5 pl-2 sm:pl-3">
            {quadrants.q2.map((fdi) => {
              const d = dentParFdi.get(fdi)
              return (
                <DentItem
                  key={fdi}
                  dent={d}
                  isSelected={dentSelectionneeFdi === fdi}
                  couleurGlobale={d ? getCouleur(d.etat_actuel) : COULEUR_SAINE}
                  onClick={() => d && onSelectDent(d)}
                />
              )
            })}
          </div>
        </div>
      </div>

      {/* ================= ARCADE MANDIBULAIRE (BAS) ================= */}
      <div className="rounded-2xl border border-border bg-card p-4 sm:p-6 shadow-xs">
        <div className="flex items-center justify-between mb-3 border-b border-border pb-2">
          <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Arcade Mandibulaire (Inférieure)
          </span>
          <span className="text-[11px] text-muted-foreground">Quadrant 4 (Droit) • Quadrant 3 (Gauche)</span>
        </div>

        <div className="flex items-center justify-center gap-1 sm:gap-2 overflow-x-auto py-2">
          {/* Quadrant 4 (48 à 41 ou 85 à 81) */}
          <div className="flex items-center gap-1 sm:gap-1.5 border-r-2 border-primary/30 pr-2 sm:pr-3">
            {quadrants.q4.map((fdi) => {
              const d = dentParFdi.get(fdi)
              return (
                <DentItem
                  key={fdi}
                  dent={d}
                  isSelected={dentSelectionneeFdi === fdi}
                  couleurGlobale={d ? getCouleur(d.etat_actuel) : COULEUR_SAINE}
                  onClick={() => d && onSelectDent(d)}
                />
              )
            })}
          </div>

          {/* Quadrant 3 (31 à 38 ou 71 à 75) */}
          <div className="flex items-center gap-1 sm:gap-1.5 pl-2 sm:pl-3">
            {quadrants.q3.map((fdi) => {
              const d = dentParFdi.get(fdi)
              return (
                <DentItem
                  key={fdi}
                  dent={d}
                  isSelected={dentSelectionneeFdi === fdi}
                  couleurGlobale={d ? getCouleur(d.etat_actuel) : COULEUR_SAINE}
                  onClick={() => d && onSelectDent(d)}
                />
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
