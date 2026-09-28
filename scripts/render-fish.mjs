import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));

export function renderFish({ body, markings, fins }) {
  for (const color of [body, markings, fins]) {
    if (!/^#[0-9a-f]{6}$/i.test(color)) throw new Error('Colors must use #RRGGBB');
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="440" viewBox="0 0 800 440">
  <defs><clipPath id="body-clip"><path d="M140 224 C140 145 216 102 320 108 C424 110 484 161 540 224 C484 282 424 333 320 338 C216 344 140 300 140 224Z"/></clipPath></defs>
  <g stroke="#344C50" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">
    <path fill="${fins}" d="M308 118 Q331 60 386 61 Q379 109 411 142Z"/>
    <path fill="${fins}" d="M326 319 Q352 380 405 372 L414 299Z"/>
    <path fill="${fins}" d="M516 224 Q572 174 639 148 Q630 194 651 224 Q630 254 639 300 Q572 274 516 224Z"/>
    <path fill="${body}" d="M140 224 C140 145 216 102 320 108 C424 110 484 161 540 224 C484 282 424 333 320 338 C216 344 140 300 140 224Z"/>
    <g clip-path="url(#body-clip)" fill="none" stroke="${markings}" stroke-width="29">
      <path d="M326 105 Q285 157 318 198"/>
      <path d="M399 112 Q351 162 384 204"/>
      <path d="M465 135 Q420 177 450 211"/>
    </g>
    <path fill="${fins}" d="M331 239 Q384 219 389 263 Q359 279 331 239Z"/>
    <path fill="none" stroke-width="4" d="M276 220 Q285 243 272 260"/>
    <ellipse fill="#FFFFFF" cx="213" cy="207" rx="23" ry="26" stroke-width="4"/>
    <ellipse fill="#344C50" cx="206" cy="209" rx="10" ry="13" stroke="none"/>
    <circle fill="#FFFFFF" cx="204" cy="204" r="3.5" stroke="none"/>
    <path fill="none" stroke-width="4" d="M145 247 Q163 259 181 247"/>
    <path fill="none" stroke-width="3" d="M566 224 L613 224"/>
  </g>
</svg>`;
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const source = resolve(process.argv[2] ?? `${root}/data/ancestor-fish.json`);
  const output = resolve(process.argv[3] ?? `${root}/assets/ancestor`);
  const fish = JSON.parse(readFileSync(source, 'utf8'));
  const svg = renderFish(fish.colors);
  const title = escapeHtml(fish.name ?? '变异鱼');
  const generation = Number.isSafeInteger(fish.generation) && fish.generation >= 0 ? fish.generation : 0;
  const kind = generation === 0 ? '祖先鱼 · 三色模板' : `第 ${generation} 代 · 变异预览`;
  const sources = fish.contributors?.map(member => escapeHtml(member.display_name)) ?? [];
  const description = fish.description ? `<section class="description">${escapeHtml(fish.description)}</section>` : '';
  mkdirSync(output, { recursive: true });
  writeFileSync(`${output}/fish.svg`, svg);
  const swatches = [
    ['01', sources[0] ? `身体 · ${sources[0]}` : '身体 · 特征色一', fish.colors.body],
    ['02', sources[1] ? `斑纹 · ${sources[1]}` : '斑纹 · 特征色二', fish.colors.markings],
    ['03', fish.parent_name ? `鳍尾 · ${escapeHtml(fish.parent_name)}遗传色` : '鳍尾 · 特征色三', fish.colors.fins],
  ].map(([number, label, color]) => `<div class="swatch"><i style="background:${color}"></i><div><small>${number} / ${label}</small><b>${color.toUpperCase()}</b></div></div>`).join('');
  writeFileSync(`${output}/preview.html`, `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>${title}配色预览</title><style>
  *{box-sizing:border-box}body{margin:0;width:960px;min-height:720px;background:#EDF3F1;color:#344C50;font-family:'Noto Sans CJK SC',sans-serif;padding:38px 48px}
  header{display:flex;justify-content:space-between;align-items:end}h1{font-size:32px;margin:4px 0;font-weight:700;letter-spacing:2px}header p{font-size:13px;letter-spacing:2px;margin:0;color:#758986}.tag{border:1px solid #C6D6D1;border-radius:20px;padding:8px 16px;font-size:13px}
  main{margin-top:22px;background:#FFFFFF;border:1px solid #DDE8E4;border-radius:28px;height:420px;display:flex;align-items:center;justify-content:center}svg{width:760px;height:418px}
  .palette{display:flex;gap:14px;margin-top:20px}.swatch{flex:1;background:#FFFFFF;border-radius:16px;padding:15px;display:flex;gap:14px;align-items:center}.swatch i{width:43px;height:43px;border-radius:50%;flex-shrink:0}.swatch small{font-size:12px;color:#687E79;display:block}.swatch b{font-size:17px;letter-spacing:1px;display:block;margin-top:3px}footer{text-align:center;font-size:12px;color:#758986;margin-top:18px;letter-spacing:1px}
  .description{font-size:15px;line-height:1.8;margin:18px 6px 0;color:#526C66}
  </style><header><div><p>无限融合变异捕鱼 / GENERATION ${generation}</p><h1>${title}</h1></div><span class="tag">${kind}</span></header><main>${svg}</main><div class="palette">${swatches}</div>${description}<footer>固定轮廓 · 三色替换 · 程序绘制</footer></html>`);
  console.log(output);
}
