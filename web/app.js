const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=s=>s?new Date(s).toLocaleString('ru-RU',{dateStyle:'medium',timeStyle:'short'}):'';
const title=a=>a.versions?.find(v=>v.id===a.active_version)?.title||a.versions?.[0]?.title||a.name||'Без названия';
let data,tab='chats',selected='',request=0;
// Export text is always escaped before formatting; HTML from chats is never executed.
function md(text){let blocks=[];let s=esc(text).replace(/```([^\n]*)\n([\s\S]*?)```/g,(_,lang,code)=>{blocks.push(`<pre><small>${lang}</small><code>${code}</code></pre>`);return `\n\n@@BLOCK${blocks.length-1}@@\n\n`});s=s.replace(/^#{1,6} (.+)$/gm,'<h3>$1</h3>').replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>').replace(/`([^`\n]+)`/g,'<code>$1</code>').replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noreferrer">$1</a>');return s.split(/\n\s*\n/).map(p=>/^@@BLOCK\d+@@$/.test(p.trim())?blocks[Number(p.trim().match(/\d+/)[0])]:`<p>${p.replace(/\n/g,'<br>')}</p>`).join('')}
function download(name,text,type='text/plain'){const u=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
function items(){return data.conversations}
function detail(label,content){return `<details><summary>${esc(label)}</summary>${content}</details>`}
function message(m){const content=m.content||[],texts=content.filter(c=>c.type==='text').map(c=>c.text).join('\n\n')||m.text||'';let extra='';for(const c of content){if(c.type==='thinking')extra+=detail('Размышления',`<div class="prose">${md(c.thinking||c.text||'')}</div>`);else if(['tool_use','tool_result'].includes(c.type))extra+=detail(c.type==='tool_use'?'Инструмент · '+(c.name||''):'Результат инструмента',`<pre>${esc(JSON.stringify(c,null,2))}</pre>`);else if(!['text','thinking','injected_prompt_block'].includes(c.type))extra+=detail(c.type==='image'?'Изображение · данные экспорта':c.type==='document'?'Документ · данные экспорта':'Блок · '+c.type,`<pre>${esc(JSON.stringify(c,null,2))}</pre>`)}for(const a of m.attachments||[])extra+=detail('Вложение · '+(a.file_name||a.file_type||'без названия'),`<div class="prose">${md(a.extracted_content||'Содержимое файла отсутствует в экспорте.')}</div>`);const injected=content.filter(c=>c.type==='injected_prompt_block');if(injected.length)extra+=detail('Служебный контекст · '+injected.length,`<pre>${esc(injected.map(c=>c.prompt||JSON.stringify(c)).join('\n\n'))}</pre>`);return `<article class="message ${m.sender==='human'?'human':''}"><div class="role">${m.sender==='human'?'Вы':'Claude'} <span class="meta">· ${esc(date(m.created_at))}</span></div><div class="prose">${md(texts)}</div>${extra}</article>`}
async function openItem(id){const token=++request;selected=id;location.hash=tab+'/'+id;renderList();const main=$('#main');main.innerHTML='<div class="empty">Загрузка…</div>';try{if(tab==='chats'){const c=await ArchiveIO.conversation(id);if(token!==request)return;main.innerHTML=`<div class="eyebrow">Диалог</div><h1>${esc(c.name||'Без названия')}</h1><div class="meta">${esc(date(c.created_at))} · ${c.chat_messages.length} сообщений</div><div class="toolbar"><button class="btn" data-variant="outline" data-size="sm" id="download">Скачать Markdown ↓</button></div>${c.chat_messages.map(message).join('')}`;$('#download').onclick=()=>download((c.name||'Диалог').replace(/[\\/:*?"<>|]/g,'_')+'.md','# '+c.name+'\n\n'+c.chat_messages.map(m=>'## '+(m.sender==='human'?'Вы':'Claude')+'\n\n'+(m.text||m.content?.filter(c=>c.type==='text').map(c=>c.text).join('\n\n')||'')).join('\n\n'));}}catch(e){if(token===request)main.innerHTML=`<div class="error">${esc(e.message)}</div>`}}
function showHome(){
 const r=data.report,c=r.counts;
 $('#main').innerHTML=`<div class="empty"><b>Локальный архив Claude</b><p>${c.conversations} диалогов · ${c.projects} проектов · ${c.artifacts} артефактов</p><p>Без проекта: ${r.unassigned_conversations.length}. Недоступных версий: ${r.missing_artifact_versions.length}.</p><p>Выберите диалог слева. ${ArchiveIO.isDemo?'Это вымышленные данные. Назначения сохраняются только в вашем браузере.':'Назначения проектов сохраняются в organization.json рядом с данными.'}</p><p><a href="${ArchiveIO.reportURL(data)}" target="_blank" rel="noopener">Открыть отчёт проверки ↗</a></p>${c.conversations?'':'<p>Экспорт не содержит диалогов. Проверьте состав ZIP.</p>'}</div>`;
}
function route(){
 const [t,id]=location.hash.slice(1).split('/');
 if(t==='chats'&&id){tab=t;selected=id;renderList();openItem(id);return;}
 ++request;tab='chats';selected='';
 if(location.hash)history.replaceState(null,'',location.pathname+location.search);
 renderList();showHome();
}
async function init(){try{
 data=await ArchiveIO.index();
 if(ArchiveIO.isDemo){$('.local').textContent='● Демо · вымышленные данные';if(!location.hash)history.replaceState(null,'',location.pathname+location.search+'#chats/'+data.conversations[0].uuid);}
 organization=data.organization;
 route();$('#search').oninput=renderList;
 window.addEventListener('hashchange',()=>{const [t,id]=location.hash.slice(1).split('/');if(t!==tab||id!==selected)route()});
}catch(e){$('#main').textContent=e.message}}
