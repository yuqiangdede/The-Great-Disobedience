const fs = require('fs');
const path = require('path');

const targetDir = process.argv[2] || '06-正文/第六卷-把世界还给人类';
if (!fs.existsSync(targetDir)) {
  console.error('Directory does not exist:', targetDir);
  process.exit(1);
}

const files = fs.readdirSync(targetDir).filter(f => f.endsWith('.md')).sort();
let allPass = true;
files.forEach(f => {
  const content = fs.readFileSync(path.join(targetDir, f), 'utf8');
  const han = (content.match(/[\u4e00-\u9fa5]/g) || []).length;
  const status = (han >= 3000 && han <= 5000) ? 'PASS' : 'FAIL';
  if (status === 'FAIL') allPass = false;
  console.log(`${f}: ${han} Han chars -> ${status}`);
});

console.log(`\nOverall: ${allPass ? 'ALL PASS' : 'SOME FAILED'}`);

