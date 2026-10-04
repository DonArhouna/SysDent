import { useState, useEffect, type FormEvent } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/stores/toast-store'
import { patientsApi } from '../services/patients-api'
import type { Patient, PatientCreateInput, PatientUpdateInput, Sexe, TypePieceIdentite } from '../types'

interface PatientFormModalProps {
  open: boolean
  onClose: () => void
  onSuccess: (patient: Patient) => void
  patientToEdit?: Patient | null
}

export function PatientFormModal({
  open,
  onClose,
  onSuccess,
  patientToEdit,
}: PatientFormModalProps) {
  const isEditing = Boolean(patientToEdit)

  // Identité
  const [prenom, setPrenom] = useState('')
  const [nom, setNom] = useState('')
  const [dateNaissance, setDateNaissance] = useState('')
  const [sexe, setSexe] = useState<Sexe>('F')
  const [groupeSanguin, setGroupeSanguin] = useState('')
  const [typePiece, setTypePiece] = useState<TypePieceIdentite | ''>('')
  const [numeroPiece, setNumeroPiece] = useState('')

  // Contact
  const [telephone1, setTelephone1] = useState('')
  const [telephone2, setTelephone2] = useState('')
  const [email, setEmail] = useState('')
  const [adresse, setAdresse] = useState('')
  const [ville, setVille] = useState('Dakar')
  const [profession, setProfession] = useState('')
  const [employeur, setEmployeur] = useState('')
  const [source, setSource] = useState('')
  const [notes, setNotes] = useState('')

  // État général initial (création uniquement)
  const [grossesse, setGrossesse] = useState(false)
  const [allaitement, setAllaitement] = useState(false)
  const [diabete, setDiabete] = useState(false)
  const [hta, setHta] = useState(false)
  const [allergieSubstance, setAllergieSubstance] = useState('')

  const [loading, setLoading] = useState(false)
  const [erreurs, setErreurs] = useState<Record<string, string>>({})

  useEffect(() => {
    if (patientToEdit) {
      setPrenom(patientToEdit.prenom)
      setNom(patientToEdit.nom)
      setDateNaissance(patientToEdit.date_naissance ? patientToEdit.date_naissance.slice(0, 10) : '')
      setSexe(patientToEdit.sexe)
      setGroupeSanguin(patientToEdit.groupe_sanguin ?? '')
      setTypePiece(patientToEdit.type_piece_identite ?? '')
      setNumeroPiece(patientToEdit.numero_piece_identite ?? '')
      setTelephone1(patientToEdit.telephone_1)
      setTelephone2(patientToEdit.telephone_2 ?? '')
      setEmail(patientToEdit.email ?? '')
      setAdresse(patientToEdit.adresse ?? '')
      setVille(patientToEdit.ville ?? 'Dakar')
      setProfession(patientToEdit.profession ?? '')
      setEmployeur(patientToEdit.employeur ?? '')
      setSource(patientToEdit.source ?? '')
      setNotes(patientToEdit.notes ?? '')
    } else {
      // Reset
      setPrenom('')
      setNom('')
      setDateNaissance('')
      setSexe('F')
      setGroupeSanguin('')
      setTypePiece('')
      setNumeroPiece('')
      setTelephone1('')
      setTelephone2('')
      setEmail('')
      setAdresse('')
      setVille('Dakar')
      setProfession('')
      setEmployeur('')
      setSource('')
      setNotes('')
      setGrossesse(false)
      setAllaitement(false)
      setDiabete(false)
      setHta(false)
      setAllergieSubstance('')
    }
    setErreurs({})
  }, [patientToEdit, open])

  const valider = () => {
    const err: Record<string, string> = {}
    if (!prenom.trim()) err.prenom = 'Le prénom est obligatoire.'
    if (!nom.trim()) err.nom = 'Le nom de famille est obligatoire.'
    if (!dateNaissance) err.dateNaissance = 'La date de naissance est obligatoire.'
    if (!telephone1.trim() || telephone1.replace(/\D/g, '').length < 6) {
      err.telephone1 = 'Le numéro de téléphone principal doit comporter au moins 6 chiffres.'
    }
    setErreurs(err)
    return Object.keys(err).length === 0
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!valider()) return

    try {
      setLoading(true)

      if (isEditing && patientToEdit) {
        const payload: PatientUpdateInput = {
          prenom: prenom.trim(),
          nom: nom.trim(),
          date_naissance: dateNaissance,
          sexe,
          telephone_1: telephone1.trim(),
          telephone_2: telephone2.trim() || undefined,
          email: email.trim() || undefined,
          adresse: adresse.trim() || undefined,
          ville: ville.trim() || undefined,
          type_piece_identite: (typePiece as TypePieceIdentite) || undefined,
          numero_piece_identite: numeroPiece.trim() || undefined,
          groupe_sanguin: groupeSanguin.trim() || undefined,
          profession: profession.trim() || undefined,
          employeur: employeur.trim() || undefined,
          source: source.trim() || undefined,
          notes: notes.trim() || undefined,
        }

        const res = await patientsApi.modifier(patientToEdit.id, payload)
        toast.success(`Dossier ${res.data.numero_dossier} mis à jour avec succès.`)
        onSuccess(res.data)
        onClose()
      } else {
        const payload: PatientCreateInput = {
          prenom: prenom.trim(),
          nom: nom.trim(),
          date_naissance: dateNaissance,
          sexe,
          telephone_1: telephone1.trim(),
          telephone_2: telephone2.trim() || undefined,
          email: email.trim() || undefined,
          adresse: adresse.trim() || undefined,
          ville: ville.trim() || undefined,
          type_piece_identite: (typePiece as TypePieceIdentite) || undefined,
          numero_piece_identite: numeroPiece.trim() || undefined,
          groupe_sanguin: groupeSanguin.trim() || undefined,
          profession: profession.trim() || undefined,
          employeur: employeur.trim() || undefined,
          source: source.trim() || undefined,
          notes: notes.trim() || undefined,
          etat_general: {
            grossesse,
            allaitement,
            diabete,
            hta,
            tabac: false,
            alcool: false,
            allergies: allergieSubstance.trim()
              ? [{ substance: allergieSubstance.trim(), severite: 'grave' }]
              : [],
          },
        }

        const res = await patientsApi.creer(payload)
        toast.success(`Dossier ${res.data.numero_dossier} créé avec succès.`)
        onSuccess(res.data)
        onClose()
      }
    } catch {
      // Erreur déjà affichée par le toast global de l'api
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEditing ? 'Modifier la fiche patient' : 'Nouveau Dossier Patient'}
      description={
        isEditing
          ? `Mise à jour des coordonnées de ${patientToEdit?.prenom} ${patientToEdit?.nom}`
          : 'Le numéro de dossier SYS-AAAAMMJJ-NNNN sera généré automatiquement.'
      }
      maxWidth="3xl"
    >
      <form onSubmit={handleSubmit} className="space-y-6 pt-2">
        {/* Section 1 : État Civil */}
        <div className="space-y-3">
          <h4 className="text-xs font-bold uppercase tracking-wider text-primary border-b border-border pb-1">
            1. État Civil & Identité
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <Label htmlFor="prenom" required>
                Prénom
              </Label>
              <Input
                id="prenom"
                value={prenom}
                onChange={(e) => setPrenom(e.target.value)}
                placeholder="Ex: Aminata"
                error={erreurs.prenom}
                required
              />
            </div>
            <div>
              <Label htmlFor="nom" required>
                Nom
              </Label>
              <Input
                id="nom"
                value={nom}
                onChange={(e) => setNom(e.target.value)}
                placeholder="Ex: Diop"
                error={erreurs.nom}
                required
              />
            </div>
            <div>
              <Label htmlFor="sexe" required>
                Sexe
              </Label>
              <Select
                id="sexe"
                value={sexe}
                onChange={(e) => setSexe(e.target.value as Sexe)}
              >
                <option value="F">Féminin</option>
                <option value="M">Masculin</option>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <Label htmlFor="dateNaissance" required>
                Date de naissance
              </Label>
              <Input
                id="dateNaissance"
                type="date"
                value={dateNaissance}
                onChange={(e) => setDateNaissance(e.target.value)}
                error={erreurs.dateNaissance}
                required
              />
            </div>
            <div>
              <Label htmlFor="groupeSanguin">Groupe Sanguin</Label>
              <Select
                id="groupeSanguin"
                value={groupeSanguin}
                onChange={(e) => setGroupeSanguin(e.target.value)}
              >
                <option value="">Non déterminé</option>
                <option value="A+">A+</option>
                <option value="A-">A-</option>
                <option value="B+">B+</option>
                <option value="B-">B-</option>
                <option value="AB+">AB+</option>
                <option value="AB-">AB-</option>
                <option value="O+">O+</option>
                <option value="O-">O-</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="typePiece">Type de pièce</Label>
              <Select
                id="typePiece"
                value={typePiece}
                onChange={(e) => setTypePiece(e.target.value as TypePieceIdentite)}
              >
                <option value="">Aucune</option>
                <option value="CNI">CNI Sénégalaise</option>
                <option value="PASSEPORT">Passeport</option>
                <option value="PERMIS">Permis de conduire</option>
                <option value="AUTRE">Autre pièce</option>
              </Select>
            </div>
          </div>

          {typePiece && (
            <div>
              <Label htmlFor="numeroPiece">Numéro de pièce d'identité</Label>
              <Input
                id="numeroPiece"
                value={numeroPiece}
                onChange={(e) => setNumeroPiece(e.target.value)}
                placeholder="Ex: 1 751 1990 01234"
              />
            </div>
          )}
        </div>

        {/* Section 2 : Coordonnées & Contact */}
        <div className="space-y-3">
          <h4 className="text-xs font-bold uppercase tracking-wider text-primary border-b border-border pb-1">
            2. Coordonnées & Contact
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="telephone1" required>
                Téléphone principal (joignable / Wave)
              </Label>
              <Input
                id="telephone1"
                value={telephone1}
                onChange={(e) => setTelephone1(e.target.value)}
                placeholder="Ex: 77 123 45 67"
                error={erreurs.telephone1}
                required
              />
            </div>
            <div>
              <Label htmlFor="telephone2">Téléphone secondaire / Proche</Label>
              <Input
                id="telephone2"
                value={telephone2}
                onChange={(e) => setTelephone2(e.target.value)}
                placeholder="Ex: 70 987 65 43"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="patient@exemple.sn"
              />
            </div>
            <div>
              <Label htmlFor="ville">Ville</Label>
              <Input
                id="ville"
                value={ville}
                onChange={(e) => setVille(e.target.value)}
                placeholder="Ex: Dakar, Thiès, Saint-Louis"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="adresse">Adresse complète</Label>
            <Input
              id="adresse"
              value={adresse}
              onChange={(e) => setAdresse(e.target.value)}
              placeholder="Ex: Mermoz Pyrotechnie, Villa 123"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="profession">Profession</Label>
              <Input
                id="profession"
                value={profession}
                onChange={(e) => setProfession(e.target.value)}
                placeholder="Ex: Enseignant, Cadre..."
              />
            </div>
            <div>
              <Label htmlFor="source">Comment a-t-il connu le cabinet ?</Label>
              <Select
                id="source"
                value={source}
                onChange={(e) => setSource(e.target.value)}
              >
                <option value="">Non précisé</option>
                <option value="Recommandation">Recommandation patient</option>
                <option value="Réseaux sociaux">Réseaux sociaux / Web</option>
                <option value="Passage">Passage spontané</option>
                <option value="Assurance">Partenaire / Assurance</option>
              </Select>
            </div>
          </div>
        </div>

        {/* Section 3 : État général rapide (seulement à la création) */}
        {!isEditing && (
          <div className="space-y-3 rounded-xl border border-warning/30 bg-warning/5 p-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-warning dark:text-warning">
              3. Vigilances médicales d'accueil (facultatif)
            </h4>
            <p className="text-xs text-muted-foreground">
              Signalez immédiatement les contre-indications majeures si le patient en fait part dès l'accueil.
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
              <label className="flex items-center gap-2 text-xs font-medium text-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={grossesse}
                  onChange={(e) => setGrossesse(e.target.checked)}
                  className="rounded border-border text-primary focus:ring-primary"
                />
                <span>Grossesse</span>
              </label>

              <label className="flex items-center gap-2 text-xs font-medium text-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={allaitement}
                  onChange={(e) => setAllaitement(e.target.checked)}
                  className="rounded border-border text-primary focus:ring-primary"
                />
                <span>Allaitement</span>
              </label>

              <label className="flex items-center gap-2 text-xs font-medium text-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={diabete}
                  onChange={(e) => setDiabete(e.target.checked)}
                  className="rounded border-border text-primary focus:ring-primary"
                />
                <span>Diabète</span>
              </label>

              <label className="flex items-center gap-2 text-xs font-medium text-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={hta}
                  onChange={(e) => setHta(e.target.checked)}
                  className="rounded border-border text-primary focus:ring-primary"
                />
                <span>HTA</span>
              </label>
            </div>

            <div className="pt-2">
              <Label htmlFor="allergie">Allergie majeure connue (ex: Pénicilline, Latex)</Label>
              <Input
                id="allergie"
                value={allergieSubstance}
                onChange={(e) => setAllergieSubstance(e.target.value)}
                placeholder="Ex: Pénicilline, Aspirine..."
              />
            </div>
          </div>
        )}

        <div>
          <Label htmlFor="notes">Observations cliniques ou administratives</Label>
          <Textarea
            id="notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Remarques particulières, préférences horaires, etc."
            rows={2}
          />
        </div>

        <div className="flex justify-end gap-3 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
            Annuler
          </Button>
          <Button type="submit" variant="primary" loading={loading}>
            {isEditing ? 'Enregistrer les modifications' : 'Créer le dossier patient'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
