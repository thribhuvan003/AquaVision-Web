const fs = require('fs');
const path = require('path');
const dir = 'c:\\Users\\ntena\\Downloads\\AquaVision_Ultimate_Build\\claude_code_repos\\claude-code-system-prompts\\system-prompts';
const out = 'c:\\Users\\ntena\\Downloads\\AquaVision_Ultimate_Build\\claude_code_repos\\combined_system_prompts.md';

console.log('Combining files...');
const files = fs.readdirSync(dir).filter(f => f.endsWith('.md'));
const chunks = [];
for (const file of files) {
  chunks.push('# File: ' + file + '\n\n' + fs.readFileSync(path.join(dir, file), 'utf8') + '\n\n');
}
fs.writeFileSync(out, chunks.join(''));
console.log('Done.');
