import { inputField, textareaField, selectField } from '/controls.js';
const $ = id => document.getElementById(id);
const credential = inputField('Device token', 'device-token', 'password'); $('credential').append(credential.group);
const message = textareaField('Connected persona message (fixture examples use their bundled facts)', 'user-message'); $('message').append(message.group);
const backend = selectField('Execution', 'execution-backend', [['fixture','Synthetic fixture'],['cloud','Gabriel Cloud'],['local','Local appliance']]); $('backend-select').append(backend.group);
const persona = selectField('Persona', 'persona-picker', []); $('persona-select').append(persona.group);
let token = '', catalog = [], selected = 'boli', pending = null;
const colours = {boli:'#f1c644', kai:'#58c58b', chakri:'#70bfb0'};
function select(id) {
  selected = id; persona.control.value = id; pending = null; $('review-actions').hidden = true;
  const pack = catalog.find(p => p.id === id); if (!pack) return;
  $('name').textContent = pack.name; $('domain').textContent = pack.domain; $('boundary').textContent = pack.boundary;
  $('avatar').textContent = pack.name[0]; $('avatar').className = 'avatar avatar-' + (id in colours ? id : 'other');
  for (const button of $('catalog').children) button.classList.toggle('active', button.dataset.persona === id);
  $('result').replaceChildren(); $('status').textContent = 'Ready for ' + pack.name + '.';
}
function render(value) {
  $('result').replaceChildren();
  const caption = document.createElement('h3'); caption.textContent = (value.status || 'Capabilities').replaceAll('_', ' ');
  const pre = document.createElement('pre'); pre.textContent = JSON.stringify(value, null, 2);
  $('result').append(caption, pre);
}
async function api(path, body) {
  const response = await fetch(path, {method: body ? 'POST' : 'GET', headers: {Authorization:'Bearer '+token, 'Content-Type':'application/json'}, ...(body ? {body:JSON.stringify(body)} : {})});
  const value = await response.json(); if (!response.ok) throw new Error(value.error?.message || 'Bridge request failed.'); return value;
}
async function work(action) {
  $('run').disabled = true; $('inspect').disabled = true; $('status').textContent = 'Working…';
  try { await action(); } catch (error) { $('status').textContent = error.message; }
  finally { $('run').disabled = false; $('inspect').disabled = false; }
}
$('connect').onclick = () => work(async () => {
  pending = null; $('review-actions').hidden = true; $('result').replaceChildren();
  catalog = []; $('catalog').replaceChildren(); persona.setOptions([]);
  $('connection').textContent = 'Connecting device…';
  token = credential.control.value.trim(); credential.control.value = '';
  catalog = (await api('/v1/catalog')).personas;
  persona.setOptions(catalog.map(pack => [pack.id, pack.name])); $('catalog').replaceChildren();
  for (const pack of catalog) {
    const button = document.createElement('button'); button.className = 'persona-card'; button.dataset.persona = pack.id;
    const name = document.createElement('strong'); name.textContent = pack.name;
    const domain = document.createElement('span'); domain.textContent = pack.domain;
    button.append(name, domain); button.onclick = () => select(pack.id); $('catalog').append(button);
  }
  $('connection').textContent = 'Device connected. '+catalog.length+' allowed personas.';
  select(catalog.some(p=>p.id==='boli') ? 'boli' : catalog[0]?.id);
});
persona.control.onchange = () => select(persona.control.value);
backend.control.onchange = () => {
  pending = null; $('review-actions').hidden = true; $('mode').textContent = backend.control.value;
  $('notice').textContent = backend.control.value === 'fixture' ? 'Fixture data is synthetic. Demo approval never executes live effects.' : 'Live persona tools may run under your published policy. Review protected actions in the authenticated Persona app.';
};
$('inspect').onclick = () => work(async()=> { render(await api('/v1/capabilities?'+new URLSearchParams({persona:selected, backend:backend.control.value}))); $('status').textContent='Capabilities received.'; });
$('run').onclick = () => work(async()=> {
  pending = null; $('review-actions').hidden = true;
  const operationId = crypto.randomUUID();
  const result = await api('/v1/turns', {persona:selected, backend:backend.control.value, operationId, text:message.control.value});
  render(result); $('status').textContent='Complete result received. Operation '+operationId;
  if (result.mode==='fixture') { pending=result; $('review-actions').hidden=false; }
});
for (const decision of ['approve','decline']) $(decision).onclick = () => work(async()=> {
  if (!pending) return;
  render(await api('/v1/reviews',{operationId:pending.operationId, revision:pending.revision, decision}));
  pending=null; $('review-actions').hidden=true; $('status').textContent='Synthetic review recorded. No external effect executed.';
});
