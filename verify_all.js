const fs = require('fs');
const path = require('path');

const baseDir = '06-正文';
const vols = fs.readdirSync(baseDir).filter(d => fs.statSync(path.join(baseDir, d)).isDirectory()).sort();

let totalChapters = 0;
let totalHan = 0;
let allPass = true;

vols.forEach(v => {
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
    const status = (han >= 3000 && han <= 5000);
    if (!status) {
      allPass = false;
      volPass = false;
      console.log(`  FAIL: ${f} (${han} Han chars)`);
    }
  });

  console.log(`[Volume] ${v}: ${files.length} chapters, ${volHan} Han chars, Status: ${volPass ? 'ALL PASS' : 'SOME FAIL'}`);
});

console.log('\n========================================');
console.log(`Total Chapters: ${totalChapters} / 130`);
console.log(`Total Han Characters: ${totalHan}`);
console.log(`Overall Novel Verification: ${allPass && totalChapters === 130 ? 'PERFECT 100% COMPLETE' : 'INCOMPLETE/FAILED'}`);

