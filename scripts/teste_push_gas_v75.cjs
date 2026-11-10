'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync(__dirname + '/haize_push_recuperacao_testes_v75.gs', 'utf8');

function ambiente(codigo = 200, resposta = { status: 'online', timestamp: '2026-11-10T13:50:00Z' }) {
  let agora = 1794318000000;
  let acessos = 0;
  let gravacoes = 0;
  let removidos = 0;
  let lock = true;
  const props = new Map();
  const outros = { funcao: 'outroGatilho' };
  const triggers = [outros];
  const scriptapp = {
    getProjectTriggers: () => triggers.map(t => ({getHandlerFunction: () => t.funcao, ref: t})),
    deleteTrigger: t => { const idx = triggers.indexOf(t.ref); if (idx >= 0) triggers.splice(idx, 1); removidos++; },
    newTrigger: name => ({timeBased: () => ({everyHours: n => ({create: () => {assert.equal(n, 1); triggers.push({funcao:name}); gravacoes++;}})})}),
  };
  const context = vm.createContext({
    Date: {now: () => agora}, Number, Object, String, Error, JSON,
    ScriptApp:scriptapp,
    PropertiesService:{getScriptProperties:()=>({getProperty:(k)=>props.get(k),setProperty:(k,v)=>props.set(k,v),deleteProperty:(k)=>props.delete(k)})},
    LockService:{getScriptLock:()=>({tryLock:()=>lock,releaseLock:()=>{}})},
    UrlFetchApp:{fetch:(url,args)=>{assert.equal(url,'https://controladoria-api-teste.onrender.com/status');assert.equal(args.method,'get');acessos++;return{getResponseCode:()=>codigo,getContentText:()=>JSON.stringify(resposta)}}},
    Logger:{log:()=>{}},
  });
  new vm.Script(script).runInContext(context);
  return {context, props, triggers, get acessos(){return acessos},get gravacoes(){return gravacoes},get removidos(){return removidos},avancar:(ms)=>{agora+=ms}, setLock:x=>{lock=x}};
}

{const t=ambiente();t.context.haizePushV75InstalarTeste48Horas();assert.equal(t.acessos,1);assert.equal(t.gravacoes,1);assert.equal(t.triggers.length,2);assert.throws(()=>t.context.haizePushV75InstalarTeste48Horas(),/ja esta instalado/);t.context.haizePushV75VerificarServidorTeste();assert.equal(t.acessos,2);t.setLock(false);t.context.haizePushV75VerificarServidorTeste();assert.equal(t.acessos,2);t.avancar(48*60*60*1000);t.setLock(true);t.context.haizePushV75VerificarServidorTeste();assert.equal(t.acessos,2);assert.equal(t.triggers.length,1);assert.equal(t.triggers[0].funcao,'outroGatilho');assert.equal(t.props.size,0);}
{const t=ambiente(503);assert.throws(()=>t.context.haizePushV75InstalarTeste48Horas(),/HTTP 503/);assert.equal(t.gravacoes,0);assert.equal(t.props.size,0);}
{const t=ambiente(200,{status:'offline'});assert.throws(()=>t.context.haizePushV75InstalarTeste48Horas(),/inesperada/);assert.equal(t.gravacoes,0);}
{const t=ambiente();t.context.haizePushV75InstalarTeste48Horas();t.context.haizePushV75CancelarTeste();assert.equal(t.triggers.length,1);assert.equal(t.props.size,0);assert.equal(t.removidos,1);}
console.log('OK: 4 cenarios de instalacao, expiracao, acesso, falha e cancelamento');
