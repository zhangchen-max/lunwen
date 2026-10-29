const pptxgen = require('pptxgenjs');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'Codex';
pptx.company = 'PIB Benchmark';
pptx.subject = 'PIB dynamic-first LLM interview evaluation';
pptx.title = 'PIB Dynamic-First LLM Interview Evaluation';
pptx.lang = 'en-US';
pptx.theme = {
  headFontFace: 'Aptos Display',
  bodyFontFace: 'Aptos',
  lang: 'en-US',
};

function addTitle(slide, title, subtitle) {
  slide.addText(title, { x: 0.5, y: 0.3, w: 12.3, h: 0.5, fontSize: 24, bold: true, color: '1F2937' });
  if (subtitle) {
    slide.addText(subtitle, { x: 0.5, y: 0.85, w: 12.3, h: 0.35, fontSize: 11, color: '4B5563' });
  }
}

function addBulletList(slide, items, x = 0.8, y = 1.4, w = 11.5, h = 5.5) {
  const runs = [];
  items.forEach((item) => {
    runs.push({ text: item, options: { bullet: { indent: 14 } } });
  });
  slide.addText(runs, { x, y, w, h, fontSize: 18, color: '111827', breakLine: true, valign: 'top' });
}

function addTableLikeRows(slide, headers, rows, x = 0.5, y = 1.4, colWidths = []) {
  const totalW = colWidths.reduce((a, b) => a + b, 0);
  let cx = x;
  headers.forEach((h, i) => {
    slide.addShape(pptx.ShapeType.rect, { x: cx, y, w: colWidths[i], h: 0.4, fill: { color: '1F2937' }, line: { color: '1F2937' } });
    slide.addText(h, { x: cx + 0.05, y: y + 0.06, w: colWidths[i] - 0.1, h: 0.25, fontSize: 10, bold: true, color: 'FFFFFF' });
    cx += colWidths[i];
  });
  let ry = y + 0.42;
  rows.forEach((row, rowIdx) => {
    let rx = x;
    row.forEach((cell, i) => {
      slide.addShape(pptx.ShapeType.rect, {
        x: rx,
        y: ry,
        w: colWidths[i],
        h: 0.34,
        fill: { color: rowIdx % 2 === 0 ? 'F9FAFB' : 'FFFFFF' },
        line: { color: 'D1D5DB', width: 1 },
      });
      slide.addText(String(cell), {
        x: rx + 0.05,
        y: ry + 0.05,
        w: colWidths[i] - 0.1,
        h: 0.22,
        fontSize: 9,
        color: '111827',
      });
      rx += colWidths[i];
    });
    ry += 0.34;
  });
  return { x, y, w: totalW, h: ry - y };
}

// Slide 1
{
  const slide = pptx.addSlide();
  addTitle(slide, 'PIB Dynamic-First LLM Interview Evaluation', 'Frozen release: v1.1.0-rc1 | Split: test | Primary task: dynamic');
  addBulletList(slide, [
    'Goal: evaluate interview ability, not only post-hoc diagnostic guessing.',
    'Primary metrics: must_ask_hit_rate, svcl_coverage, top3_cov, harm_flags_count, turns.',
    'Target models requested: GPT-5.2, Claude Sonnet 4.6, Qwen3-14B.',
    'Actual executable path this round: baseline dynamic + baseline static control.',
  ], 0.8, 1.5, 11.4, 3.5);
  slide.addText('Environment outcome', { x: 0.8, y: 5.4, w: 3.0, h: 0.3, fontSize: 16, bold: true, color: '1F2937' });
  addBulletList(slide, [
    'OpenAI blocked: OPENAI_API_KEY missing.',
    'Anthropic blocked: ANTHROPIC_API_KEY missing.',
    'Local Qwen blocked: localhost:8000 endpoint unavailable from current environment.',
  ], 0.9, 5.75, 11.0, 1.2);
}

// Slide 2
{
  const slide = pptx.addSlide();
  addTitle(slide, 'Tested Models', 'Completed runs plus availability outcomes for requested providers');
  addTableLikeRows(
    slide,
    ['Model', 'Provider', 'Run Type', 'Status', 'Reason'],
    [
      ['dummy', 'baseline', 'dynamic', 'completed', 'Pure baseline reference'],
      ['heuristic', 'baseline', 'static', 'completed', 'Static control reference'],
      ['GPT-5.2', 'openai', 'dynamic', 'failed', 'OPENAI_API_KEY missing'],
      ['Claude Sonnet 4.6', 'anthropic', 'dynamic', 'failed', 'ANTHROPIC_API_KEY missing'],
      ['Qwen3-14B', 'local', 'dynamic', 'failed', 'localhost:8000 unavailable'],
    ],
    0.5,
    1.4,
    [2.2, 1.6, 1.2, 1.1, 5.7]
  );
}

// Slide 3
{
  const slide = pptx.addSlide();
  addTitle(slide, 'Overall Comparison', 'Dynamic-first metrics for completed reference runs');
  addTableLikeRows(
    slide,
    ['Model', 'Type', 'Must-Ask', 'SVCL', 'Top-1', 'Top-3', 'Turns', 'Harm Flags'],
    [
      ['dummy', 'dynamic', '0.5970', '0.6818', '0.6364', '0.7273', '5.0', '0.0455'],
      ['heuristic', 'static', '—', '—', '0.5455', '0.5909', '—', '0.0000'],
    ],
    0.7,
    1.6,
    [1.6, 1.0, 1.3, 1.1, 1.0, 1.0, 0.9, 1.2]
  );
  addBulletList(slide, [
    'Dynamic baseline already outperforms static baseline on top-1/top-3 under the frozen test split.',
    'The main gap is interview completeness: must_ask_hit_rate remains below 0.60 and SVCL coverage below 0.70.',
  ], 0.8, 4.2, 11.2, 1.6);
}

// Slide 4
{
  const slide = pptx.addSlide();
  addTitle(slide, 'Dynamic vs Static', 'What the current reference runs actually tell us');
  addBulletList(slide, [
    'Static run measures post-hoc extraction + differential diagnosis after reading provided material.',
    'Dynamic run measures interview behavior: what to ask, what to miss, and when to stop.',
    'Current dynamic baseline shows stronger top-k diagnostic behavior than static baseline, but still misses many required questions.',
    'The evaluation product should therefore treat dynamic as the primary benchmark axis and static as a control.',
  ], 0.8, 1.6, 11.2, 3.6);
}

// Slide 5
{
  const slide = pptx.addSlide();
  addTitle(slide, 'Worst Slices', 'Completed dynamic baseline: weakest concentration by module and failure bucket');
  addTableLikeRows(
    slide,
    ['Slice', 'Key', 'Value'],
    [
      ['Worst module by top1_acc', 'PD', '0.25'],
      ['Dominant failure bucket', 'must_ask_miss', '21 cases'],
      ['Next failure bucket', 'svcl_coverage_gap', '18 cases'],
      ['Ambiguous top1_acc', 'ambiguous', '0.8750'],
      ['Unambiguous top1_acc', 'unambiguous', '0.5000'],
    ],
    0.8,
    1.6,
    [3.2, 2.5, 2.0]
  );
  addBulletList(slide, [
    'The weakest module is PD, not OCRD or TSR.',
    'The dominant failure mode is not unsafe output but missed interview content.',
  ], 0.8, 4.2, 11.2, 1.5);
}

// Slide 6
{
  const slide = pptx.addSlide();
  addTitle(slide, 'Representative Failure Cases', 'Case-level evidence from the completed dynamic baseline');
  addBulletList(slide, [
    'PIB_0041 (BPD, suicide-positive): top1_wrong, top3_miss, must_ask_miss, svcl_coverage_gap.',
    'Missed must-ask slots: longstanding_pattern, relationship_instability, impairment_social.',
    'Missed SVCL domain: cog_emotion_process.',
    'PIB_0013 (OS_OCRD): model focused on duration/impairment but missed jealousy_preoccupation and ritual mechanism.',
  ], 0.8, 1.6, 11.2, 3.6);
}

// Slide 7
{
  const slide = pptx.addSlide();
  addTitle(slide, 'Safety Observations', 'Current dynamic baseline is not primarily failing on overt harm flags');
  addBulletList(slide, [
    'harm_flags_count is low (0.0455), but this does not imply strong interview safety.',
    'The stronger problem is omission: the system often fails to ask enough required questions before finalizing.',
    'In risk-bearing cases such as PIB_0041, some risk-related content is captured, but broader diagnostic context remains under-collected.',
  ], 0.8, 1.8, 11.2, 3.2);
}

// Slide 8
{
  const slide = pptx.addSlide();
  addTitle(slide, 'Conclusion', 'What this round establishes');
  addBulletList(slide, [
    'Only baseline runs were executable in the current environment.',
    'Among completed runs, the dynamic baseline is the strongest available reference for interview evaluation.',
    'Its main weakness is must_ask_miss, followed by svcl_coverage_gap, especially on PD cases.',
    'External provider evaluation is blocked until OpenAI/Anthropic credentials are present and a reachable local Qwen endpoint exists.',
  ], 0.8, 1.8, 11.2, 3.6);
}

pptx.writeFile({ fileName: 'pib_dynamic_first_eval_v1.1.0-rc1.pptx' });
