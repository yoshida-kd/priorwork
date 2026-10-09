// settings.ts — 設定のページ（webview）。API キー・Zotero（.env）と SSCI リストを、ファイルを開かずに設定する。
//
// 読むのも書くのも `priorwork settings`。キーの値はページに出さず（CLI も返さない）、書くときは標準入力で渡す。
import * as vscode from 'vscode';
import { DoctorCheck, DoctorReport, runJson, SettingItem, SettingsReport } from './cli';
import { Model } from './model';

export interface SettingsActions {
    busy<T>(title: string, task: (opts: { token: vscode.CancellationToken; onOutput: (s: string) => void }) => Promise<T>): Thenable<T>;
    fail(e: unknown): void;
}

/** 秘密の欄は undefined（触っていない）と ''（消す）を区別する。JSON では undefined のキーは落ちる。 */
type Values = Record<string, string>;

type Msg =
    | { type: 'save'; values: Values }
    | { type: 'check'; values: Values }
    | { type: 'importSsci'; values: Values };

function esc(s: unknown): string {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));
}

export class SettingsPanel implements vscode.Disposable {
    private panel?: vscode.WebviewPanel;
    private checks?: DoctorCheck[];
    private busyNow = false;

    constructor(private readonly context: vscode.ExtensionContext, private readonly model: Model,
                private readonly actions: SettingsActions) {}

    dispose(): void {
        this.panel?.dispose();
    }

    async show(): Promise<void> {
        if (!this.panel) {
            this.panel = vscode.window.createWebviewPanel('priorwork.settings', vscode.l10n.t('Prior Work Settings'),
                vscode.ViewColumn.Active, {
                    enableScripts: true,
                    localResourceRoots: [vscode.Uri.joinPath(this.context.extensionUri, 'media')],
                });
            this.panel.iconPath = vscode.Uri.joinPath(this.context.extensionUri, 'media', 'icon.png');
            this.panel.onDidDispose(() => { this.panel = undefined; this.checks = undefined; });
            this.panel.webview.onDidReceiveMessage((m: Msg) => { void this.onMessage(m); });
        } else {
            this.panel.reveal();
        }
        await this.render();
    }

    private async onMessage(m: Msg): Promise<void> {
        if (this.busyNow) {
            return;
        }
        this.busyNow = true;
        try {
            if (Object.keys(m.values).length && !await this.save(m.values)) {
                return;
            }
            if (m.type === 'save' && Object.keys(m.values).length) {
                vscode.window.setStatusBarMessage(vscode.l10n.t('Prior Work: saved the settings.'), 4000);
            } else if (m.type === 'check') {
                const r = await this.actions.busy(vscode.l10n.t('checking the connections'),
                    (o) => runJson<DoctorReport>(this.model.root, ['doctor', '--online'], o));
                this.checks = r.checks;
            } else if (m.type === 'importSsci') {
                await this.importSsci();
            }
        } catch (e) {
            this.actions.fail(e);
        } finally {
            this.busyNow = false;
        }
        await this.render();
    }

    private async save(values: Values): Promise<boolean> {
        try {
            await runJson(this.model.root, ['settings', '--stdin'], { input: JSON.stringify(values) });
            this.model.refresh();
            return true;
        } catch (e) {
            this.actions.fail(e);
            return false;
        }
    }

    private async importSsci(): Promise<void> {
        const picked = await vscode.window.showOpenDialog({
            canSelectMany: false,
            filters: { CSV: ['csv'] },
            openLabel: vscode.l10n.t('Import'),
            title: vscode.l10n.t('The SSCI list downloaded from the Master Journal List (CSV)'),
        });
        if (!picked?.length) {
            return;
        }
        const r = await runJson<SettingsReport>(this.model.root, ['settings', '--import-ssci', picked[0].fsPath]);
        this.model.refresh();
        void vscode.window.showInformationMessage(vscode.l10n.t('Prior Work: imported the SSCI list ({0} journals).',
                                                                r.ssci.journals));
    }

    private async render(): Promise<void> {
        if (!this.panel) {
            return;
        }
        if (!this.model.root) {
            this.panel.webview.html = this.page(`<p>${esc(vscode.l10n.t('Open a Prior Work workspace folder first.'))}</p>`);
            return;
        }
        try {
            const r = await runJson<SettingsReport>(this.model.root, ['settings']);
            this.panel.webview.html = this.page(this.body(r));
        } catch (e) {
            this.panel.webview.html = this.page(`<p class="error">${esc(e instanceof Error ? e.message : e)}</p>`);
        }
    }

    private body(r: SettingsReport): string {
        const L = vscode.l10n;
        const items = new Map(r.items.map((i) => [i.key, i]));
        const labels: Record<string, string> = {
            SEMANTIC_SCHOLAR_API_KEY: L.t('API key'),
            OPENALEX_API_KEY: L.t('API key'),
            OPENALEX_MAILTO: L.t('Your email address (sent with requests, as OpenAlex asks)'),
            ZOTERO_API_KEY: L.t('API key'),
            ZOTERO_USER_ID: L.t('User ID ("Your user ID for use in API calls" on the same page)'),
            ZOTERO_DATA_DIR: L.t('Zotero\'s data folder, if Zotero runs on this computer (default: ~/Zotero)'),
            ZOTERO_WEBDAV_URL: L.t('URL of the folder that holds the PDF zips (the URL set in Zotero, plus zotero/)'),
            ZOTERO_WEBDAV_USER: L.t('User name'),
            ZOTERO_WEBDAV_PASSWORD: L.t('Password (an app password with read-only access is safer)'),
        };
        const link = (url: string, text: string): string => `<a href="${esc(url)}">${esc(text)}</a>`;
        const groups: { title: string; note: string; keys: string[] }[] = [
            { title: 'Semantic Scholar',
              note: L.t('Recommended. Searches work without a key, but often fail on the rate limit.') + ' '
                  + link('https://www.semanticscholar.org/product/api#api-key-form', L.t('Request a free API key')),
              keys: ['SEMANTIC_SCHOLAR_API_KEY'] },
            { title: 'OpenAlex',
              note: L.t('Optional. Used to verify DOIs and journals; works without a key, with a daily usage cap.'),
              keys: ['OPENALEX_API_KEY', 'OPENALEX_MAILTO'] },
            { title: 'Zotero',
              note: L.t('Optional, read only: shows which included papers are in Zotero and gets full texts from the PDFs attached there.') + ' '
                  + link('https://www.zotero.org/settings/keys', L.t('Create a key with only "Allow library access"')),
              keys: ['ZOTERO_API_KEY', 'ZOTERO_USER_ID', 'ZOTERO_DATA_DIR'] },
            { title: L.t('Zotero file sync through WebDAV'),
              note: L.t('Only if Zotero syncs its files through WebDAV (Nextcloud and the like).'),
              keys: ['ZOTERO_WEBDAV_URL', 'ZOTERO_WEBDAV_USER', 'ZOTERO_WEBDAV_PASSWORD'] },
        ];
        const field = (i: SettingItem): string => {
            const label = `<span>${esc(labels[i.key] ?? i.key)} <code>${esc(i.key)}</code></span>`;
            if (!i.secret) {
                return `<label class="field">${label}<input type="text" data-key="${esc(i.key)}"
                          data-original="${esc(i.value)}" value="${esc(i.value)}" spellcheck="false"></label>`;
            }
            const placeholder = i.set ? L.t('Set — type a new one to replace it') : L.t('Not set');
            return `<label class="field">${label}<span class="secret">
                      <input type="password" data-key="${esc(i.key)}" data-secret="1" placeholder="${esc(placeholder)}"
                             autocomplete="off" spellcheck="false">
                      ${i.set ? `<button data-remove="${esc(i.key)}" data-removed="${esc(L.t('Removed when you save'))}">${esc(L.t('Remove'))}</button>` : ''}</span></label>`;
        };
        const sections = groups.map((g) => `
          <section class="group"><h2>${esc(g.title)}</h2><p class="muted">${g.note}</p>
            ${g.keys.map((k) => items.get(k)).filter((i): i is SettingItem => Boolean(i)).map(field).join('')}
          </section>`).join('');
        const ssci = r.ssci.file
            ? `<p>✅ ${esc(L.t('{0} ({1} journals)', r.ssci.file, r.ssci.journals))}</p>`
            : `<p class="warning">${esc(L.t('Not set, so the SSCI status is guessed from a built-in list of about 100 major journals (🟡).'))}</p>`;
        const icon = { ok: '✅', warn: '⚠️', ng: '❌' };
        const checks = this.checks ? `
          <section class="group"><h2>${esc(L.t('Diagnosis'))}</h2>
            <ul class="checks">${this.checks.map((c) =>
                `<li class="c-${c.level}">${icon[c.level]} <b>${esc(c.name)}</b>: ${esc(c.message)}</li>`).join('')}</ul>
          </section>` : '';
        return `
        <h1>${esc(L.t('Prior Work Settings'))}</h1>
        <p class="muted">${esc(L.t('Saved in .env in the workspace, which is kept out of Git. Keys are never shown here.'))}</p>
        ${sections}
        <section class="group"><h2>${esc(L.t('SSCI journal list'))}</h2>
          <p class="muted">${esc(L.t('Only Clarivate\'s Master Journal List settles whether a journal is in the SSCI. Download the SSCI list there as CSV and import it.'))}
             ${link('https://mjl.clarivate.com/', 'Master Journal List')}</p>
          ${ssci}
          <button data-action="importSsci">${esc(L.t('Import the SSCI List (CSV)…'))}</button>
        </section>
        <div class="actions">
          <button class="include" data-action="save">${esc(L.t('Save'))} <kbd>Ctrl+S</kbd></button>
          <button data-action="check">${esc(L.t('Save and Check the Connections'))}</button>
          <span class="unsaved">● ${esc(L.t('Unsaved changes'))}</span>
        </div>
        ${checks}`;
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
<body class="settings">
${body}
<script nonce="${nonce}" src="${media('settings.js')}"></script>
</body>
</html>`;
    }
}
