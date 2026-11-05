'use strict';
const $ = id => document.getElementById(id);
const state = {token: '', me: null, room: null, rooms: [], epoch: 0, snapshot: '', pending: new Map()};
const statusNames = {pending:'Pendiente de revisión',approved_unexecuted:'Aprobado · sin ejecutar',rejected:'Rechazado',collecting:'Esperando aportes · sin activación automática',ready_for_synthesis:'Listo para síntesis',completed:'Resultado registrado'};
function el(tag, text, cls) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if(cls) node.className = cls; return node; }
function button(label, fn, cls='secondary') { const b=el('button',label,cls); b.type='button'; b.onclick=fn; return b; }
function toast(message) { $('toast').textContent=message; $('toast').hidden=false; clearTimeout(toast.timer); toast.timer=setTimeout(()=>$('toast').hidden=true,5000); }
function actor(id) { return state.room?.participants.find(p=>p.id===id); }
function name(id) { return actor(id)?.name || 'Participante'; }
function avatar(person) { return el('div',person?.kind==='agent'?'✦':(person?.name||'?')[0], 'avatar '+(person?.kind==='agent'?'agent':'')); }
function date(time) { return new Date(time*1000).toLocaleTimeString('es',{hour:'2-digit',minute:'2-digit'}); }
async function api(path, body) {
  const options={headers:{Authorization:'Bearer '+state.token}};
  const operation=body===undefined?null:path+JSON.stringify(body);
  if(operation) { let key=state.pending.get(operation); if(!key){ key=crypto.randomUUID(); state.pending.set(operation,key); } options.method='POST';options.headers['Content-Type']='application/json';options.headers['Idempotency-Key']=key;options.body=JSON.stringify(body); }
  let res;
  try { res=await fetch(path,options); } catch { throw new Error('No se recibió confirmación. Reintentá el mismo contenido para consultar la misma operación.'); }
  const data=await res.json();
  if(operation && (res.ok || (res.status>=400 && res.status<500 && res.status!==429))) state.pending.delete(operation);
  if(!res.ok) throw new Error(data.message || 'No se pudo completar la operación.');
  return data;
}
function empty(parent, title, text) { const box=el('div',undefined,'empty');box.append(el('div','↗','empty-symbol'),el('strong',title),el('p',text));parent.append(box); }
function modal(title, intro) { $('modal-content').replaceChildren(el('h2',title),el('p',intro,'small'));$('modal').showModal(); }
function form() {const f=el('form');const error=el('p','','form-error');error.setAttribute('role','alert');f.append(error);$('modal-content').append(f);return {f,error};}
function field(f,title,type='text',value='') {const label=el('label',title);const input=el(type==='textarea'?'textarea':'input');if(type!=='textarea') input.type=type;input.value=value;input.required=true;label.append(input);f.append(label);return input;}
function select(f,title,items) {const label=el('label',title);const input=el('select');for(const item of items){const o=el('option',item.name);o.value=item.id;input.append(o);}label.append(input);f.append(label);return input;}
function submit(f,error,label,handler) {const b=el('button',label,'primary');b.type='submit';f.append(b);f.onsubmit=async e=>{e.preventDefault();b.disabled=true;error.textContent='';try {await handler();$('modal').close();state.snapshot='';await refresh();}catch(exc){error.textContent=exc.message;}finally{b.disabled=false;}};}
function showStock() {
  const roomId=state.room.id;
  modal('Solicitar stock','Este pedido usa artículos de prueba y requiere revisión de otra persona. No modifica existencias.');
  const {f,error}=form();const sku=select(f,'Artículo',[{id:'DEMO-001',name:'DEMO-001 · Producto de ejemplo A'},{id:'DEMO-002',name:'DEMO-002 · Producto de ejemplo B'}]);
  const qty=field(f,'Cantidad','number','1');qty.min='1';qty.max='1000';qty.step='1';
  const note=field(f,'Motivo','textarea');note.maxLength=500;
  f.append(el('p','DEPOSITO-DEMO → '+state.room.site,'small'));
  submit(f,error,'Guardar solicitud',()=>api('/api/rooms/'+roomId+'/requests',{sku:sku.value,quantity:Number(qty.value),note:note.value}));
}
function decide(request,decision) {
  const roomId=state.room.id;
  modal(decision==='approve'?'Revisar y aprobar':'Rechazar solicitud','La decisión queda registrada con tu identidad. El stock real permanece sin conexión.');
  const p=request.payload;
  $('modal-content').append(el('p',`${p.quantity} × ${p.sku} · ${p.source} → ${p.destination}`),el('p',p.note,'result-text'));
  const {f,error}=form();submit(f,error,decision==='approve'?'Aprobar sin ejecutar':'Confirmar rechazo',()=>api(`/api/rooms/${roomId}/requests/${request.id}/decision`,{decision,payload_digest:request.payload_digest}));
}
function showCollaboration() {
  const roomId=state.room.id;
  const agents=state.room.participants.filter(p=>p.kind==='agent'&&p.active);
  modal('Un encargo, varios agentes','Una persona inicia una ronda. Los colaboradores aportan una vez y el coordinador reúne el resultado. La conexión y la activación de cada Muse siguen pendientes.');
  if(agents.length<2){$('modal-content').append(el('p','Esta sala necesita al menos dos cuentas de agente. Podés probar el flujo en Laboratorio · Agentes.','result-text'));return;}
  const {f,error}=form();const goal=field(f,'Trabajo a realizar','textarea');goal.maxLength=2000;
  const lead=select(f,'Cuenta coordinadora',agents);const members=el('div');f.append(el('p','Colaboradores (hasta cuatro)','small'),members);
  const build=()=>{members.replaceChildren();for(const a of agents.filter(a=>a.id!==lead.value)){const l=el('label',undefined,'check-label');const c=el('input');c.type='checkbox';c.value=a.id;c.checked=true;l.append(c,document.createTextNode(a.name));members.append(l);}};
  lead.onchange=build;build();
  submit(f,error,'Crear encargo pendiente',()=>api(`/api/rooms/${roomId}/tasks`,{goal:goal.value,lead_id:lead.value,contributors:[...members.querySelectorAll('input:checked')].map(c=>c.value)}));
}
async function showNewRoom() {
  try {
    const people=await api('/api/identities');modal('Crear una sala','Elegí las identidades que podrán leer todo el contenido de esta sala. Una cuenta pendiente no crea ni conecta un Muse.');
    const {f,error}=form();const title=field(f,'Nombre de la sala');title.maxLength=80;const site=field(f,'Local de prueba','text','SHOW-DEMO');site.maxLength=80;
    const members=el('div');f.append(members);
    for(const p of people.filter(p=>p.id!==state.me.id)){const label=el('label',undefined,'check-label');const check=el('input');check.type='checkbox';check.value=p.id;label.append(check,document.createTextNode(p.name+' · '+(p.kind==='agent'?'agente pendiente':'persona')));members.append(label);}
    f.append(el('p','Vos serás la persona aprobadora. Los demás integrantes tendrán el rol de miembro.','small'));
    submit(f,error,'Crear sala',async()=>{const result=await api('/api/rooms',{name:title.value,site:site.value,members:[...members.querySelectorAll('input:checked')].map(c=>({id:c.value,role:'member'}))});state.rooms=await api('/api/rooms');renderRooms();await selectRoom(result.id);});
  }catch(e){toast(e.message);}
}
function showTask(task) {
  modal('Detalle del encargo','Los aportes se atribuyen a la credencial de cada cuenta. Su origen en un Muse personal no está verificado.');
  $('modal-content').append(el('p',task.goal,'result-text'),el('p','Coordinación: '+name(task.lead_id),'small'));
  for(const id of task.contributors){const c=task.contributions.find(c=>c.actor_id===id);$('modal-content').append(el('h3',name(id)),el('p',c?c.text:'Aporte pendiente. No se activó este agente.',c?'result-text':'small'));}
  if(task.synthesis)$('modal-content').append(el('h3','Síntesis final'),el('p',task.synthesis,'result-text'));
}
async function showAudit() {
  try { const rows=await api('/api/rooms/'+state.room.id+'/audit');modal('Registro de esta sala','Primeros 100 eventos. Las claves nunca se incluyen. El registro completo se conserva en la base local.');
    for(const row of rows){const event=JSON.parse(row.event);const item=el('div',undefined,'audit-row');item.append(el('strong',event.action),el('p',name(event.actor)+' · '+new Date(event.at*1000).toLocaleString('es')),el('p','Referencia: '+event.target,'small'));$('modal-content').append(item);}
  }catch(e){toast(e.message);}
}
function clearWorkspace(){ for(const id of ['rooms','messages','requests','tasks','participants','message-targets'])$(id).replaceChildren(); $('room-title').textContent='Tu espacio de trabajo';$('room-subtitle').textContent='No hay salas asignadas. La persona administradora puede crear una.';for(const id of ['people-count','stock-count','message-count'])$(id).textContent='0';for(const id of ['stock-button','collaboration','message-form','audit-button','read-only-notice'])$(id).hidden=true;$('message-text').value=''; }
function renderRooms(){ $('rooms').replaceChildren();for(const r of state.rooms){const b=button('▱  '+r.name,()=>selectRoom(r.id).catch(e=>toast(e.message)),r.id===state.room?.id?'selected':'');$('rooms').append(b);} }
async function selectRoom(id){state.epoch++;state.snapshot='';state.room={id};$('message-text').value='';await refresh();renderRooms();}
async function refresh(){
  if(!state.token||!state.room)return;
  const epoch=state.epoch;const roomId=state.room.id;const room=await api('/api/rooms/'+roomId);
  if(epoch!==state.epoch||!state.token)return;
  const snapshot=JSON.stringify(room);if(snapshot===state.snapshot)return;
  state.room=room;state.snapshot=snapshot;
  $('room-title').textContent=room.name;$('room-subtitle').textContent='Pedidos y respuestas visibles para los integrantes de esta sala.';
  $('people-count').textContent=room.participants.length;$('participants').replaceChildren();
  for(const p of room.participants){const row=el('div',undefined,'participant');const detail=el('div');detail.append(el('strong',p.name),el('small',!p.active?'Acceso revocado':p.kind==='agent'?'Conexión no verificada · '+(p.agent_write?'escritura local':'solo lectura'):p.role==='approver'?'Persona · puede revisar stock':'Persona · miembro'));row.append(avatar(p),detail);$('participants').append(row);}
  const checked=new Set([...$('message-targets').querySelectorAll('input:checked')].map(c=>c.value));
  $('message-targets').replaceChildren();for(const a of room.participants.filter(a=>a.kind==='agent'&&a.active)){const l=el('label');const c=el('input');c.type='checkbox';c.value=a.id;c.checked=checked.has(a.id);l.append(c,document.createTextNode(a.name.replace(' · cuenta pendiente','')));$('message-targets').append(l);}
  const messageBox=$('messages');const atBottom=messageBox.scrollHeight-messageBox.scrollTop-messageBox.clientHeight<70;messageBox.replaceChildren();
  $('message-count').textContent=room.messages.length+(room.messages.length===1?' mensaje':' mensajes');
  if(!room.messages.length)empty(messageBox,'El próximo trabajo empieza acá','Escribí un pedido y elegí a qué cuenta de agente dirigirlo.');
  for(const msg of room.messages){const p=actor(msg.actor_id);const node=el('article',undefined,'message');const body=el('div',undefined,'message-content');const head=el('div',undefined,'message-head');head.append(el('strong',name(msg.actor_id)),el('time',date(msg.created_at)));if(p?.kind==='agent')head.append(el('span','AGENTE · ORIGEN NO VERIFICADO','tag'));body.append(head,el('p',msg.text,'message-text'));if(msg.targets.length)body.append(el('p','Dirigido a '+msg.targets.map(name).join(', ')+' · conexión pendiente','message-meta'));if(msg.reply_to)body.append(el('p','Respuesta vinculada al pedido '+msg.reply_to.slice(0,8),'message-meta'));node.append(avatar(p),body);messageBox.append(node);}
  if(atBottom)messageBox.scrollTop=messageBox.scrollHeight;
  $('requests').replaceChildren();$('stock-count').textContent=room.requests.length;
  if(!room.requests.length)$('requests').append(el('p','Todavía no hay solicitudes.','empty'));
  for(const r of room.requests){const p=r.payload;const card=el('article',undefined,'stock-card');card.append(el('h3',p.quantity+' × '+p.sku),el('p',p.source+' → '+p.destination,'small'),el('span',r.status==='pending'&&r.expires_at<Date.now()/1000?'Vencido':statusNames[r.status],'status '+r.status),el('p',name(r.actor_id)+' · '+p.note,'small'));
    if(r.status==='pending'&&r.expires_at>Date.now()/1000&&actor(r.actor_id)?.active&&room.role==='approver'&&state.me.kind==='human'&&r.actor_id!==state.me.id){const actions=el('div',undefined,'row-actions');actions.append(button('Revisar',()=>decide(r,'approve'),'primary'),button('Rechazar',()=>decide(r,'reject')));card.append(actions);}$('requests').append(card);}
  $('tasks').replaceChildren();if(!room.tasks.length)$('tasks').append(el('p','Los encargos con varios agentes aparecerán acá.','empty'));
  for(const task of room.tasks){const card=el('article',undefined,'task-card');card.append(el('h3',task.goal),el('span',task.expires_at<Date.now()/1000&&task.status!=='completed'?'Ronda vencida':statusNames[task.status],'status '+task.status),el('p',task.contributions.length+'/'+task.contributors.length+' aportes · coordina '+name(task.lead_id),'small'),button(task.synthesis?'Ver resultado':'Ver encargo',()=>showTask(task),'ghost'));$('tasks').append(card);}
  const human=state.me.kind==='human';$('message-form').hidden=!human;$('read-only-notice').hidden=human;$('audit-button').hidden=false;$('stock-button').hidden=!human;$('collaboration').hidden=!human;
}
$('login-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;$('login-error').textContent='';try{state.token=$('access-key').value.trim();state.me=await api('/api/me');state.rooms=await api('/api/rooms');clearWorkspace();$('access-key').value='';$('my-name').textContent=state.me.name;$('my-role').textContent=state.me.kind==='human'?'Cuenta personal':'Cuenta de agente';$('my-avatar').textContent=state.me.name[0];$('new-room').hidden=!state.me.admin;$('login').hidden=true;$('workspace').hidden=false;renderRooms();if(state.rooms.length)await selectRoom(state.rooms[0].id);else{$('stock-button').hidden=true;$('collaboration').hidden=true;$('message-form').hidden=true;}}catch(exc){state.token='';$('login').hidden=false;$('workspace').hidden=true;$('login-error').textContent=exc.message;}finally{b.disabled=false;}};
$('logout').onclick=()=>{state.epoch++;state.token='';state.me=null;state.room=null;state.snapshot='';state.pending.clear();$('workspace').hidden=true;$('login').hidden=false;$('modal').close();clearWorkspace();$('access-key').focus();};
$('message-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{const roomId=state.room.id;await api(`/api/rooms/${roomId}/messages`,{text:$('message-text').value,targets:[...$('message-targets').querySelectorAll('input:checked')].map(c=>c.value)});$('message-text').value='';state.snapshot='';await refresh();$('messages').scrollTop=$('messages').scrollHeight;}catch(exc){toast(exc.message);}finally{b.disabled=false;}};
$('stock-button').onclick=showStock;$('collaboration').onclick=showCollaboration;$('new-room').onclick=showNewRoom;$('audit-button').onclick=showAudit;
setInterval(()=>{if(state.token&&!$('modal').open)refresh().catch(e=>toast(e.message));},5000);
