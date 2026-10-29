import { useEffect, useMemo, useState } from 'react'
import './GestaoContatosWhatsApp.css'

const texto = value => String(value || '').toLocaleLowerCase('pt-BR')

export default function GestaoContatosWhatsApp({ apiUrl, token }) {
  const [usuarios, setUsuarios] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')
  const [busca, setBusca] = useState('')
  const [perfil, setPerfil] = useState('todos')
  const [status, setStatus] = useState('todos')
  const [editando, setEditando] = useState(null)
  const [numero, setNumero] = useState('')
  const [salvando, setSalvando] = useState(false)

  async function carregar(silencioso = false) {
    if (!silencioso) setCarregando(true)
    setErro('')
    try {
      const resposta = await fetch(`${apiUrl}/avisos-whatsapp/admin/usuarios`, {
        headers: { Authorization: `Bearer ${token}` }, cache: 'no-store'
      })
      const dados = await resposta.json()
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar os cadastros.')
      setUsuarios(dados)
    } catch (e) { setErro(e.message) }
    finally { setCarregando(false) }
  }

  useEffect(() => { carregar() }, [apiUrl, token])

  const filtrados = useMemo(() => usuarios.filter(u => {
    const termo = texto(busca.trim())
    const alvo = texto([u.nome, u.email, u.perfil, u.condominio_nome, u.numero, u.id].join(' '))
    if (termo && !alvo.includes(termo)) return false
    if (perfil !== 'todos' && u.perfil !== perfil) return false
    const situacao = !u.numero ? 'sem_numero' : u.receber_alertas ? 'autorizado' : 'aguardando'
    return status === 'todos' || status === situacao
  }), [usuarios, busca, perfil, status])

  const comNumero = usuarios.filter(u => Boolean(u.numero)).length
  const autorizados = usuarios.filter(u => Boolean(u.numero) && u.receber_alertas).length

  const comecarEdicao = u => { setEditando(u.id); setNumero(u.numero || ''); setErro(''); setAviso('') }

  async function salvar(e, u) {
    e.preventDefault()
    setSalvando(true); setErro(''); setAviso('')
    try {
      const resposta = await fetch(`${apiUrl}/avisos-whatsapp/admin/usuarios/${u.id}/numero`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ numero }),
      })
      const dados = await resposta.json()
      if (!resposta.ok) throw new Error(typeof dados.detail === 'string' ? dados.detail : 'Não foi possível salvar.')
      setUsuarios(lista => lista.map(item => item.id === u.id
        ? { ...item, numero: dados.numero || '', receber_alertas: Boolean(dados.receber_alertas), consentido_em: dados.alterado ? null : item.consentido_em }
        : item))
      setEditando(null)
      setAviso(dados.alterado
        ? `Número de ${u.nome} atualizado. A pessoa precisará autorizar o recebimento dos avisos.`
        : `Cadastro de ${u.nome} já estava atualizado.`)
    } catch (e) { setErro(e.message) }
    finally { setSalvando(false) }
  }

  return <section className="wa-admin" aria-label="Gestão de contatos WhatsApp">
    <div className="wa-admin-heading">
      <div><p className="wa-admin-eyebrow">GESTÃO DE USUÁRIOS</p>
        <h2>Contatos para notificações</h2>
        <p>Cadastre os números de todos os usuários existentes, sem depender do preenchimento individual.</p>
      </div>
      <button className="wa-admin-button wa-admin-refresh" type="button" onClick={() => carregar()} disabled={carregando || salvando}>Atualizar lista</button>
    </div>

    <div className="wa-admin-metrics">
      <div><small>Cadastros existentes</small><strong>{usuarios.length}</strong></div>
      <div><small>Com número</small><strong>{comNumero}</strong></div>
      <div><small>Autorizados</small><strong>{autorizados}</strong></div>
      <div><small>Aguardando cadastro</small><strong>{usuarios.length - comNumero}</strong></div>
    </div>

    <p className="wa-admin-note"><strong>Importante:</strong> a Controladoria informa os telefones, mas não autoriza mensagens em nome dos colaboradores. Ao trocar um número, o consentimento anterior é cancelado. Nenhum WhatsApp é enviado nesta versão.</p>

    <div className="wa-admin-filters">
      <label>Buscar usuário, e-mail, condomínio ou telefone
        <input value={busca} onChange={e => setBusca(e.target.value)} placeholder="Digite para filtrar..." />
      </label>
      <label>Perfil
        <select value={perfil} onChange={e => setPerfil(e.target.value)}>
          <option value="todos">Todos os perfis</option>
          <option value="Controladoria">Controladoria</option>
          <option value="Checklist">Zeladores (Checklist)</option>
          <option value="Solicitante">Solicitantes</option>
        </select>
      </label>
      <label>Situação
        <select value={status} onChange={e => setStatus(e.target.value)}>
          <option value="todos">Todas</option>
          <option value="sem_numero">Sem número</option>
          <option value="aguardando">Aguardando autorização</option>
          <option value="autorizado">Autorizado</option>
        </select>
      </label>
    </div>

    {erro && <p className="wa-admin-alert wa-admin-error" role="alert">{erro}</p>}
    {aviso && <p className="wa-admin-alert wa-admin-success" role="status">{aviso}</p>}

    {carregando ? <p className="wa-admin-empty">Carregando cadastros...</p> :
      <div className="wa-admin-list">
        <div className="wa-admin-listhead"><strong>Usuários cadastrados</strong><span>{filtrados.length} exibidos de {usuarios.length}</span></div>
        {filtrados.length === 0 ? <p className="wa-admin-empty">Nenhum usuário encontrado com esses filtros.</p>
          : filtrados.map(u => <article className="wa-admin-user" key={u.id}>
              <div className="wa-admin-user-info">
                <div className="wa-admin-avatar" aria-hidden="true">{u.nome?.charAt(0)?.toUpperCase() || '?'}</div>
                <div>
                  <strong>{u.nome}</strong>
                  <span className="wa-admin-email">{u.email}</span>
                  <span className="wa-admin-meta">{u.perfil === 'Checklist' ? 'Zelador (Checklist)' : u.perfil}
                    {u.condominio_nome ? ` · ${u.condominio_nome}` : ''}</span>
                </div>
              </div>
              <div className="wa-admin-contact">
                {editando === u.id ? <form onSubmit={e => salvar(e, u)} className="wa-admin-edit">
                  <label htmlFor={`wa-numero-${u.id}`}>Celular com DDD</label>
                  <input id={`wa-numero-${u.id}`} autoFocus inputMode="tel" placeholder="(43) 99999-9999" value={numero} onChange={e => setNumero(e.target.value)} maxLength={35} />
                  <small>Deixe em branco para remover o número.</small>
                  <div className="wa-admin-actions"><button className="wa-admin-button wa-admin-save" type="submit" disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar'}</button>
                    <button className="wa-admin-button" type="button" onClick={() => setEditando(null)} disabled={salvando}>Cancelar</button></div>
                </form> : <>
                  <div><span className="wa-admin-phone-label">Celular</span><strong className="wa-admin-phone">{u.numero || 'Não cadastrado'}</strong></div>
                  <span className={`wa-admin-state ${!u.numero ? 'wa-admin-missing' : u.receber_alertas ? 'wa-admin-opted' : 'wa-admin-pending'}`}>
                    {!u.numero ? 'Sem número' : u.receber_alertas ? 'Autorizado pela pessoa' : 'Aguardando autorização'}
                  </span>
                  <button type="button" className="wa-admin-button wa-admin-change" onClick={() => comecarEdicao(u)} disabled={editando !== null}>Editar número</button>
                </>}
              </div>
            </article>)}
      </div>
    }
  </section>
}
