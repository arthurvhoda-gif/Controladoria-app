import { useEffect, useState } from 'react'

export default function PreferenciasWhatsApp({ apiUrl, token, onClose }) {
  const [numero, setNumero] = useState('')
  const [receberAlertas, setReceberAlertas] = useState(false)
  const [carregando, setCarregando] = useState(true)
  const [salvando, setSalvando] = useState(false)
  const [aviso, setAviso] = useState('')
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    fetch(`${apiUrl}/avisos-whatsapp/me`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' })
      .then(async r => { if (!r.ok) throw new Error('Não foi possível carregar suas preferências.'); return r.json() })
      .then(d => { if (ativo) { setNumero(d.numero || ''); setReceberAlertas(Boolean(d.receber_alertas)) } })
      .catch(e => { if (ativo) setErro(e.message) })
      .finally(() => { if (ativo) setCarregando(false) })
    return () => { ativo = false }
  }, [apiUrl, token])

  const salvar = async e => {
    e.preventDefault(); setErro(''); setAviso(''); setSalvando(true)
    try {
      const res = await fetch(`${apiUrl}/avisos-whatsapp/me`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ receber_alertas: receberAlertas }),
      })
      const d = await res.json()
      if (!res.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'Não foi possível salvar.')
      setNumero(d.numero || '')
      setReceberAlertas(Boolean(d.receber_alertas))
      setAviso('Preferências salvas. Nenhum WhatsApp é enviado nesta etapa de testes.')
    } catch (e) { setErro(e.message) } finally { setSalvando(false) }
  }

  return <div className="modal-overlay" style={{ zIndex: 99999 }} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
    <div className="modal" role="dialog" aria-modal="true" aria-label="Avisos pelo WhatsApp" style={{ maxWidth: 480 }}>
      <div className="modal-header"><h3>Avisos pelo WhatsApp</h3><button type="button" className="modal-close" onClick={onClose}>×</button></div>
      <form onSubmit={salvar}>
        <div className="modal-body" style={{ display: 'grid', gap: 14 }}>
          <p style={{ fontSize: 13, lineHeight: 1.5 }}>A Controladoria cadastra seu número de contato. Você escolhe se deseja receber avisos operacionais pelo WhatsApp.</p>
          {carregando ? <p>Carregando...</p> : <>
            <div className="form-group"><label>Celular cadastrado pela Controladoria</label>
              <div style={{ border: '1px solid #cbd5e1', borderRadius: 8, padding: '10px 12px', background: '#f8fafc', fontWeight: 650 }}>
                {numero || 'Ainda não cadastrado'}
              </div></div>
            {!numero && <p style={{ color: '#92400e', fontSize: 13 }}>Peça à Controladoria para cadastrar seu celular antes de autorizar os avisos.</p>}
            <label style={{ display: 'flex', gap: 9, alignItems: 'flex-start', fontSize: 13 }}>
              <input type="checkbox" disabled={!numero} checked={receberAlertas} onChange={e => setReceberAlertas(e.target.checked)} />
              Concordo em receber avisos operacionais da Haize neste número. Posso desativar quando quiser.
            </label>
          </>}
          <p style={{ fontSize: 12, color: '#64748b' }}>Preparação: nenhum WhatsApp será enviado até a integração oficial ser ativada pela empresa.</p>
          {erro && <p role="alert" style={{ color: '#b91c1c', fontSize: 13 }}>{erro}</p>}
          {aviso && <p role="status" style={{ color: '#166534', fontSize: 13 }}>{aviso}</p>}
        </div>
        <div className="modal-actions"><button type="button" className="button-secondary" onClick={onClose}>Fechar</button>
          <button type="submit" className="button-primary" disabled={carregando || salvando}>{salvando ? 'Salvando...' : 'Salvar preferências'}</button></div>
      </form>
    </div>
  </div>
}
