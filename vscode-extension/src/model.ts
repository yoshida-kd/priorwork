// model.ts — ワークスペースの状態（CLI から読んだもの）を持ち、変わったら知らせる。
//
// サイドバー（tree.ts）と論文のページ（paper.ts）は、ここを通して読む。
// 状態ファイル（.priorwork/surveys/*.json）を見張り、エージェントがターミナルから
// 採否を変えたり検索したりしても、サイドバーが追随する。
import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';
import { CliError, Entry, runJson, SurveyDetail, SurveySummary, WorkspaceStatus } from './cli';

/** 開いているフォルダのうち、ワークスペース（.priorwork/ があるもの）。 */
export function findRoot(): string | undefined {
    for (const f of vscode.workspace.workspaceFolders ?? []) {
        const p = f.uri.fsPath;
        if (fs.existsSync(path.join(p, '.priorwork'))) {
            return p;
        }
    }
    return undefined;
}

export class Model implements vscode.Disposable {
    private readonly changed = new vscode.EventEmitter<void>();
    readonly onDidChange = this.changed.event;
    private readonly subs: vscode.Disposable[] = [];
    private status?: WorkspaceStatus;
    private statusError?: string;
    private loading?: Promise<void>;
    private readonly entries = new Map<string, Entry[]>();
    private readonly details = new Map<string, SurveyDetail>();
    private timer?: NodeJS.Timeout;
    root: string | undefined;

    constructor(private readonly log: (s: string) => void) {
        this.root = findRoot();
        const watcher = vscode.workspace.createFileSystemWatcher('**/.priorwork/{surveys/*.json,config.json}');
        // カードはレポートに書かれるので、エージェントがレポートを直したときも読み直す
        const reports = vscode.workspace.createFileSystemWatcher('**/reports/*.md', true, false, true);
        const soon = (): void => this.refreshSoon();
        this.subs.push(watcher, watcher.onDidChange(soon), watcher.onDidCreate(soon), watcher.onDidDelete(soon),
            reports, reports.onDidChange(soon), vscode.workspace.onDidChangeWorkspaceFolders(() => this.refresh()));
    }

    dispose(): void {
        for (const s of this.subs) {
            s.dispose();
        }
        this.changed.dispose();
    }

    /** 状態ファイルは1回の操作で何度か書かれるので、まとめて読み直す。 */
    refreshSoon(): void {
        if (this.timer) {
            clearTimeout(this.timer);
        }
        this.timer = setTimeout(() => this.refresh(), 400);
    }

    refresh(): void {
        this.root = findRoot();
        this.status = undefined;
        this.statusError = undefined;
        this.loading = undefined;
        this.entries.clear();
        this.details.clear();
        this.changed.fire();
    }

    /** ワークスペースの状態。CLI が無い・壊れているときは undefined（理由は lastError）。 */
    async workspace(): Promise<WorkspaceStatus | undefined> {
        if (!this.root) {
            await this.setContext(false, false);
            return undefined;
        }
        if (!this.status && !this.statusError) {
            this.loading ??= this.load();
            await this.loading;
        }
        return this.status;
    }

    get lastError(): string | undefined {
        return this.statusError;
    }

    private async load(): Promise<void> {
        try {
            this.status = await runJson<WorkspaceStatus>(this.root, ['status'], { timeoutMs: 60000 });
        } catch (e) {
            this.statusError = e instanceof Error ? e.message : String(e);
            this.log(`[status] ${this.statusError}${e instanceof CliError ? `\n${e.output}` : ''}`);
        }
        const s = this.status;
        await this.setContext(Boolean(s?.workspace), Boolean(s?.surveys.length));
    }

    private async setContext(hasWorkspace: boolean, hasSurveys: boolean): Promise<void> {
        await vscode.commands.executeCommand('setContext', 'priorwork.hasWorkspace', hasWorkspace);
        await vscode.commands.executeCommand('setContext', 'priorwork.hasSurveys', hasSurveys);
    }

    async surveys(): Promise<SurveySummary[]> {
        return (await this.workspace())?.surveys ?? [];
    }

    async papers(survey: string): Promise<Entry[]> {
        let got = this.entries.get(survey);
        if (!got) {
            got = await runJson<Entry[]>(this.root, ['list', survey], { timeoutMs: 60000 });
            this.entries.set(survey, got);
        }
        return got;
    }

    async detail(survey: string): Promise<SurveyDetail> {
        let got = this.details.get(survey);
        if (!got) {
            got = await runJson<SurveyDetail>(this.root, ['status', survey], { timeoutMs: 60000 });
            this.details.set(survey, got);
        }
        return got;
    }

    /** サーベイを1つ選ばせる（1つしか無ければそれ）。 */
    async pickSurvey(placeHolder?: string): Promise<SurveySummary | undefined> {
        const list = await this.surveys();
        if (list.length <= 1) {
            return list[0];
        }
        const picked = await vscode.window.showQuickPick(
            list.map((s) => ({ label: s.topic, description: s.name, s })),
            { placeHolder: placeHolder ?? vscode.l10n.t('Which survey?') });
        return picked?.s;
    }
}
