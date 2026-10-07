import { useState, useEffect } from 'react'
import { Drawer } from '@/components/ui/drawer'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/stores/toast-store'
import { odontogrammeApi } from '../services/odontogramme-api'
import type { DentOdontogramme, EtatReferentiel } from '../types'

interface DentDrawerProps {
  patientId: string
  dent: DentOdontogramme | null
  open: boolean
  onClose: () => void
  referentielEtats: EtatReferentiel[]
  onSuccess: () => void
}

const FACES_DECOUPEES = [
  { code: 'OCCLUSALE', court: 'O', label: 'Occlusale / Incisive (Centre)' },
  { code: 'VESTIBULAIRE', court: 'V', label: 'Vestibulaire (Côté lèvre/joue)' },
  { code: 'LINGUALE', court: 'L', label: 'Palatine / Linguale (Côté langue/palais)' },
  { code: 'MESIALE', court: 'M', label: 'Mésiale (Vers l’avant)' },
  { code: 'DISTALE', court: 'D', label: 'Distale (Vers l’arrière)' },
]

export function DentDrawer({
  patientId,
  dent,
  open,
  onClose,
  referentielEtats,
  onSuccess,
}: DentDrawerProps) {
  const [etatActuel, setEtatActuel] = useState(dent?.etat_actuel ?? 'SAINE')
  const [mobilite, setMobilite] = useState(String(dent?.mobilite ?? 0))
  const [notes, setNotes] = useState(dent?.notes ?? '')
  const [faces, setFaces] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (dent) {
      setEtatActuel(dent.etat_actuel)
      setMobilite(String(dent.mobilite ?? 0))
      setNotes(dent.notes ?? '')

      const initialFaces: Record<string, string> = {}
      FACES_DECOUPEES.forEach((f) => {
        const found = dent.faces.find(
          (fc) => fc.face === f.code || fc.face_courte === f.court,
        )
        initialFaces[f.code] = found ? found.etat : 'SAINE'
      })
      setFaces(initialFaces)
    }
  }, [dent])

  if (!dent) return null

  const handleSave = async () => {
    try {
      setLoading(true)

      // 1. Sauvegarder l'état global
      await odontogrammeApi.modifierDent(patientId, {
        numero_fdi: dent.numero_fdi,
        etat: etatActuel,
        mobilite: parseInt(mobilite, 10),
        notes: notes.trim() || undefined,
      })

      // 2. Sauvegarder les 5 faces
      const facesPayload = Object.entries(faces).map(([face, etat]) => ({
        face,
        etat,
      }))
      await odontogrammeApi.modifierFaces(patientId, dent.numero_fdi, facesPayload)

      toast.success(`Dent ${dent.numero_fdi} enregistrée.`)
      onSuccess()
      onClose()
    } catch {
      // Géré par le toast global
    } finally {
      setLoading(false)
    }
  }

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <span>Dent {dent.numero_fdi}</span>
          {dent.numero_universal && (
            <Badge variant="outline" className="font-mono text-[10px]">
              Univ. {dent.numero_universal}
            </Badge>
          )}
          {dent.a_alerte && <Badge variant="danger">Alerte</Badge>}
        </div>
      }
      description="Modification de l'état clinique, des 5 faces et de la mobilité parodontale"
      width="md"
    >
      <div className="space-y-6">
        {/* État Global */}
        <div className="space-y-2">
          <Label htmlFor="etat-global" required>
            État général de la dent
          </Label>
          <Select
            id="etat-global"
            value={etatActuel}
            onChange={(e) => setEtatActuel(e.target.value)}
          >
            {referentielEtats.map((etat) => (
              <option key={etat.code} value={etat.code}>
                {etat.libelle}
              </option>
            ))}
          </Select>
        </div>

        {/* Mobilité parodontale */}
        <div>
          <Label htmlFor="mobilite">Mobilité parodontale (Indice 0 à 3)</Label>
          <Select
            id="mobilite"
            value={mobilite}
            onChange={(e) => setMobilite(e.target.value)}
          >
            <option value="0">0 : Physiologique (Ancrée)</option>
            <option value="1">1 : Légère mobilité transversale (&lt; 1mm)</option>
            <option value="2">2 : Mobilité transversale marquée (&gt; 1mm)</option>
            <option value="3">3 : Mobilité axiale / Enfoncement</option>
          </Select>
        </div>

        {/* Décomposition par faces */}
        <div className="space-y-3 pt-3 border-t border-border">
          <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Lésions par faces (M, D, V, L/P, O/I)
          </h4>

          <div className="space-y-2.5">
            {FACES_DECOUPEES.map((f) => (
              <div key={f.code} className="flex items-center justify-between gap-3 text-xs">
                <span className="font-medium text-foreground w-1/2 truncate" title={f.label}>
                  <strong className="text-primary font-mono mr-1">[{f.court}]</strong> {f.label}
                </span>
                <select
                  value={faces[f.code] ?? 'SAINE'}
                  onChange={(e) => setFaces({ ...faces, [f.code]: e.target.value })}
                  className="w-1/2 rounded-lg border border-input bg-card px-2.5 py-1 text-xs text-foreground"
                >
                  <option value="SAINE">Saine</option>
                  <option value="CARIE_DEBUTANTE">Carie débutante</option>
                  <option value="CARIE_AVANCEE">Carie avancée</option>
                  <option value="SOIGNEE">Obturation / Composite</option>
                  <option value="COURONNE">Couronne</option>
                </select>
              </div>
            ))}
          </div>
        </div>

        {/* Notes */}
        <div>
          <Label htmlFor="dent-notes">Notes & Recommandations opératoires</Label>
          <Textarea
            id="dent-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Ex: Reprise de traitement canalaire prévue, fêlure coronaire..."
            rows={3}
          />
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4 border-t border-border">
          <Button variant="outline" onClick={onClose} disabled={loading} className="flex-1">
            Fermer
          </Button>
          <Button variant="primary" onClick={handleSave} loading={loading} className="flex-1">
            Enregistrer
          </Button>
        </div>
      </div>
    </Drawer>
  )
}
