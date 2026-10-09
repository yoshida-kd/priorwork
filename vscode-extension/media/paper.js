// 論文のページ（paper.ts）の操作。ボタンとキーを拡張機能へのメッセージにする。
// 状態として持つのはカードの書きかけだけ（論文ごとに webview の状態へ退避し、描き直されても戻す）。
const vscode = acquireVsCodeApi();
const reason = document.getElementById('reason');
const card = document.querySelector('section.card[data-number]');
const draftKey = card ? `${card.dataset.survey}#${card.dataset.number}` : '';

function cardInputs() {
  return card ? [...card.querySelectorAll('[data-field]')] : [];
}

function changedFields() {
  return cardInputs().filter((el) => el.value !== el.dataset.original);
}

function fit(el) {
  if (el.tagName === 'TEXTAREA') {
    el.rows = Math.max(2, el.value.split('\n').length + 1);
  }
}

/** 変更の印を付け、書きかけを退避する（元に戻した欄は退避から消す）。 */
function noteChanges() {
  const changed = changedFields();
  card.classList.toggle('dirty', changed.length > 0);
  const state = vscode.getState() || {};
  const drafts = { ...(state.drafts || {}) };
  if (changed.length) {
    drafts[draftKey] = Object.fromEntries(changed.map((el) => [el.dataset.field, el.value]));
  } else {
    delete drafts[draftKey];
  }
  vscode.setState({ ...state, drafts });
}

function saveCard() {
  const changed = changedFields();
  if (changed.length && !changed.some((el) => el.dataset.field === 'evidence' && !el.value)) {
    vscode.postMessage({ type: 'saveCard', values: Object.fromEntries(changed.map((el) => [el.dataset.field, el.value])) });
  }
}

if (card) {
  const draft = ((vscode.getState() || {}).drafts || {})[draftKey] || {};
  for (const el of cardInputs()) {
    if (el.dataset.field in draft) {
      el.value = draft[el.dataset.field];
      fit(el);
    }
  }
  noteChanges();
  card.addEventListener('input', (ev) => {
    fit(ev.target);
    noteChanges();
  });
}

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
  } else if (el.dataset.card === 'save') {
    saveCard();
  } else if (el.dataset.card === 'agent') {
    vscode.postMessage({ type: 'askAgent' });
  } else if (el.dataset.card === 'revert') {
    for (const input of cardInputs()) {
      input.value = input.dataset.original;
      fit(input);
    }
    noteChanges();
  }
});

document.addEventListener('keydown', (ev) => {
  if (card && card.contains(ev.target)) {   // カードに書いている間は、採否のキーを効かせない
    if ((ev.ctrlKey || ev.metaKey) && (ev.key.toLowerCase() === 's' || ev.key === 'Enter')) {
      ev.preventDefault();
      saveCard();
    }
    return;
  }
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 's') {
    ev.preventDefault();
    saveCard();
    return;
  }
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
