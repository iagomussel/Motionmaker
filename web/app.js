const $ = s => document.querySelector(s);
const styles = {paper:'Paper',flat:'Flat',kinetic:'Kinetic',blueprint:'Blueprint',ui:'UI',editorial:'Editorial'};
for (const [value,label] of Object.entries(styles)) {
  const button=document.createElement('button');button.type='button';button.className='style';
  button.setAttribute('aria-label',label);button.setAttribute('aria-pressed',String(value==='paper'));
  const swatch=document.createElement('span');swatch.className=`swatch ${value}`;swatch.textContent=value==='kinetic'?'MOVE':'Aa';
  const title=document.createElement('span');title.textContent=label;button.append(swatch,title);
  button.onclick=()=>{ $('#style').value=value;document.querySelectorAll('.style').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));$('#poster').className=`poster ${value}`; };
  $('#styles').append(button);
}
$('#format').onchange=()=>{const horizontal=$('#format').value==='16:9';$('#ratio').textContent=$('#format').value;$('#poster').style.aspectRatio=horizontal?'16/9':'9/16';};
async function health(){
  $('#health').textContent='Verificando dependências locais…';
  try {const h=await (await fetch('/api/health')).json();$('#health').textContent=`${h.ollama?'● Ollama conectado':'○ Ollama indisponível: inicie com ollama serve'}. ${h.ffmpeg&&h.ffprobe?'FFmpeg pronto.':'Instale FFmpeg e ffprobe.'} ${h.ollama&&!h.models.length?'Baixe um modelo com ollama pull qwen2.5-coder:14b.':''}`;$('#models').replaceChildren(...h.models.map(name=>{const o=document.createElement('option');o.value=name;return o;}));}
  catch{$('#health').textContent='Não foi possível consultar o servidor local.';}
}
$('#refresh').onclick=health;
let active=false, busy=false, signature='';
async function jobs(){
  if(busy)return;busy=true;
  try {
    const response=await fetch('/api/jobs');if(!response.ok)throw Error('Não foi possível carregar as gerações.');
    const list=await response.json();active=list.some(j=>j.status==='running');$('#generate').disabled=active;$('#generate').firstChild.textContent=active?'Gerando seu vídeo… ':'Gerar meu vídeo ';
    const next=JSON.stringify(list);
    if(next!==signature){signature=next;$('#jobs').replaceChildren();
      if(!list.length){const p=document.createElement('p');p.className='muted';p.textContent='Seus vídeos aparecerão aqui.';$('#jobs').append(p);}
      for(const j of list){
        const item=document.createElement('div');item.className='job';const title=document.createElement('strong');title.textContent=j.title;
        const badge=document.createElement('span');badge.className='badge';badge.textContent=({running:'◌ Gerando',done:'✓ Concluído',failed:'! Falhou'})[j.status];item.append(title,badge);
        if(j.error){const p=document.createElement('p');p.textContent=j.error;item.append(p);}
        if(j.status==='done'){const video=document.createElement('video');video.controls=true;video.preload='metadata';video.src=`/api/jobs/${j.id}/video`;const a=document.createElement('a');a.href=video.src;a.download='motionforge.mp4';a.textContent='↓ Baixar MP4';item.append(video,a);}
        const details=document.createElement('details');details.open=j.status==='running';const summary=document.createElement('summary');summary.textContent='Registro da geração';const pre=document.createElement('pre');pre.dataset.job=j.id;details.append(summary,pre);details.ontoggle=()=>{if(details.open)updateLog(pre);};item.append(details);$('#jobs').append(item);
      }
    }
    await Promise.all([...document.querySelectorAll('.job details[open] pre')].map(updateLog));
  }catch(e){$('#error').textContent=e.message;}finally{busy=false;}
}
async function updateLog(pre){try{const r=await fetch(`/api/jobs/${pre.dataset.job}/log`);pre.textContent=r.ok?(await r.text())||'Iniciando pipeline…':'Aguardando registro…';}catch{pre.textContent='Não foi possível carregar o registro.';}}
$('#form').onsubmit=async e=>{
  e.preventDefault();if(active)return;$('#error').textContent='';$('#generate').disabled=true;
  const data=Object.fromEntries(new FormData(e.target));data.no_tts=e.target.no_tts.checked;data.no_captions=e.target.no_captions.checked;
  try{const r=await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await r.json();if(!r.ok)throw Error(result.error);await jobs();}
  catch(err){$('#error').textContent=err.message;$('#generate').disabled=false;}
};
health();jobs();setInterval(jobs,2000);
