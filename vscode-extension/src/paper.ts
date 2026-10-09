// paper.ts — 論文のページ（webview）。要旨・書誌・警告を見て、採用・保留・除外を決める。
//
// ページは1枚を使い回す。採否を決めたら（設定 priorwork.autoAdvance）次の未選別の論文に進むので、
// 候補を上から順に選別できる。採否の記録は CLI（`priorwork include|maybe|exclude|reset`）が行い、
// ここは結果を読み直して描き直すだけ。
import * as vscode from 'vscode';
import { CardReport, Entry, runJson, Scope, Status } from './cli';
import { Model } from './model';
import { authorYear, groupLabel } from './tree';

export interface PaperActions {
    decide(survey: string, numbers: number[], status: Status, reason: string): Promise<boolean>;
    fulltext(survey: string, number: number): Promise<void>;
    saveCard(survey: string, number: number, values: Record<string, string>): Promise<boolean>;
    askAgent(survey: string, number: number): Thenable<unknown>;
    openReport(survey: string): Promise<void>;
}

type Msg =
    | { type: 'decide'; status: Status; reason: string }
    | { type: 'nav'; to: 'prev' | 'next' | 'nextUnscreened' }
    | { type: 'openDoi' }
    | { type: 'fulltext' }
    | { type: 'saveCard'; values: Record<string, string> }
    | { type: 'askAgent' }
    | { type: 'openReport' };

function esc(s: unknown): string {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));
}

export function badge(status: string): string {
    switch (status) {
        case 'ssci': return vscode.l10n.t('✅ SSCI (checked against the list)');
        case 'ssci_likely': return vscode.l10n.t('🟡 Probably SSCI (guessed from the journal name; verify)');
        case 'journal': return vscode.l10n.t('🔍 Journal (SSCI not verified)');
        case 'not_ssci': return vscode.l10n.t('⚪ Not in SSCI (checked against the list)');
        case 'book': return vscode.l10n.t('📕 Book (outside SSCI)');
        case 'preprint': return vscode.l10n.t('❌ Working paper / preprint');
        default: return vscode.l10n.t('❓ Unknown venue');
    }
}

export function doiUrl(e: Entry): string | undefined {
    return e.record.doi ? `https://doi.org/${e.record.doi}` : (e.record.url || undefined);
}

export class PaperPanel implements vscode.Disposable {
    private panel?: vscode.WebviewPanel;
    private survey?: string;
    private number?: number;
    private busy = false;
    private readonly sub: vscode.Disposable;

    constructor(private readonly context: vscode.ExtensionContext, private readonly model: Model,
                private readonly actions: PaperActions) {
        // エージェントや別の操作で状態が変わったら描き直す
        this.sub = model.onDidChange(() => { void this.render(); });
    }

    dispose(): void {
        this.sub.dispose();
        this.panel?.dispose();
    }

    /** number を省くと、最初の未選別の論文（無ければ最初の論文）。 */
    async show(survey: string, number?: number): Promise<void> {
        const papers = await this.model.papers(survey);
        if (!papers.length) {
            void vscode.window.showInformationMessage(vscode.l10n.t('This survey has no papers yet. Search first.'));
            return;
        }
        const target = number ?? (papers.find((e) => e.status === 'candidate' || e.status === 'maybe') ?? papers[0]).number;
        this.survey = survey;
        this.number = target;
        if (!this.panel) {
            this.panel = vscode.window.createWebviewPanel('priorwork.paper', vscode.l10n.t('Paper'),
                { viewColumn: vscode.ViewColumn.Active, preserveFocus: false }, {
                    enableScripts: true,
                    retainContextWhenHidden: true,
                    localResourceRoots: [vscode.Uri.joinPath(this.context.extensionUri, 'media')],
                });
            this.panel.iconPath = vscode.Uri.joinPath(this.context.extensionUri, 'media', 'icon.png');
            this.panel.onDidDispose(() => { this.panel = undefined; });
            this.panel.webview.onDidReceiveMessage((m: Msg) => { void this.onMessage(m); });
        } else {
            this.panel.reveal(undefined, false);
        }
        await this.render();
    }

    private async current(): Promise<{ papers: Entry[]; entry?: Entry }> {
        if (!this.survey) {
            return { papers: [] };
        }
        const papers = await this.model.papers(this.survey);
        return { papers, entry: papers.find((e) => e.number === this.number) };
    }

    private async onMessage(m: Msg): Promise<void> {
        if (!this.survey || this.number === undefined || this.busy) {
            return;
        }
        const survey = this.survey;
        const { papers, entry } = await this.current();
        if (!entry) {
            return;
        }
        switch (m.type) {
            case 'decide': {
                this.busy = true;
                const wasOpen = entry.status === 'candidate' || entry.status === 'maybe';
                try {
                    const ok = await this.actions.decide(survey, [entry.number], m.status, m.reason);
                    if (ok && wasOpen && m.status !== 'candidate'
                        && vscode.workspace.getConfiguration('priorwork').get<boolean>('autoAdvance', true)) {
                        const next = nextOpen(papers, entry.number);
                        if (next !== undefined) {
                            this.number = next;
                        }
                    }
                } finally {
                    this.busy = false;
                }
                await this.render();
                return;
            }
            case 'nav': {
                const i = papers.findIndex((e) => e.number === entry.number);
                if (m.to === 'nextUnscreened') {
                    const next = nextOpen(papers, entry.number);
                    if (next === undefined) {
                        void vscode.window.showInformationMessage(vscode.l10n.t('No unscreened papers left.'));
                        return;
                    }
                    this.number = next;
                } else {
                    const j = m.to === 'next' ? Math.min(i + 1, papers.length - 1) : Math.max(i - 1, 0);
                    this.number = papers[j].number;
                }
                await this.render();
                return;
            }
            case 'openDoi': {
                const url = doiUrl(entry);
                if (url) {
                    void vscode.env.openExternal(vscode.Uri.parse(url));
                }
                return;
            }
            case 'fulltext':
                await this.actions.fulltext(survey, entry.number);
                return;
            case 'askAgent':
                await this.actions.askAgent(survey, entry.number);
                return;
            case 'saveCard':
                this.busy = true;
                try {
                    await this.actions.saveCard(survey, entry.number, m.values);
                } finally {
                    this.busy = false;
                }
                await this.render();
                return;
            case 'openReport':
                await this.actions.openReport(survey);
                return;
        }
    }

    private async render(): Promise<void> {
        if (!this.panel || !this.survey) {
            return;
        }
        let papers: Entry[];
        let entry: Entry | undefined;
        let scope: Scope | undefined;
        let card: CardReport | string | undefined;
        try {
            ({ papers, entry } = await this.current());
            scope = (await this.model.detail(this.survey)).scope;
            if (entry?.status === 'included') {
                // カードが読めなくても（レポートの管理ブロックが壊れているなど）、選別はできるようにする
                card = await runJson<CardReport>(this.model.root, ['card', this.survey, String(entry.number)])
                    .catch((e: unknown) => (e instanceof Error ? e.message : String(e)));
            }
        } catch (e) {
            this.panel.webview.html = this.page(`<p class="error">${esc(e instanceof Error ? e.message : e)}</p>`);
            return;
        }
        if (!entry) {
            this.panel.webview.html = this.page(`<p>${esc(vscode.l10n.t('This paper is no longer in the survey.'))}</p>`);
            return;
        }
        this.panel.title = `#${entry.number} ${authorYear(entry)}`;
        const open = papers.filter((e) => e.status === 'candidate' || e.status === 'maybe').length;
        this.panel.webview.html = this.page(this.body(entry, papers, scope, open, card));
    }

    private body(e: Entry, papers: Entry[], scope: Scope | undefined, open: number,
                 card: CardReport | string | undefined): string {
        const r = e.record;
        const L = vscode.l10n;
        const i = papers.findIndex((p) => p.number === e.number);
        const url = doiUrl(e);
        const reasons = commonReasons(papers);
        const criteria = scope && (scope.inclusion || scope.exclusion || scope.question) ? `
            <details class="criteria" open><summary>${esc(L.t('Scope'))}</summary>
              ${scope.question ? `<p><b>${esc(L.t('Research question'))}</b> ${esc(scope.question)}</p>` : ''}
              ${scope.inclusion ? `<p><b>${esc(L.t('Inclusion criteria'))}</b> ${esc(scope.inclusion)}</p>` : ''}
              ${scope.exclusion ? `<p><b>${esc(L.t('Exclusion criteria'))}</b> ${esc(scope.exclusion)}</p>` : ''}
            </details>` : '';
        const history = e.history.length > 1 ? `<p class="muted">${esc(L.t('History'))}: ${e.history.map((h) =>
            esc(groupLabel(h.status)) + (h.reason ? ` (${esc(h.reason)})` : '')).join(' → ')}</p>` : '';
        const summary = r.tldr ? `<p><b>TL;DR</b> ${esc(r.tldr)}</p>` : '';
        const abstract = r.abstract ? `<p class="abstract">${esc(r.abstract)}</p>`
            : `<p class="muted">${esc(L.t('No abstract.'))}</p>`;
        const warnings = r.warnings.map((w) => `<p class="warning">⚠️ ${esc(w)}</p>`).join('');
        const status = e.status;
        const btn = (s: Status, key: string, label: string, cls: string): string =>
            `<button class="${cls}${status === s ? ' current' : ''}" data-status="${s}" title="${esc(key)}">${esc(label)}`
            + ` <kbd>${esc(key)}</kbd></button>`;
        return `
        <nav>
          <button data-nav="prev" title="K / ←">‹</button>
          <span>${i + 1} / ${papers.length}</span>
          <button data-nav="next" title="J / →">›</button>
          <button data-nav="nextUnscreened" title="N">${esc(L.t('Next unscreened'))} (${open})</button>
          <span class="spacer"></span>
          <button data-open="report">${esc(L.t('Open the report'))}</button>
        </nav>
        ${criteria}
        <header>
          <p class="status s-${status}">#${e.number} · ${esc(groupLabel(status))}${e.reason ? ` — ${esc(e.reason)}` : ''}</p>
          <h1>${esc(r.title)}</h1>
          <p>${esc(r.authors.join(', ') || 'Unknown')}</p>
          <p><i>${esc(r.journal_name || 'N/A')}</i> (${esc(r.year ?? 'n.d.')}) · ${esc(badge(r.ssci.status))}
             · ${esc(L.t('cited by {0}', r.citation_count))}
             ${url ? ` · <a href="#" data-open="doi">${esc(r.doi || L.t('Link'))}</a>` : ''}</p>
          ${warnings}
          ${history}
        </header>
        <section class="decide">
          ${btn('included', 'I', L.t('Include'), 'include')}
          ${btn('maybe', 'M', L.t('Maybe'), 'maybe')}
          <span class="exclude-group">
            <input id="reason" type="text" placeholder="${esc(L.t('Reason (required to exclude)'))}"
                   value="${esc(status === 'excluded' || status === 'maybe' ? e.reason : '')}">
            ${btn('excluded', 'X', L.t('Exclude'), 'exclude')}
          </span>
          ${status !== 'candidate' ? `<button class="reset" data-status="candidate" title="U">${esc(L.t('Back to candidate'))} <kbd>U</kbd></button>` : ''}
          ${reasons.length ? `<div class="reasons">${reasons.map((x) =>
              `<button class="chip" data-reason="${esc(x)}">${esc(x)}</button>`).join('')}</div>` : ''}
        </section>
        <section>
          ${summary}
          ${abstract}
          <p class="muted">${esc(L.t('Found by'))}: ${esc(e.found_by.join(', '))}
            ${e.fulltext ? ` · ${esc(L.t('Full text'))}: ${esc(e.fulltext.path)}` : ''}</p>
          ${status === 'included' && !e.fulltext ? `<button data-open="fulltext">${esc(L.t('Get the full text'))}</button>` : ''}
        </section>
        ${card === undefined ? '' : this.cardForm(e, card)}
        <p class="keys muted">${esc(L.t('Keys: I include · M maybe · X exclude (type the reason first) · U back to candidate · N next unscreened · J/K next/previous · O open DOI · Ctrl+S save the card'))}</p>`;
    }

    /** 採用論文のカードの記入欄。書きかけは paper.js が論文ごとに webview の状態へ退避する。 */
    private cardForm(e: Entry, card: CardReport | string): string {
        const L = vscode.l10n;
        if (typeof card === 'string') {
            return `<section class="card"><h2>${esc(L.t('Paper card'))}</h2><p class="error">${esc(card)}</p></section>`;
        }
        const evidence = card.evidence ?? '';
        const options = card.evidence_options.map((o) =>
            `<option value="${esc(o.key)}"${o.key === evidence ? ' selected' : ''}>${esc(o.label)}</option>`).join('');
        const fields = card.fields.map((f) => `
          <label class="field"><span>${esc(f.label)}</span>
            <textarea data-field="${esc(f.key)}" data-original="${esc(f.value)}"
                      rows="${Math.max(2, f.value.split('\n').length + 1)}">${esc(f.value)}</textarea></label>`).join('');
        return `
        <section class="card" data-survey="${esc(this.survey)}" data-number="${e.number}">
          <h2>${esc(L.t('Paper card'))} <span class="unsaved">● ${esc(L.t('Unsaved changes'))}</span></h2>
          <p class="muted">${esc(L.t('Write only what the abstract or the full text says. The first line of each field goes into the comparison matrix; the lines below it become bullet points.'))}</p>
          <label class="field"><span>${esc(L.t('Evidence'))}</span>
            <select data-field="evidence" data-original="${esc(evidence)}">
              ${evidence ? '' : `<option value="" selected>${esc(L.t('(unreadable — choose one)'))}</option>`}${options}
            </select></label>
          ${fields}
          <div class="card-actions">
            <button class="include" data-card="save">${esc(L.t('Save the card'))} <kbd>Ctrl+S</kbd></button>
            <button data-card="revert">${esc(L.t('Discard the changes'))}</button>
            <span class="spacer"></span>
            <button data-card="agent" title="${esc(L.t('Copies a request to paste into your agent\'s chat'))}">${esc(L.t('Ask the agent to fill it in'))}</button>
          </div>
        </section>`;
    }

    private page(body: string): string {
        const webview = this.panel!.webview;
        const media = (f: string): vscode.Uri => webview.asWebviewUri(vscode.Uri.joinPath(this.context.extensionUri, 'media', f));
        const nonce = [...Array(24)].map(() => Math.floor(Math.random() * 36).toString(36)).join('');
        return `<!DOCTYPE html>
<html lang="${vscode.env.language}">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="${media('paper.css')}">
</head>
<body>
${body}
<script nonce="${nonce}" src="${media('paper.js')}"></script>
</body>
</html>`;
    }
}

/** number より後ろ（無ければ先頭から）で、最初の未選別（候補・保留）の論文。 */
function nextOpen(papers: Entry[], number: number): number | undefined {
    const open = papers.filter((e) => (e.status === 'candidate' || e.status === 'maybe') && e.number !== number);
    return (open.find((e) => e.number > number) ?? open[0])?.number;
}

/** このサーベイでよく使われた除外・保留の理由（多い順に8つまで）。 */
function commonReasons(papers: Entry[]): string[] {
    const n = new Map<string, number>();
    for (const e of papers) {
        if (e.reason && (e.status === 'excluded' || e.status === 'maybe')) {
            n.set(e.reason, (n.get(e.reason) ?? 0) + 1);
        }
    }
    return [...n.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([r]) => r);
}
