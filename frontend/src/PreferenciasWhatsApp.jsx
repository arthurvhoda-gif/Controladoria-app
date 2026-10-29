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
    fetch(`${apiUrl}/avisos-whatsapp/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) throw new Error('Não foi possível carregar as preferências.')
        return r.json()
      })
      .then((d) => { if (ativo) { setNumero(d.numero || ''); setReceberAlertas(Boolean(d.receber_alertas)) } })
      .catch((e) => { if (ativo) setErro(e.message) })
      .finally(() => { if (ativo) setCarregando(false) })
    return () => { ativo = false }
  }, [apiUrl, token])

  const salvar = async (e) => {
    e.preventDefault(); setErro(''); setAviso(''); setSalvando(true)
    try {
      const r = await fetch(`${apiUrl}/avisos-whatsapp/me`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ numero, receber_alertas: receberAlertas }),
      })
      const dados = await r.json()
      if (!r.ok) throw new Error(typeof dados.detail === 'string' ? dados.detail : 'Não foi possível salvar.')
      setAviso('Preferências salvas. O WhatsApp ainda não envia mensagens nesta versão de testes.')
    } catch (e) { setErro(e.message) } finally { setSalvando(false) }
  }
  return <div className="modal-overlay" style={{ zIndex: 99999 }} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
    <div className="modal" role="dialog" aria-modal="true" aria-label="Avisos pelo WhatsApp" style={{ maxWidth: 450 }}>
      <div className="modal-header"><h3>Avisos pelo WhatsApp</h3><button type="button" className="modal-close" onClick={onClose}>×</button></div>
      <form onSubmit={salvar}>
        <div className="modal-body" style={{ display: 'grid', gap: 14 }}>
          <p style={{ fontSize: 13, lineHeight: 1.5 }}>Cadastre seu número para receber avisos de tarefas da Haize. As ações continuarão exclusivamente no aplicativo.</p>
          {carregando ? <p>Carregando...</p> : <>
            <div className="form-group"><label htmlFor="haize-wa-numero">Celular com DDD</label>
              <input id="haize-wa-numero" inputMode="tel" autoComplete="tel" placeholder="(43) 99999-9999" value={numero} onChange={e => setNumero(e.target.value)} /></div>
            <label style={{ display: 'flex', gap: 9, alignItems: 'flex-start', fontSize: 13 }}>
              <input type="checkbox" checked={receberAlertas} onChange={e => setReceberAlertas(e.target.checked)} />
              Concordo em receber avisos operacionais da Haize neste número pelo WhatsApp. Posso desativar quando quiser.
            </label>
          </>}
          <p style={{ fontSize: 12, color: '#64748b' }}>Fase de preparação: nenhum WhatsApp será enviado até a integração oficial ser ativada pela empresa.</p>
          {erro && <p role="alert" style={{ color: '#b91c1c', fontSize: 13 }}>{erro}</p>}
          {aviso && <p role="status" style={{ color: '#166534', fontSize: 13 }}>{aviso}</p>}
        </div>
        <div className="modal-actions"><button type="button" className="button-secondary" onClick={onClose}>Fechar</button>
        <button type="submit" className="button-primary" disabled={carregando || salvando}>{salvando ? 'Salvando...' : 'Salvar preferências'}</button></div>
      </form>
    </div>
  </div>
}
