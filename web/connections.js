// Shared by the viewer and importer; original exports remain unchanged.
let organization={projects:{},frames:{}};
async function saveOrganization(){
 await ArchiveIO.save(data,organization);
}
function linkedChats(a){return [...new Set(organization.frames[a.id]??a.conversations??[])];}
function projectOfChat(id){return organization.projects['chats/'+id] ?? data?.project_matches?.[id]?.project ?? '';}
function projectSelector(type,id){const value=type==='chats'?projectOfChat(id):organization.projects[type+'/'+id]||'';return `<label class="project-label">Проект <select class="select" id="assign-project"><option value="">Без проекта</option>${data.projects.map(p=>`<option value="${p.uuid}" ${value===p.uuid?'selected':''}>${esc(p.name)}</option>`).join('')}</select></label>`;}
function projectEvidence(id){
 const item=organization.project_evidence?.['chats/'+id];if(!item)return '';
 const labels={export:'экспорт',screenshot:'скриншот',copied_sidebar:'скопированная панель',user_note:'заметка пользователя',user_confirmation:'подтверждение пользователя',content_inference:'сопоставление по содержимому',manual:'ручной выбор'};
 const project=data.projects.find(p=>p.uuid===item.project)?.name||'Без проекта';
 const heading=item.status==='proposed'?'Предлагается: '+project+' · не подтверждено':'Основание назначения · '+(labels[item.source]||item.source);
 return `<div class="meta">${detail(heading,`<p>${esc(item.reference)}</p><p>${esc(item.reason)}</p>`)}</div>`;
}
function attachProjectSelector(type,id){
 if(type!=='chats')return;
 const main=$('#main');
 const block=document.createElement('div');
 block.className='chat-project-switcher';
 block.innerHTML=projectSelector(type,id)+projectEvidence(id);
 const anchor=main.querySelector('.toolbar')||main.querySelector('.meta');
 if(anchor)anchor.after(block);else main.prepend(block);
 const select=block.querySelector('select');
 select.setAttribute('aria-label',type==='chats'?'Переместить чат в проект':'Проект артефакта');
 select.onchange=async e=>{const key=type+'/'+id,previous=JSON.parse(JSON.stringify(organization));select.disabled=true;organization.projects[key]=e.target.value;organization.project_evidence||={};organization.project_evidence[key]={project:e.target.value,source:'manual',status:'confirmed',reference:'Просмотрщик архива',reason:'Пользователь выбрал назначение проекта в просмотрщике.'};try{await saveOrganization();renderList();openItem(id)}catch(error){organization=previous;select.value=projectOfChat(id);select.disabled=false;alert(error.message)}};
}
const originalOpenItem=openItem;
openItem=async function(id){const type=tab;await originalOpenItem(id);if(tab===type&&selected===id&&!$('#main .error'))attachProjectSelector(type,id);};
