/** HAIZE V7.2 — ponte de armazenamento, somente TESTES.
 * Propriedades: HAIZE_STORAGE_FOLDER_ID e HAIZE_STORAGE_SECRET (64 hex).
 * Pasta privada, dedicada e sob controle exclusivo da conta proprietária.
 * Não possui exclusão, sobrescrita, listagem pública ou envio de e-mails.
 * O backend ainda deve autorizar cada usuário/condomínio antes de chamar a ponte.
 */
const V72_MAX_BYTES = 20 * 1024 * 1024;
const V72_MAX_BODY = 29 * 1024 * 1024;

function v72Erro_(codigo) { throw new Error('V72:' + codigo); }
function v72Hex_(bytes) {
  return bytes.map(b => ('0' + ((b + 256) % 256).toString(16)).slice(-2)).join('');
}
function v72Hash_(bytes) {
  return v72Hex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes));
}
function v72Assinar_(payload, segredo) {
  return v72Hex_(Utilities.computeHmacSha256Signature(payload, segredo, Utilities.Charset.UTF_8));
}
function v72Igual_(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
function v72Config_() {
  const p = PropertiesService.getScriptProperties();
  const id = p.getProperty('HAIZE_STORAGE_FOLDER_ID');
  const segredo = p.getProperty('HAIZE_STORAGE_SECRET');
  if (!id || !/^[a-f0-9]{64}$/.test(segredo || '')) v72Erro_('CONFIGURACAO');
  return {id: id, segredo: segredo};
}
function v72Pasta_(id) {
  const pasta = DriveApp.getFolderById(id);
  if (pasta.getName() !== 'HAIZE_APP_TESTES_V72' || pasta.isTrashed()) v72Erro_('PASTA_TESTE');
  if (pasta.getSharingAccess() !== DriveApp.Access.PRIVATE ||
      pasta.getEditors().length || pasta.getViewers().length) v72Erro_('PASTA_COMPARTILHADA');
  return pasta;
}
function v72Arquivo_(pasta, chave) {
  const arquivos = pasta.getFilesByName('haize-v72-' + chave);
  if (!arquivos.hasNext()) return null;
  const arquivo = arquivos.next();
  if (arquivos.hasNext()) v72Erro_('CHAVE_DUPLICADA');
  if (arquivo.isTrashed()) v72Erro_('NAO_ENCONTRADO');
  if (arquivo.getSharingAccess() !== DriveApp.Access.PRIVATE ||
      arquivo.getEditors().length || arquivo.getViewers().length) v72Erro_('ARQUIVO_COMPARTILHADO');
  return arquivo;
}
function v72Ler_(arquivo) {
  if (arquivo.getSize() > V72_MAX_BYTES) v72Erro_('LIMITE');
  return arquivo.getBlob().getBytes();
}
function v72Processar_(corpo) {
  const config = v72Config_();
  if (typeof corpo !== 'string' || corpo.length > V72_MAX_BODY) v72Erro_('REQUISICAO');
  let envelope;
  try { envelope = JSON.parse(corpo); } catch (_) { v72Erro_('REQUISICAO'); }
  if (!envelope || typeof envelope.payload !== 'string' ||
      !/^[a-f0-9]{64}$/.test(envelope.signature || '')) v72Erro_('AUTENTICACAO');
  if (!v72Igual_(v72Assinar_(envelope.payload, config.segredo), envelope.signature)) v72Erro_('AUTENTICACAO');
  let dados;
  try { dados = JSON.parse(envelope.payload); } catch (_) { v72Erro_('REQUISICAO'); }
  if (!dados || dados.version !== 1 || !Number.isInteger(dados.ts) ||
      Math.abs(Math.floor(Date.now() / 1000) - dados.ts) > 300) v72Erro_('EXPIRADO');
  if (!['ping', 'put', 'get'].includes(dados.op)) v72Erro_('OPERACAO');
  if (dados.op !== 'ping' && !/^[a-f0-9]{32}$/.test(dados.key || '')) v72Erro_('CHAVE');
  const pasta = v72Pasta_(config.id);
  if (dados.op === 'ping') return {ok: true, version: 1, ambiente: 'testes'};
  if (dados.op === 'get') {
    const arquivo = v72Arquivo_(pasta, dados.key);
    if (!arquivo) v72Erro_('NAO_ENCONTRADO');
    const bytes = v72Ler_(arquivo);
    return {ok: true, key: dados.key, size: bytes.length, sha256: v72Hash_(bytes), data: Utilities.base64Encode(bytes)};
  }
  if (!Number.isInteger(dados.size) || dados.size < 1 || dados.size > V72_MAX_BYTES) v72Erro_('LIMITE');
  if (!/^[a-f0-9]{64}$/.test(dados.sha256 || '') || typeof dados.data !== 'string' ||
      dados.data.length !== 4 * Math.ceil(dados.size / 3)) v72Erro_('INTEGRIDADE');
  let bytes;
  try { bytes = Utilities.base64Decode(dados.data); } catch (_) { v72Erro_('INTEGRIDADE'); }
  if (bytes.length !== dados.size || Utilities.base64Encode(bytes) !== dados.data ||
      !v72Igual_(v72Hash_(bytes), dados.sha256)) v72Erro_('INTEGRIDADE');
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(15000)) v72Erro_('OCUPADO');
  try {
    let arquivo = v72Arquivo_(pasta, dados.key);
    const repetido = !!arquivo;
    if (!arquivo) {
      arquivo = pasta.createFile(Utilities.newBlob(bytes, 'application/octet-stream', 'haize-v72-' + dados.key));
    }
    // Uma repetição nunca sobrescreve: valida o conteúdo já existente.
    const salvo = v72Ler_(arquivo);
    if (salvo.length !== dados.size || !v72Igual_(v72Hash_(salvo), dados.sha256)) v72Erro_('CONFLITO');
    return {ok: true, key: dados.key, size: salvo.length, sha256: dados.sha256, repeated: repetido};
  } finally { lock.releaseLock(); }
}
function v72Resposta_(dados) {
  return ContentService.createTextOutput(JSON.stringify(dados)).setMimeType(ContentService.MimeType.JSON);
}
function doGet() { return v72Resposta_({ok: false, error: 'POST_ASSINADO_EXIGIDO'}); }
function doPost(e) {
  try {
    return v72Resposta_(v72Processar_(e && e.postData && e.postData.contents));
  } catch (erro) {
    const mensagem = String(erro.message || '');
    const codigo = /^V72:[A-Z_]+$/.test(mensagem) ? mensagem.slice(4) : 'INDISPONIVEL';
    // Nunca retorna exceções do Drive, conteúdo, IDs de pasta ou segredos.
    return v72Resposta_({ok: false, error: codigo});
  }
}
/** Executar no editor antes de implantar. Cria apenas um arquivo fictício.
 * Não testa HTTPS/quotas/carga; esses testes pertencem à homologação.
 */
function validarPonteV72() {
  const config = v72Config_();
  const bytes = Utilities.newBlob('HAIZE V7.2 — evidência fictícia').getBytes();
  const chave = Utilities.getUuid().replace(/-/g, '').toLowerCase();
  function chamar(dados, assinaturaErrada) {
    dados.version = 1;
    dados.ts = Math.floor(Date.now() / 1000);
    const payload = JSON.stringify(dados);
    return JSON.parse(doPost({postData: {contents: JSON.stringify({payload: payload,
      signature: assinaturaErrada ? '0'.repeat(64) : v72Assinar_(payload, config.segredo)})}}).getContent());
  }
  const negado = chamar({op: 'ping'}, true);
  if (negado.ok || negado.error !== 'AUTENTICACAO') throw new Error('Falha ao negar assinatura inválida.');
  const envio = {op: 'put', key: chave, size: bytes.length, sha256: v72Hash_(bytes), data: Utilities.base64Encode(bytes)};
  const primeiro = chamar(envio);
  if (!primeiro.ok || primeiro.repeated) throw new Error('Falha na gravação: ' + primeiro.error);
  const segundo = chamar(envio);
  if (!segundo.ok || !segundo.repeated) throw new Error('Falha na repetição segura.');
  const leitura = chamar({op: 'get', key: chave});
  if (!leitura.ok || leitura.sha256 !== envio.sha256 || leitura.data !== envio.data) throw new Error('Falha na recuperação.');
  console.log('APROVADO: autenticação, gravação, repetição sem duplicar e recuperação íntegra.');
}
