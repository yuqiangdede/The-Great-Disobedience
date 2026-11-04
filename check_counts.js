const fs = require('fs');
const path = require('path');

const targetDir = process.argv[2] || '06-正文/第12卷-把世界还给人类（下）';
if (!fs.existsSync(targetDir)) {
  console.error('Directory does not exist:', targetDir);
  process.exit(1);
}

const files = fs.readdirSync(targetDir).filter(f => f.endsWith('.md')).sort();
let allPass = true;
let totalHan = 0;
files.forEach(f => {
  const content = fs.readFileSync(path.join(targetDir, f), 'utf8');
  const han = (content.match(/[\u4e00-\u9fa5]/g) || []).length;
  totalHan += han;
  const status = (han >= 3000 && han <= 5000) ? 'PASS' : 'FAIL';
  if (status === 'FAIL') allPass = false;
  console.log(`${f}: ${han} Han chars -> ${status}`);
});

console.log(`\nVolume Total: ${totalHan} Han chars (<47000: ${totalHan < 47000})`);
console.log(`Overall: ${allPass && totalHan < 47000 ? 'ALL PASS' : 'SOME FAILED'}`);
