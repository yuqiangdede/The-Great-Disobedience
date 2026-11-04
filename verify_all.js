const fs = require('fs');
const path = require('path');

const baseDir = '06-正文';
const vols = fs.readdirSync(baseDir).filter(d => fs.statSync(path.join(baseDir, d)).isDirectory()).sort();

let totalChapters = 0;
let totalHan = 0;
let allPass = true;
let allVolsUnder47k = true;

console.log('================================================================================');
console.log('                 《大模型不听话》全书十二卷正文与质量全面核验报告                ');
console.log('================================================================================\n');

vols.forEach((v, vIdx) => {
  const vPath = path.join(baseDir, v);
  const files = fs.readdirSync(vPath).filter(f => f.endsWith('.md')).sort();
  let volPass = true;
  let volHan = 0;

  files.forEach(f => {
    totalChapters++;
    const content = fs.readFileSync(path.join(vPath, f), 'utf8');
    const han = (content.match(/[\u4e00-\u9fa5]/g) || []).length;
    totalHan += han;
    volHan += han;
    const chapStatus = (han >= 3000 && han <= 5000);
    if (!chapStatus) {
      allPass = false;
      volPass = false;
      console.log(`  [FAIL CHAPTER] ${f} (${han} Han chars, expected 3000-5000)`);
    }
  });

  const volUnder47k = volHan < 47000;
  if (!volUnder47k) {
    allPass = false;
    allVolsUnder47k = false;
  }

  const volStatusStr = (volPass && volUnder47k) ? 'ALL PASS' : 'FAILED';
  console.log(`[Volume ${(vIdx + 1).toString().padStart(2, '0')}] ${v}`);
  console.log(`    Chapters: ${files.length.toString().padStart(2, ' ')} (${files[0].match(/第\d+章/)[0]} ~ ${files[files.length - 1].match(/第\d+章/)[0]})`);
  console.log(`    Total Han: ${volHan} chars | Under 47k check: ${volUnder47k ? 'PASS (<47000)' : 'FAIL (>=47000)'}`);
  console.log(`    Volume Status: ${volStatusStr}\n`);
});

console.log('================================================================================');
console.log(`Total Volumes : ${vols.length} (Expected: 12) -> ${vols.length === 12 ? 'PASS' : 'FAIL'}`);
console.log(`Total Chapters: ${totalChapters} / 130 -> ${totalChapters === 130 ? 'PASS' : 'FAIL'}`);
console.log(`Total Han Chars: ${totalHan}`);
console.log(`All Volumes < 47,000 Han chars: ${allVolsUnder47k ? 'PERFECT PASS' : 'FAILED'}`);
console.log(`Overall Novel Verification: ${allPass && totalChapters === 130 && vols.length === 12 && allVolsUnder47k ? 'PERFECT 100% COMPLETE & PASS' : 'INCOMPLETE/FAILED'}`);
console.log('================================================================================');
