// webview に渡す JavaScript を構文検査する（実行はしない）。VS Code の中の挙動はどのテストも見ていないので、
// せめて「読めない JS を配ってしまう」だけは防ぐ。
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
for (const f of ['paper.js']) {
  execFileSync(process.execPath, ['--check', join(root, 'media', f)], { stdio: 'inherit' });
  console.log('checked', f);
}
