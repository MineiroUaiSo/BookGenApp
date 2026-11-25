interface Props { checked: boolean; onChange: (v: boolean) => void }

/** Opt-in (desmarcado por padrão) para enviar a IMAGEM da radiografia à IA na nuvem. Sem marcar, só medidas e regras vão ao texto. */
export default function ImageConsent({ checked, onChange }: Props) {
  return (
    <div className="image-consent">
      <label className="switch">
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        Enviar imagem à IA na nuvem
      </label>
      <p className="hint" role="note">
        Por padrão só medidas e regras são enviadas. Ao marcar, a radiografia é enviada ao provedor de IA na nuvem
        (nunca com texto queimado detectado). Confirme que não há dado que identifique o paciente — LGPD.
      </p>
    </div>
  );
}
