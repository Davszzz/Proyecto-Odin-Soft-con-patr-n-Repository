/* Apache ECharts: datos de Flask, sin interpolar código dentro de JavaScript. */
(function () {
  'use strict';
  const form = document.getElementById('reportFilters');
  const select = document.getElementById('reportCode');
  if (!form || !select) return;
  const snapshotIds = JSON.parse(document.getElementById('snapshotPayload').textContent);
  function updateFilters() {
    const snapshot = snapshotIds.includes(select.value);
    for (const key of ['desde','hasta','agrupar']) document.getElementById(key).disabled = snapshot;
    document.getElementById('filterHelp').textContent = snapshot ? 'Fotografía actual: no requiere fechas.' : 'Deja las fechas vacías para consultar el historial disponible. La agrupación se usa en reportes temporales.';
    if (select.value) form.action = form.dataset.base + encodeURIComponent(select.value);
  }
  select.addEventListener('change', updateFilters);
  form.addEventListener('submit', function (e) {if (!select.value) {e.preventDefault();return;} updateFilters();});
  updateFilters();
  const payload = document.getElementById('reportPayload');
  if (!payload) return;
  const data = JSON.parse(payload.textContent), chart = data.chart;
  const target = document.getElementById('reportChart');
  if (!chart.labels.length || !chart.values.some(v => v !== 0)) {
    target.style.height='130px';target.textContent='No hay valores distintos de cero para graficar. Consulta la tabla.';target.classList.add('d-flex','align-items-center','justify-content-center','text-muted');
  } else if (!window.echarts) {
    target.style.height='130px';target.textContent='No se pudo cargar Apache ECharts. La tabla y la descarga siguen disponibles.';
  } else {
    const instance = echarts.init(target, null, {renderer:'canvas'});
    const colors=['#1268F3','#1D9C87','#5671A4','#E59B37','#8298B2','#7C64B4','#0B416A'];
    const common={color:colors,tooltip:{trigger:chart.type==='pie'?'item':'axis',confine:true,renderMode:'richText'},aria:{enabled:true},animation:false};
    if (chart.type==='pie') {
      instance.setOption({...common,legend:{bottom:0,type:'scroll'},series:[{type:'pie',radius:['38%','68%'],center:['50%','45%'],data:chart.labels.map((name,i)=>({name,value:chart.values[i]})),label:{show:false}}]});
    } else if (chart.type==='line') {
      instance.setOption({...common,grid:{left:65,right:25,top:35,bottom:70,containLabel:true},xAxis:{type:'category',data:chart.labels,axisLabel:{rotate:35}},yAxis:{type:'value',name:chart.metric},dataZoom:chart.labels.length>12?[{type:'slider',bottom:6,start:0,end:100}]:[],series:[{type:'line',data:chart.values,symbolSize:7,areaStyle:{opacity:.08}}]});
    } else {
      // Horizontal bars preserve long catalogue labels. Increase chart height for 15 categories.
      target.style.height=Math.max(300,Math.min(640,chart.labels.length*30+90))+'px';instance.resize();
      instance.setOption({...common,grid:{left:15,right:45,top:25,bottom:20,containLabel:true},xAxis:{type:'value',name:chart.metric,nameLocation:'middle',nameGap:26},yAxis:{type:'category',inverse:true,data:chart.labels,axisLabel:{width:190,overflow:'truncate'}},series:[{type:'bar',data:chart.values,barMaxWidth:24,itemStyle:{borderRadius:[0,4,4,0]}}]});
    }
    if (window.ResizeObserver) new ResizeObserver(()=>instance.resize()).observe(target);else window.addEventListener('resize',()=>instance.resize());
    document.getElementById('chartNote').textContent=chart.type==='line'?'Serie del período consultado.':'El gráfico muestra hasta 15 categorías. La tabla y el Excel conservan el resultado completo.';
  }
  const body=document.getElementById('reportRows'), info=document.getElementById('pageInfo');
  const prev=document.getElementById('prevPage'), next=document.getElementById('nextPage'), search=document.getElementById('tableSearch');
  let page=0, filtered=data.rows;const perPage=50;
  function render() {
    const start=page*perPage;body.replaceChildren();
    for (const row of filtered.slice(start,start+perPage)) {
      const tr=document.createElement('tr');for (const cell of row) {const td=document.createElement('td');td.textContent=String(cell??'Sin dato');tr.appendChild(td);}body.appendChild(tr);
    }
    if (!filtered.length) {const tr=document.createElement('tr');const td=document.createElement('td');td.colSpan=data.columns.length;td.className='text-center text-muted py-4';td.textContent='Sin registros.';tr.appendChild(td);body.appendChild(tr);}
    info.textContent=filtered.length?`${start+1}–${Math.min(start+perPage,filtered.length)} de ${filtered.length} filas`:'0 filas';prev.disabled=page===0;next.disabled=start+perPage>=filtered.length;
  }
  search.addEventListener('input',()=>{const q=search.value.toLocaleLowerCase();filtered=data.rows.filter(r=>r.some(c=>String(c).toLocaleLowerCase().includes(q)));page=0;render();});
  prev.addEventListener('click',()=>{if(page>0){page--;render();}});next.addEventListener('click',()=>{if((page+1)*perPage<filtered.length){page++;render();}});render();
})();
