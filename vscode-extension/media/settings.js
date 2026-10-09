// 設定のページ（settings.ts）の操作。変えた欄だけを拡張機能に渡す。
// 秘密の欄（API キー・パスワード）は、何か入力したときと「削除」を押したときだけ渡す。
const vscode = acquireVsCodeApi();
const inputs = [...document.querySelectorAll('input[data-key]')];
const removed = new Set();

function values() {
  const out = {};
  for (const el of inputs) {
    const key = el.dataset.key;
    if (el.dataset.secret) {
      if (el.value.trim()) {
        out[key] = el.value.trim();
      } else if (removed.has(key)) {
        out[key] = '';
      }
    } else if (el.value !== el.dataset.original) {
      out[key] = el.value.trim();
    }
  }
  return out;
}

function noteChanges() {
  document.body.classList.toggle('dirty', Object.keys(values()).length > 0);
}

document.addEventListener('input', noteChanges);

document.addEventListener('click', (ev) => {
  const el = ev.target.closest('button');
  if (!el) {
    return;
  }
  if (el.dataset.remove) {
    removed.add(el.dataset.remove);
    const input = inputs.find((i) => i.dataset.key === el.dataset.remove);
    if (input) {
      input.value = '';
      input.placeholder = el.dataset.removed;
    }
    el.disabled = true;
    noteChanges();
  } else if (el.dataset.action) {
    vscode.postMessage({ type: el.dataset.action, values: values() });
  }
});

document.addEventListener('keydown', (ev) => {
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 's') {
    ev.preventDefault();
    vscode.postMessage({ type: 'save', values: values() });
  }
});
