#!/usr/bin/env python3
"""disk-root-cause-clean 两段式报告生成器。

用法:
  make_report.py scan    findings.json > 体检报告.html   # 时机一:扫描完成后
  make_report.py cleaned result.json   > 清理战报.html   # 时机二:清理验证后

JSON 结构见 SKILL.md「两段式报告」一节。输出单文件 HTML(ECharts CDN),双主题。
"""
import json, sys, html

def esc(s): return html.escape(str(s), quote=False)

def tier_color(t):
    return {'safe': '__C_S1__', 'confirm': '__C_S2__'}.get(t, '__C_BASE__')

def build(mode, d):
    disk = d.get('disk', {})
    tl = d.get('timeline') or []
    findings = d.get('findings', [])
    actions = d.get('actions') or []
    potential = d.get('potential') or []
    dist = d.get('distribution') or []
    machine, date = esc(d.get('machine','')), esc(d.get('date',''))

    if mode == 'scan':
        tiers = {}
        for f in findings: tiers[f.get('tier','confirm')] = tiers.get(f.get('tier','confirm'),0)+f.get('gb',0)
        kpis = [
          dict(cls='hero', label='当前可用空间', value=f"{disk.get('avail_gib','?')}", unit='GiB',
               delta=f"使用率 {disk.get('used_pct','?')}% · 共 {disk.get('total_gib','?')} GB"),
          dict(label='预计可回收 · 安全层', value=f"~{tiers.get('safe',0):.0f}", unit='GB', delta='零数据损失,可直接清'),
          dict(label='预计可回收 · 待确认', value=f"~{tiers.get('confirm',0):.0f}", unit='GB', delta=f"涉个人数据,需逐项确认"),
          dict(label='已排除 / 暂不动', value=f"~{tiers.get('excluded',0):.0f}", unit='GB', delta='按用户指示保留')]
        title, sub = '磁盘体检报告', f'{machine} · {date} · 对账式根因扫描 · 等待清理指令'
    else:
        kpis = [
          dict(cls='hero', label='本次释放可用空间', value=f"+{d.get('freed_gib','?')}", unit='GiB',
               delta=f"{disk.get('avail_gib_start','?')} → {disk.get('avail_gib','?')} GiB · 使用率 {disk.get('used_pct_start','?')}% → {disk.get('used_pct','?')}%"),
          dict(label='主动清理', value=f"~{d.get('cleaned_gb','?')}", unit='GB', delta=f"{len(actions)} 项 · 零数据损失"),
          dict(label='根因类别', value=f"{len(findings)}", unit='类', delta='按根因分类清理'),
          dict(label='剩余可清潜力', value=f"~{sum(p.get('gb',0) for p in potential):.0f}", unit='GB', delta='未动项,见下表')]
        title, sub = '磁盘清理战报', f'{machine} · {date} · 前后对比 · 口径见注脚'

    kpi_html = ''.join(
        f'<div class="tile {k.get("cls","")}"><div class="label">{k["label"]}</div>'
        f'<div class="value">{k["value"]}<small>{k["unit"]}</small></div>'
        f'<div class="delta">{k["delta"]}</div></div>' for k in kpis)

    fdata = [dict(name=esc(f['category']), value=f['gb'], tier=f.get('tier','confirm')) for f in findings]
    adata = [[esc(a['name']), a['before_gb'], a.get('after_gb',0)] for a in actions]
    pdata = [[esc(p['name']), p['gb']] for p in potential]

    data_js = json.dumps(dict(mode=mode, kpis=len(kpis), findings=fdata, actions=adata,
        timeline=tl, potential=pdata, distribution=dist), ensure_ascii=False)

    charts_js = f"""
const DATA = __DATA__;
const css = getComputedStyle(document.body);
const C = k => css.getPropertyValue(k).trim();
const P = {{ s1:C('--s1'), deep:C('--s1-deep'), wash:C('--s1-wash'), s2:C('--s2'),
  t1:C('--text-1'), t2:C('--text-2'), muted:C('--muted'), grid:C('--grid'), base:C('--baseline'), surf:C('--surface-1') }};
const baseText = {{ color:P.t2, fontSize:12 }};
const tooltip = {{ trigger:'item', backgroundColor:P.surf, borderColor:P.grid,
  textStyle:{{ color:P.t1, fontSize:12 }}, extraCssText:'box-shadow:none;' }};
function mk(id, opt){{ const c=echarts.init(document.getElementById(id)); c.setOption(opt); return c; }}
const charts=[]; window.addEventListener('resize',()=>charts.forEach(c=>c.resize()));
const TIERC = {{ safe:P.s1, confirm:P.s2, excluded:P.base }};
const TIER_LABEL = {{ safe:'安全层 · 可直接清', confirm:'待确认 · 需逐项勾选', excluded:'已排除 · 保留' }};

/* 发现构成 treemap(两模式共用;scan 按 tier 着色, cleaned 按 blue 阶梯) */
const blues=['#0d366b','#104281','#184f95','#1c5cab','#256abf','#2a78d6','#3987e5','#5598e7','#6da7ec'];
const fs=DATA.findings; const tot=fs.reduce((a,f)=>a+f.value,0)||1;
charts.push(mk('compose',{{ tooltip:{{...tooltip, formatter:p=>`${{p.name}}<br/><b>${{p.value}} GB</b> · 占 ${{(p.value/tot*100).toFixed(0)}}%`}},
  series:[{{ type:'treemap', data: fs.map((f,i)=>({{ name:f.name, value:f.value,
      itemStyle:{{ color: DATA.mode==='scan' ? TIERC[f.tier] : blues[Math.min(i,8)],
        borderColor:P.surf, borderWidth:2, borderRadius:4, gapWidth:2 }},
      label:{{ show:true, formatter:'{{b}}\\n{{c}} GB', fontSize:12,
        color: DATA.mode==='scan' ? (f.tier==='excluded' ? P.t2 : '#ffffff') : (i<6?'#ffffff':'#0b0b0b'), lineHeight:17 }} }})),
    left:0, right:0, top:6, bottom:6, leafDepth:1, roam:false, nodeClick:false, breadcrumb:{{show:false}} }}] }}));

/* cleaned: 时间线 + dumbbell + 箱型 + 剩余潜力; scan: 大户排行 + 剩余潜力 */
if (DATA.mode==='cleaned' && DATA.timeline.length>1){{
  charts.push(mk('timeline',{{ tooltip:{{...tooltip, trigger:'axis', formatter:ps=>`${{ps[0].name}}<br/>可用 <b>${{ps[0].value}} GiB</b>`}},
    grid:{{left:44,right:70,top:24,bottom:30}},
    xAxis:{{type:'category', data:DATA.timeline.map(t=>t[0]), axisLine:{{lineStyle:{{color:P.base}}}}, axisTick:{{show:false}}, axisLabel:{{...baseText}}}},
    yAxis:{{type:'value', name:'GiB', nameTextStyle:{{color:P.muted}}, splitLine:{{lineStyle:{{color:P.grid,width:1}}}}, axisLabel:{{...baseText}}}},
    series:[{{type:'line', step:'middle', data:DATA.timeline.map(t=>t[1]), symbol:'circle', symbolSize:9,
      itemStyle:{{color:P.s1, borderColor:P.surf, borderWidth:2}}, lineStyle:{{color:P.s1,width:2,cap:'round',join:'round'}},
      areaStyle:{{color:P.s1, opacity:0.10}},
      label:{{show:true, position:'top', color:P.t2, fontSize:12,
        formatter:p=>(p.dataIndex===0||p.dataIndex===DATA.timeline.length-1)?p.value+' GiB':''}}}}]}}));
  const items=DATA.actions;
  charts.push(mk('dumbbell',{{ tooltip:{{...tooltip, formatter:p=>{{ const it=items[p.dataIndex];
      return `${{it[0]}}<br/>清理前 ${{it[1]}} GB → 现状 ${{it[2]}} GB<br/>释放 <b>${{(it[1]-it[2]).toFixed(1)}} GB</b>`; }} }},
    grid:{{left:200,right:56,top:34,bottom:26}},
    legend:{{data:['清理前','现状'], textStyle:{{color:P.t2,fontSize:12}}, top:0, itemWidth:10, itemHeight:10}},
    xAxis:{{type:'value', name:'GB', nameTextStyle:{{color:P.muted}}, axisLabel:{{...baseText}}, splitLine:{{lineStyle:{{color:P.grid,width:1}}}}}},
    yAxis:{{type:'category', inverse:true, data:items.map(i=>i[0]), axisLine:{{show:false}}, axisTick:{{show:false}}, axisLabel:{{color:P.t2,fontSize:12}}}},
    series:[{{ name:'清理前', type:'custom', renderItem:(params,api)=>{{ const it=items[params.dataIndex], y=params.dataIndex;
      const b=api.coord([it[1],y]), a=api.coord([it[2],y]);
      return {{type:'group', children:[
        {{type:'line', shape:{{x1:b[0],y1:b[1],x2:a[0],y2:a[1]}}, style:{{stroke:P.wash,width:4,cap:'round'}}}},
        {{type:'circle', shape:{{cx:b[0],cy:b[1],r:5}}, style:{{fill:P.wash, stroke:P.surf, lineWidth:2}}}},
        {{type:'circle', shape:{{cx:a[0],cy:a[1],r:5}}, style:{{fill:P.deep, stroke:P.surf, lineWidth:2}}}}]}};}},
      data:items.map((it,idx)=>[it[1],it[2],idx]), encode:{{x:[0,1],y:2}}, z:10}}]}}));
}}
if (DATA.mode==='scan'){{
  const ranked=[...fs].sort((a,b)=>b.value-a.value).slice(0,12);
  charts.push(mk('dumbbell',{{ tooltip:{{...tooltip, formatter:p=>`${{p.name}}<br/><b>${{p.value}} GB</b> · ${{p.data.tierText}}`}},
    grid:{{left:230,right:56,top:8,bottom:26}},
    xAxis:{{type:'value', axisLabel:{{...baseText}}, splitLine:{{lineStyle:{{color:P.grid,width:1}}}}}},
    yAxis:{{type:'category', inverse:true, data:ranked.map(f=>f.name), axisLine:{{show:false}}, axisTick:{{show:false}}, axisLabel:{{color:P.t2,fontSize:12}}}},
    series:[{{type:'bar', data:ranked.map(f=>({{value:f.value, itemStyle:{{color:TIERC[f.tier], borderRadius:[0,4,4,0]}}, tier:f.tier, tierText:TIER_LABEL[f.tier]||''}})),
      barWidth:16, label:{{show:true, position:'right', color:P.t2, fontSize:12, formatter:'{{c}} GB'}}}}]}}));
}}
if (DATA.distribution.length){{
  const s=[...DATA.distribution].sort((a,b)=>a-b);
  const q=(arr,p)=>{{ const i=(arr.length-1)*p, lo=Math.floor(i), hi=Math.ceil(i); return arr[lo]+(arr[hi]-arr[lo])*(i-lo); }};
  const box=[Math.min(...s), q(s,.25), q(s,.5), q(s,.75), Math.max(...s)];
  charts.push(mk('boxplot',{{ tooltip:{{...tooltip, formatter:()=>`最小 ${{box[0].toFixed(1)}} · Q1 ${{box[1].toFixed(1)}} · 中位 ${{box[2].toFixed(1)}}<br/>Q3 ${{box[3].toFixed(1)}} · 最大 ${{box[4].toFixed(1)}} MiB · n=${{s.length}}`}},
    grid:{{left:60,right:30,top:30,bottom:36}},
    xAxis:{{type:'category', data:['node_modules 尺寸分布'], axisLine:{{lineStyle:{{color:P.base}}}}, axisTick:{{show:false}}, axisLabel:{{...baseText}}}},
    yAxis:{{type:'log', logBase:10, axisLabel:{{...baseText, formatter:v=>v>=1024?(v/1024).toFixed(1)+'G':v+'M'}}, splitLine:{{lineStyle:{{color:P.grid,width:1}}}}}},
    series:[{{type:'boxplot', data:[box], itemStyle:{{color:P.s1, borderColor:P.deep, borderWidth:2}}, boxWidth:[14,40]}},
      {{type:'scatter', symbolSize:6, itemStyle:{{color:P.s2, opacity:.55, borderColor:P.surf, borderWidth:1}},
        data:s.map((v,i)=>[0.5+(Math.sin(i*12.9898)*43758.5453%1-0.5)*0.55, v])}}]}}));
}}
if (DATA.potential.length){{
  charts.push(mk('potential',{{ tooltip:{{...tooltip, formatter:p=>`${{p.name}}<br/><b>${{p.value}} GB</b>`}},
    grid:{{left:250,right:56,top:8,bottom:26}},
    xAxis:{{type:'value', axisLabel:{{...baseText}}, splitLine:{{lineStyle:{{color:P.grid,width:1}}}}}},
    yAxis:{{type:'category', inverse:true, data:DATA.potential.map(p=>p[0]), axisLine:{{show:false}}, axisTick:{{show:false}}, axisLabel:{{color:P.t2,fontSize:12}}}},
    series:[{{type:'bar', data:DATA.potential.map(p=>p[1]), barWidth:16, itemStyle:{{color:P.wash, borderRadius:[0,4,4,0]}},
      label:{{show:true, position:'right', color:P.t2, fontSize:12, formatter:'{{c}} GB'}}}}]}}));
}}
"""

    scan_only = mode == 'scan'
    tmpl = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root { color-scheme: light; }
.viz-root { --surface-1:#fcfcfb; --page:#f9f9f7; --text-1:#0b0b0b; --text-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --baseline:#c3c2b7; --ring:rgba(11,11,11,0.10);
  --s1:#2a78d6; --s1-deep:#1c5cab; --s1-wash:#86b6ef; --s2:#eb6834; }
@media (prefers-color-scheme: dark) { .viz-root { color-scheme: dark;
  --surface-1:#1a1a19; --page:#0d0d0d; --text-1:#f0efec; --text-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --baseline:#383835; --ring:rgba(255,255,255,0.10);
  --s1:#3987e5; --s1-deep:#6da7ec; --s1-wash:#1c5cab; --s2:#d95926; } }
* { margin:0; padding:0; box-sizing:border-box; }
body.viz-root { background:var(--page); color:var(--text-1);
  font-family:system-ui,-apple-system,"Segoe UI","PingFang SC",sans-serif;
  padding:32px clamp(16px,4vw,56px) 48px; max-width:1200px; margin:0 auto; }
h1 { font-size:26px; font-weight:700; letter-spacing:-0.01em; }
.sub { color:var(--text-2); font-size:14px; margin:6px 0 28px; }
.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin-bottom:26px; }
.tile { background:var(--surface-1); border:1px solid var(--ring); border-radius:10px; padding:18px 20px 16px; }
.tile .label { font-size:13px; color:var(--text-2); }
.tile .value { font-size:34px; font-weight:600; margin-top:6px; line-height:1.1; }
.tile .value small { font-size:17px; font-weight:500; color:var(--text-2); margin-left:2px; }
.tile .delta { font-size:13px; margin-top:6px; color:var(--text-2); }
.tile.hero .value { font-size:44px; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
@media (max-width:860px){ .grid2 { grid-template-columns:1fr; } }
.card { background:var(--surface-1); border:1px solid var(--ring); border-radius:10px; padding:18px 20px 12px; margin-bottom:14px; }
.card h2 { font-size:15px; font-weight:650; }
.card .note { font-size:12px; color:var(--muted); margin-top:2px; }
.chart { width:100%; height:340px; } .chart.tall { height:420px; }
.banner { background:var(--surface-1); border:1px solid var(--ring); border-left:3px solid var(--s1);
  border-radius:8px; padding:12px 16px; font-size:14px; color:var(--text-2); margin-bottom:26px; }
footer { color:var(--muted); font-size:12px; line-height:1.7; margin-top:10px; border-top:1px solid var(--grid); padding-top:14px; }
</style></head><body class="viz-root">
<header><h1>__TITLE__</h1><div class="sub">__SUB__</div></header>
__KPIS__
__BANNER__
<div class="card"><h2>__FINDTITLE__</h2>
  <div class="note">__FINDNOTE__</div><div id="compose" class="chart tall"></div></div>
<div class="grid2">
__LEFT__
__RIGHT__
</div>
<footer><b>口径</b>：GB 为 du 十进制口径，GiB 为 df 二进制口径，相差约 7% 属正常。
<b>分层</b>：安全层=零数据损失；待确认=涉个人数据需逐项勾选；排除=按用户指示保留。</footer>
<script>
__CHARTS__
</script></body></html>"""

    find_title = '发现的可清理项 · 按根因类别' if scan_only else '本次清理构成 · 按根因类别'
    find_note = ('蓝色=安全层可直接清 · 橙色=待你确认 · 灰色=已排除 · 面积=GB'
                 if scan_only else 'du 口径 · 含逐项确认层 · 面积=GB')
    banner = ('<div class="banner">扫描完成 —— 安全层可立即清理，待确认层等你逐项指定。'
              '回复编号或「按建议执行」即开始清理。</div>') if scan_only else ''
    left = ('<div class="card"><h2>大户排行 · 前十二</h2><div class="note">颜色=分层（蓝安全/橙待确认/灰排除）</div>'
            '<div id="dumbbell" class="chart tall"></div></div>') if scan_only else \
           ('<div class="card"><h2>可用空间时间线</h2><div class="note">df 实测 · 陡升台阶即清理动作</div>'
            '<div id="timeline" class="chart"></div></div>')
    right = ('<div class="card"><h2>剩余可清潜力</h2><div class="note">未动项 · 单位 GB</div>'
             '<div id="potential" class="chart tall"></div></div>') if scan_only else \
            ('<div class="card"><h2>清理前后 · 分项对比</h2><div class="note">浅点=清理前 · 深点=现状 · 线长=释放量</div>'
             '<div id="dumbbell" class="chart tall"></div></div>')
    if dist:
        right += ('<div class="card"><h2>node_modules 森林 · 尺寸分布</h2>'
                  '<div class="note">对数轴 · 长尾分布</div><div id="boxplot" class="chart"></div></div>')
    if not scan_only:
        right += ('<div class="card"><h2>剩余可清潜力</h2><div class="note">未动项 · 等你后续决策 · 单位 GB</div>'
                  '<div id="potential" class="chart"></div></div>')

    out = (tmpl.replace('__TITLE__', esc(title)).replace('__SUB__', sub)
               .replace('__KPIS__', kpi_html).replace('__BANNER__', banner)
               .replace('__FINDTITLE__', find_title).replace('__FINDNOTE__', find_note)
               .replace('__LEFT__', left).replace('__RIGHT__', right)
               .replace('__CHARTS__', charts_js).replace('__DATA__', data_js))
    return out

if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('scan', 'cleaned'):
        sys.exit(__doc__)
    with open(sys.argv[2], encoding='utf-8') as f:
        print(build(sys.argv[1], json.load(f)))
