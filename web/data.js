// One viewer, with a local API or an explicitly generated fictional static demo.
const ArchiveIO=(()=>{
 const demo=window.CLAUDE_ARCHIVE_DEMO;
 const key='claude-archive-fictional-demo-v1:'+location.pathname;
 const json=async(url,options)=>{const r=await fetch(url,options);const value=await r.json();if(!r.ok)throw Error(value.error||'Не удалось прочитать архив');return value;};
 function checkedOrganization(value){
  const chats=new Set(demo.index.conversations.map(c=>'chats/'+c.uuid)),projects=new Set(['',...demo.index.projects.map(p=>p.uuid)]),frames=new Set(demo.index.frames.map(f=>f.id));
  if(!value||typeof value!=='object'||Array.isArray(value)||!value.projects||!value.frames)throw Error('Invalid demo organization');
  for(const [chat,project] of Object.entries(value.projects))if(!chats.has(chat)||!projects.has(project))throw Error('Invalid demo project');
  for(const [frame,ids] of Object.entries(value.frames))if(!frames.has(frame)||!Array.isArray(ids)||ids.some(id=>!chats.has('chats/'+id)))throw Error('Invalid demo artifact');
  const result={projects:value.projects,frames:value.frames};
  if(value.project_evidence!==undefined){
   const evidence=value.project_evidence,sources=new Set(['export','screenshot','copied_sidebar','user_note','user_confirmation','content_inference','manual']);
   if(!evidence||typeof evidence!=='object'||Array.isArray(evidence))throw Error('Invalid project evidence');
   for(const [chat,item] of Object.entries(evidence)){
    if(!chats.has(chat)||!item||!projects.has(item.project)||!sources.has(item.source)||!['confirmed','proposed'].includes(item.status))throw Error('Invalid project evidence');
    for(const field of ['reference','reason'])if(typeof item[field]!=='string'||!item[field].trim()||item[field].length>4000)throw Error('Invalid project evidence reference');
    if(item.status==='confirmed'&&value.projects[chat]!==item.project)throw Error('Evidence does not match assignment');
    if(item.status==='proposed'&&value.projects[chat]===item.project)throw Error('Proposed assignment is already active');
   }
   result.project_evidence=evidence;
  }
  return result;
 }
 function currentReport(data,org){
  const report=JSON.parse(JSON.stringify(data.report));
  const project=c=>org.projects['chats/'+c.uuid]??data.project_matches[c.uuid]?.project??'';
  report.unassigned_conversations=data.conversations.filter(c=>!project(c)).map(c=>c.uuid);
  report.projects=report.projects.map(p=>({...p,conversations:data.conversations.filter(c=>project(c)===p.id).length}));
  report.project_evidence=org.project_evidence||{};
  return report;
 }
 return {
  isDemo:!!demo,
  async index(){
   if(!demo)return json('/api/index');
   const value=JSON.parse(JSON.stringify(demo.index));
   try{const stored=localStorage.getItem(key);if(stored){
    const saved=checkedOrganization(JSON.parse(stored)),base=value.organization;
    value.organization={projects:{...base.projects,...saved.projects},frames:{...base.frames,...saved.frames},project_evidence:{...base.project_evidence,...saved.project_evidence}};
    for(const [chat,item] of Object.entries(value.organization.project_evidence))if(item.status==='confirmed'&&value.organization.projects[chat]!==item.project)delete value.organization.project_evidence[chat];
   }}catch{ /* A blocked store still permits read-only browsing. */ }
   value.report=currentReport(value,value.organization);return value;
  },
  async conversation(id){
   if(!demo)return json('/api/conversation/'+encodeURIComponent(id));
   const chat=demo.conversations.find(c=>c.uuid===id);if(!chat)throw Error('Диалог не найден');return chat;
  },
  async save(data,org){
   if(demo){localStorage.setItem(key,JSON.stringify(checkedOrganization(org)));data.report=currentReport(data,org);return;}
   const result=await json('/api/organization',{method:'PUT',headers:{'Content-Type':'application/json','X-Archive-Token':data.write_token},body:JSON.stringify({organization:org,revision:data.organization_revision})});
   data.organization_revision=result.revision;data.report=currentReport(data,org);
  },
  artifactURL(path){return demo?new URL('assets/'+path.split('/').map(encodeURIComponent).join('/'),document.baseURI).href:'/export/'+path;},
  async artifactText(path){const r=await fetch(this.artifactURL(path));if(!r.ok)throw Error('Файл артефакта не найден');return r.text();},
  reportURL(data){return demo?URL.createObjectURL(new Blob([JSON.stringify(data.report,null,2)],{type:'application/json'})):'/api/report';}
 };
})();
