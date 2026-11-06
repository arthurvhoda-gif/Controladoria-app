const {test} = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../integracoes/google_drive/ArmazenamentoV72.gs'), 'utf8');
function setup() {
  const files = new Map();
  const secret = 'a'.repeat(64);
  const blob = (v, mime, name) => ({name, getBytes: () => Array.from(typeof v === 'string' ? Buffer.from(v) : Buffer.from(v))});
  const folder = {getName: () => 'HAIZE_APP_TESTES_V72', isTrashed: () => false,
    getSharingAccess: () => 'private', getEditors: () => [], getViewers: () => [],
    getFilesByName(name) {const values = files.has(name) ? [files.get(name)] : []; return {hasNext: () => !!values.length, next: () => values.shift()};},
    createFile(b) {const f = {isTrashed: () => false, getSharingAccess: () => 'private', getEditors: () => [], getViewers: () => [], getSize: () => b.getBytes().length, getBlob: () => b}; files.set(b.name, f); return f;}};
  const ctx = vm.createContext({console, Date, PropertiesService: {getScriptProperties: () => ({getProperty: k => k.endsWith('SECRET') ? secret : 'folder'})},
    DriveApp: {Access: {PRIVATE: 'private'}, getFolderById: () => folder},
    LockService: {getScriptLock: () => ({tryLock: () => true, releaseLock() {}})},
    ContentService: {MimeType: {JSON: 'json'}, createTextOutput: s => ({setMimeType() {return this;}, getContent: () => s})},
    Utilities: {DigestAlgorithm: {SHA_256: 'sha256'}, Charset: {UTF_8: 'utf8'},
      computeDigest: (_, bytes) => Array.from(crypto.createHash('sha256').update(Buffer.from(bytes)).digest()),
      computeHmacSha256Signature: (p, s) => Array.from(crypto.createHmac('sha256', s).update(p).digest()),
      base64Encode: b => Buffer.from(b).toString('base64'), base64Decode: s => Array.from(Buffer.from(s, 'base64')),
      newBlob: blob, getUuid: crypto.randomUUID}});
  vm.runInContext(source, ctx);
  function send(d, mutate) {
    const payload = JSON.stringify({version: 1, ts: Math.floor(Date.now()/1000), ...d});
    const e = {payload, signature: crypto.createHmac('sha256', secret).update(payload).digest('hex')};
    if (mutate) mutate(e);
    return JSON.parse(ctx.doPost({postData: {contents: JSON.stringify(e)}}).getContent());
  }
  const put = (data = 'evidência', key = 'b'.repeat(32)) => ({op: 'put', key, size: Buffer.byteLength(data), data: Buffer.from(data).toString('base64'), sha256: crypto.createHash('sha256').update(data).digest('hex')});
  return {ctx, send, put, files, folder};
}
test('roundtrip exato, repetição idempotente e conflito sem sobrescrita', () => {
  const {send, put, files} = setup(); const d = put();
  assert.equal(send(d).repeated, false); assert.equal(send(d).repeated, true); assert.equal(files.size, 1);
  assert.equal(send({op:'get', key:d.key}).data, d.data);
  assert.equal(send(put('outro')).error, 'CONFLITO');
  assert.equal(send({op:'get', key:d.key}).sha256, d.sha256);
});
test('assinatura inválida e adulteração rejeitadas antes do Drive', () => {
  const {ctx, send, put} = setup(); ctx.DriveApp.getFolderById = () => {throw new Error('não deveria acessar');};
  assert.equal(send(put(), e => e.signature = '0'.repeat(64)).error, 'AUTENTICACAO');
  assert.equal(send(put(), e => e.payload += ' ').error, 'AUTENTICACAO');
});
test('expiração passada e futura', () => {const {send} = setup(); for (const ts of [1, Math.floor(Date.now()/1000)+600]) assert.equal(send({op:'ping',ts}).error,'EXPIRADO');});
test('hash e tamanho divergentes não gravam', () => {const {send,put,files}=setup(); assert.equal(send({...put(),sha256:'0'.repeat(64)}).error,'INTEGRIDADE'); assert.equal(send({...put(),size:1}).error,'INTEGRIDADE'); assert.equal(files.size,0);});
test('vazio e acima de 20 MiB rejeitados', () => {const {send,put}=setup(); for (const size of [0,20971521]) assert.equal(send({...put(),size}).error,'LIMITE');});
test('chave inválida, travessia e ID externo rejeitados', () => {const {send}=setup(); for (const key of ['../segredo','drive-file-id','']) assert.equal(send({op:'get',key}).error,'CHAVE');});
test('chave inexistente e exclusão não permitida', () => {const {send}=setup(); assert.equal(send({op:'get',key:'c'.repeat(32)}).error,'NAO_ENCONTRADO'); assert.equal(send({op:'delete'}).error,'OPERACAO');});
test('pasta pública ou compartilhada recusada', () => {const {send,folder}=setup(); folder.getSharingAccess=()=> 'public'; assert.equal(send({op:'ping'}).error,'PASTA_COMPARTILHADA'); folder.getSharingAccess=()=> 'private'; folder.getEditors=()=> ['editor']; assert.equal(send({op:'ping'}).error,'PASTA_COMPARTILHADA');});
test('arquivo compartilhado não retornado', () => {const {send,put,files}=setup();const d=put();send(d);files.values().next().value.getViewers=()=> ['viewer'];assert.equal(send({op:'get',key:d.key}).error,'ARQUIVO_COMPARTILHADO');});
test('GET não expõe arquivos e erros do provedor são sanitizados', () => {const {ctx,send}=setup();assert.equal(JSON.parse(ctx.doGet().getContent()).ok,false);ctx.DriveApp.getFolderById=()=> {throw new Error('segredo-do-provedor');};assert.deepEqual(send({op:'ping'}),{ok:false,error:'INDISPONIVEL'});});
test('JSON malformado e versão errada', () => {const {ctx,send}=setup();assert.equal(JSON.parse(ctx.doPost({postData:{contents:'{'}}).getContent()).error,'REQUISICAO');assert.equal(send({op:'ping',version:2}).error,'EXPIRADO');});
test('lock ocupado não grava', () => {const {ctx,send,put,files}=setup();ctx.LockService.getScriptLock=()=> ({tryLock:()=>false});assert.equal(send(put()).error,'OCUPADO');assert.equal(files.size,0);});
test('autoteste do editor exercita ponte completa', () => {const {ctx,files}=setup();ctx.validarPonteV72();assert.equal(files.size,1);});
