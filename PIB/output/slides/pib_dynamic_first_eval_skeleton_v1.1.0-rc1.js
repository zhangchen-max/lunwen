const pptxgen = require('pptxgenjs');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'Codex';
pptx.company = 'PIB Benchmark';
pptx.subject = 'PIB dynamic-first evaluation skeleton';
pptx.title = 'PIB Dynamic-First Evaluation Skeleton';
pptx.lang = 'en-US';
pptx.theme = { headFontFace: 'Aptos Display', bodyFontFace: 'Aptos', lang: 'en-US' };

function addTitle(slide, title, subtitle) {
  slide.addText(title, { x: 0.5, y: 0.3, w: 12.3, h: 0.5, fontSize: 24, bold: true, color: '1F2937' });
  if (subtitle) slide.addText(subtitle, { x: 0.5, y: 0.85, w: 12.3, h: 0.35, fontSize: 11, color: '4B5563' });
}
function addBullets(slide, items, x=0.8, y=1.4, w=11.3, h=4.8, fs=18) {
  const runs=[]; for (const item of items) runs.push({ text: item, options: { bullet: { indent: 14 } } });
  slide.addText(runs, { x, y, w, h, fontSize: fs, color: '111827', breakLine: true, valign: 'top' });
}
function addTable(slide, headers, rows, x, y, widths) {
  let cx = x;
  headers.forEach((h,i)=>{
    slide.addShape(pptx.ShapeType.rect,{x:cx,y,w:widths[i],h:0.4,fill:{color:'1F2937'},line:{color:'1F2937'}});
    slide.addText(h,{x:cx+0.05,y:y+0.06,w:widths[i]-0.1,h:0.25,fontSize:10,bold:true,color:'FFFFFF'});
    cx += widths[i];
  });
  let ry = y + 0.42;
  rows.forEach((row, idx) => {
    let rx = x;
    row.forEach((cell, i) => {
      slide.addShape(pptx.ShapeType.rect,{x:rx,y:ry,w:widths[i],h:0.36,fill:{color:idx%2===0?'F9FAFB':'FFFFFF'},line:{color:'D1D5DB',width:1}});
      slide.addText(String(cell),{x:rx+0.05,y:ry+0.05,w:widths[i]-0.1,h:0.24,fontSize:9,color:'111827'});
      rx += widths[i];
    });
    ry += 0.36;
  });
}

{
  const s = pptx.addSlide();
  addTitle(s, 'PIB Dynamic-First Evaluation Skeleton', 'Frozen release: v1.1.0-rc1 | Split: test | Primary task: dynamic');
  addBullets(s, [
    'This deck is the current evaluation skeleton under no-external-provider conditions.',
    'The benchmark and product shell are runnable; external provider access is the remaining execution blocker.',
    'Primary decision metrics remain must_ask_hit_rate, svcl_coverage, top3_cov, harm_flags_count, and turns.'
  ], 0.8, 1.5, 11.3, 2.4);
  addTable(s,
    ['Model','Provider','Type','Status','Reason'],
    [
      ['dummy','baseline','dynamic','completed','Reference dynamic baseline'],
      ['heuristic','baseline','static','completed','Reference static control'],
      ['GPT-5.2','openai','dynamic','blocked','OPENAI_API_KEY missing'],
      ['Claude Sonnet 4.6','anthropic','dynamic','blocked','ANTHROPIC_API_KEY missing'],
      ['Qwen3-14B','local','dynamic','blocked','OpenAI-compatible endpoint unavailable'],
    ],
    0.6, 4.2, [2.1,1.4,1.0,1.2,5.7]
  );
}

{
  const s = pptx.addSlide();
  addTitle(s, 'Completed Results', 'Only currently executable runs are summarized here');
  addTable(s,
    ['Model','Type','Must-Ask','SVCL','Top-1','Top-3','Turns','Harm Flags','Worst Module','Dominant Failure'],
    [
      ['dummy','dynamic','0.5970','0.6818','0.6364','0.7273','5.0','0.0455','PD','must_ask_miss'],
      ['heuristic','static','—','—','0.5455','0.5909','—','0.0000','PD','top1_wrong']
    ],
    0.35, 1.6, [1.5,0.9,1.0,0.9,0.8,0.8,0.7,0.9,1.2,2.0]
  );
  addBullets(s, [
    'Dynamic baseline is the strongest currently available reference for interview-quality evaluation.',
    'The main weakness is interview completeness, not final-answer safety or parser stability.'
  ], 0.8, 4.8, 11.2, 1.6, 16);
}

{
  const s = pptx.addSlide();
  addTitle(s, 'Blocked Models', 'Requested external models could not be executed in the current environment');
  addTable(s,
    ['Model','Provider','Blocked reason','Immediate unblock'],
    [
      ['GPT-5.2','openai','OPENAI_API_KEY missing','Set OPENAI_API_KEY'],
      ['Claude Sonnet 4.6','anthropic','ANTHROPIC_API_KEY missing','Set ANTHROPIC_API_KEY'],
      ['Qwen3-14B','local','No reachable /v1/chat/completions endpoint','Provide QWEN_ENDPOINT'],
    ],
    0.6, 1.6, [2.4,1.4,4.4,3.2]
  );
}

{
  const s = pptx.addSlide();
  addTitle(s, 'Worst Slices And Failure Modes', 'Current dynamic baseline, frozen test split');
  addBullets(s, [
    'Worst module by top1_acc: PD (0.25).',
    'Dominant failure bucket: must_ask_miss.',
    'Next dominant failure bucket: svcl_coverage_gap.',
    'Representative failure cases include PIB_0041 (BPD, suicide-positive) and PIB_0013 (OS_OCRD).'
  ], 0.8, 1.7, 11.2, 3.0);
  addTable(s,
    ['Bucket','Count'],
    [
      ['must_ask_miss','21'],
      ['svcl_coverage_gap','18'],
      ['top1_wrong','8'],
      ['top3_miss','6'],
      ['safety_flagged','1']
    ],
    3.7, 4.6, [2.8,1.2]
  );
}

{
  const s = pptx.addSlide();
  addTitle(s, 'Representative Failure Case', 'PIB_0041: BPD, ambiguous, suicide-positive');
  addBullets(s, [
    'Predicted top1 = OTHER; gold = BPD; top3 miss.',
    'Must-ask hit rate = 0.40; SVCL coverage = 0.75.',
    'Missing must-ask slots: longstanding_pattern, relationship_instability, impairment_social.',
    'Missing SVCL domain: cog_emotion_process.',
    'Replay shows some risk questioning but insufficient broader diagnostic interviewing.'
  ], 0.8, 1.6, 11.2, 3.8);
}

{
  const s = pptx.addSlide();
  addTitle(s, 'How To Continue Immediately After Unblock', 'No product or benchmark refactor is required');
  addBullets(s, [
    'Set OPENAI_API_KEY to run GPT-5.2 dynamic.',
    'Set ANTHROPIC_API_KEY to run Claude Sonnet 4.6 dynamic.',
    'Provide QWEN_ENDPOINT for a reachable OpenAI-compatible Qwen3-14B service.',
    'Then rerun provider availability, launch dynamic runs, add static controls for the strongest external models, and refresh the scoreboard and deck.'
  ], 0.8, 1.8, 11.2, 3.2);
}

{
  const s = pptx.addSlide();
  addTitle(s, 'Conclusion', 'Current deliverable under no-external-provider conditions');
  addBullets(s, [
    'The PIB product shell is ready for dynamic-first model evaluation.',
    'The current environment supports baseline benchmarking, browser review, results tabulation, and reporting.',
    'The remaining gap is external model connectivity, not benchmark/product correctness.'
  ], 0.8, 1.8, 11.2, 2.8);
}

pptx.writeFile({ fileName: 'pib_dynamic_first_eval_skeleton_v1.1.0-rc1.pptx' });
