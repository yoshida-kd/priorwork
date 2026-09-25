// 論文のページ（paper.ts）の操作。ボタンとキーを拡張機能へのメッセージにするだけで、状態は持たない。
const vscode = acquireVsCodeApi();
const reason = document.getElementById('reason');

function decide(status) {
  const text = reason ? reason.value.trim() : '';
  if (status === 'excluded' && !text) {
    reason.classList.add('missing');
    reason.focus();
    return;
  }
  vscode.postMessage({ type: 'decide', status, reason: status === 'included' || status === 'candidate' ? '' : text });
}

document.addEventListener('click', (ev) => {
  const el = ev.target.closest('button, a');
  if (!el) {
    return;
  }
  if (el.dataset.status) {
    decide(el.dataset.status);
  } else if (el.dataset.nav) {
    vscode.postMessage({ type: 'nav', to: el.dataset.nav });
  } else if (el.dataset.reason && reason) {
    reason.value = el.dataset.reason;
    reason.classList.remove('missing');
    reason.focus();
  } else if (el.dataset.open === 'doi') {
    ev.preventDefault();
    vscode.postMessage({ type: 'openDoi' });
  } else if (el.dataset.open === 'fulltext') {
    vscode.postMessage({ type: 'fulltext' });
  } else if (el.dataset.open === 'report') {
    vscode.postMessage({ type: 'openReport' });
  }
});

document.addEventListener('keydown', (ev) => {
  if (ev.target === reason) {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      decide('excluded');
    } else if (ev.key === 'Escape') {
      reason.blur();
    }
    return;
  }
  if (ev.ctrlKey || ev.metaKey || ev.altKey) {
    return;
  }
  const key = ev.key.toLowerCase();
  const actions = {
    i: () => decide('included'),
    m: () => decide('maybe'),
    x: () => (reason && reason.value.trim() ? decide('excluded') : reason && reason.focus()),
    u: () => decide('candidate'),
    n: () => vscode.postMessage({ type: 'nav', to: 'nextUnscreened' }),
    j: () => vscode.postMessage({ type: 'nav', to: 'next' }),
    arrowright: () => vscode.postMessage({ type: 'nav', to: 'next' }),
    k: () => vscode.postMessage({ type: 'nav', to: 'prev' }),
    arrowleft: () => vscode.postMessage({ type: 'nav', to: 'prev' }),
    o: () => vscode.postMessage({ type: 'openDoi' }),
  };
  if (actions[key]) {
    ev.preventDefault();
    actions[key]();
  }
});
