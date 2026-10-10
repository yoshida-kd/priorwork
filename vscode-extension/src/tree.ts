// tree.ts — サイドバーの「サーベイ」。サーベイ → 次にやること・採否ごとの論文。
//
// 中身はぜんぶ CLI から取る（model.ts 経由）: 一覧 `priorwork status --json`、
// 次にやること `priorwork status SURVEY --json`、論文 `priorwork list SURVEY --json`。
import * as vscode from 'vscode';
import { Entry, NextStep, Status, SurveySummary } from './cli';
import { Model } from './model';

export type Node =
    | { kind: 'survey'; survey: SurveySummary }
    | { kind: 'steps'; survey: SurveySummary }
    | { kind: 'step'; survey: SurveySummary; step: NextStep }
    | { kind: 'group'; survey: SurveySummary; status: Status; count: number }
    | { kind: 'paper'; survey: SurveySummary; entry: Entry }
    | { kind: 'message'; label: string; icon?: string; command?: vscode.Command };

const GROUP_ORDER: Status[] = ['candidate', 'maybe', 'included', 'excluded'];

export function groupLabel(status: Status): string {
    switch (status) {
        case 'candidate': return vscode.l10n.t('To screen');
        case 'maybe': return vscode.l10n.t('Maybe');
        case 'included': return vscode.l10n.t('Included');
        case 'excluded': return vscode.l10n.t('Excluded');
    }
}

export function statusIcon(status: Status): vscode.ThemeIcon {
    switch (status) {
        case 'candidate': return new vscode.ThemeIcon('circle-large-outline');
        case 'maybe': return new vscode.ThemeIcon('question', new vscode.ThemeColor('list.warningForeground'));
        case 'included': return new vscode.ThemeIcon('pass-filled', new vscode.ThemeColor('testing.iconPassed'));
        case 'excluded': return new vscode.ThemeIcon('circle-slash', new vscode.ThemeColor('disabledForeground'));
    }
}

const STEP_ICON: Record<string, string> = {
    scope: 'settings', search: 'search', screen: 'checklist', snowball: 'references', zotero: 'library',
    fill: 'edit', draft: 'book', check: 'pass', export: 'open-preview',
};

/** 'Card & Krueger (1994)' の形。 */
export function authorYear(e: Entry): string {
    const names = e.record.authors.map((a) => a.replace(/,/g, ' ').trim().split(/\s+/).pop() ?? '').filter(Boolean);
    const who = names.length === 0 ? 'Unknown'
        : names.length === 1 ? names[0]
            : names.length === 2 ? `${names[0]} & ${names[1]}` : `${names[0]} et al.`;
    return `${who} (${e.record.year ?? 'n.d.'})`;
}

export function surveyDescription(s: SurveySummary): string {
    const c = s.counts;
    const parts = [];
    if (c.candidate + c.maybe) {
        parts.push(vscode.l10n.t('{0} to screen', c.candidate + c.maybe));
    }
    parts.push(vscode.l10n.t('{0} included', c.included));
    return parts.join(' · ');
}

export class SurveyTree implements vscode.TreeDataProvider<Node>, vscode.Disposable {
    private readonly changed = new vscode.EventEmitter<Node | undefined>();
    readonly onDidChangeTreeData = this.changed.event;
    private readonly sub: vscode.Disposable;

    constructor(private readonly model: Model) {
        this.sub = model.onDidChange(() => this.changed.fire(undefined));
    }

    dispose(): void {
        this.sub.dispose();
        this.changed.dispose();
    }

    async getChildren(node?: Node): Promise<Node[]> {
        if (!node) {
            const ws = await this.model.workspace();
            if (!ws) {
                const err = this.model.lastError;
                if (!this.model.root || !err) {
                    return [];                         // viewsWelcome が出る
                }
                return [
                    { kind: 'message', label: err, icon: 'error' },
                    { kind: 'message', label: vscode.l10n.t('Set up the Python environment (.venv)'), icon: 'package',
                      command: { command: 'priorwork.setupEnvironment', title: '' } },
                    { kind: 'message', label: vscode.l10n.t('Show the output'), icon: 'output',
                      command: { command: 'priorwork.showOutput', title: '' } },
                ];
            }
            const rows: Node[] = [];
            if (ws.git && !ws.git.remote) {   // 古い CLI は git を返さない
                rows.push({ kind: 'message', label: vscode.l10n.t('Not on GitHub yet — publish it as a private repository'),
                            icon: 'github', command: { command: 'priorwork.publish', title: '' } });
            }
            if (ws.sync) {
                rows.push({ kind: 'message', label: vscode.l10n.t('AGENTS.md and the skills are out of date — update them'),
                            icon: 'warning', command: { command: 'priorwork.sync', title: '' } });
            }
            return [...rows, ...ws.surveys.map((s): Node => ({ kind: 'survey', survey: s }))];
        }
        if (node.kind === 'survey') {
            const rows: Node[] = [{ kind: 'steps', survey: node.survey }];
            for (const status of GROUP_ORDER) {
                const count = node.survey.counts[status];
                if (count) {
                    rows.push({ kind: 'group', survey: node.survey, status, count });
                }
            }
            return rows;
        }
        if (node.kind === 'steps') {
            try {
                const d = await this.model.detail(node.survey.name);
                return d.next.map((step): Node => ({ kind: 'step', survey: node.survey, step }));
            } catch (e) {
                return [{ kind: 'message', label: e instanceof Error ? e.message : String(e), icon: 'error' }];
            }
        }
        if (node.kind === 'group') {
            try {
                const papers = await this.model.papers(node.survey.name);
                return papers.filter((e) => e.status === node.status)
                    .map((entry): Node => ({ kind: 'paper', survey: node.survey, entry }));
            } catch (e) {
                return [{ kind: 'message', label: e instanceof Error ? e.message : String(e), icon: 'error' }];
            }
        }
        return [];
    }

    getTreeItem(node: Node): vscode.TreeItem {
        const C = vscode.TreeItemCollapsibleState;
        switch (node.kind) {
            case 'survey': {
                const it = new vscode.TreeItem(node.survey.topic, C.Expanded);
                it.id = `survey:${node.survey.name}`;
                it.description = surveyDescription(node.survey);
                it.iconPath = new vscode.ThemeIcon('book');
                it.contextValue = 'priorwork.survey';
                it.tooltip = new vscode.MarkdownString(
                    `**${node.survey.topic}**\n\n${node.survey.name} · ${node.survey.depth} · ${node.survey.lang}\n\n`
                    + vscode.l10n.t('searches: {0}', node.survey.searches));
                return it;
            }
            case 'steps': {
                const it = new vscode.TreeItem(vscode.l10n.t('Next steps'), C.Collapsed);
                it.id = `steps:${node.survey.name}`;
                it.iconPath = new vscode.ThemeIcon('list-ordered');
                return it;
            }
            case 'step': {
                const it = new vscode.TreeItem(node.step.text, C.None);
                it.iconPath = new vscode.ThemeIcon(STEP_ICON[node.step.id] ?? 'arrow-right');
                it.tooltip = `priorwork ${node.step.args.join(' ')}`;
                it.command = { command: 'priorwork.runStep', title: node.step.text, arguments: [node.survey, node.step] };
                return it;
            }
            case 'group': {
                const it = new vscode.TreeItem(groupLabel(node.status),
                    node.status === 'candidate' ? C.Expanded : C.Collapsed);
                it.id = `group:${node.survey.name}:${node.status}`;
                it.description = String(node.count);
                it.iconPath = statusIcon(node.status);
                return it;
            }
            case 'paper': {
                const e = node.entry;
                const it = new vscode.TreeItem(`#${e.number} ${authorYear(e)}`, C.None);
                it.id = `paper:${node.survey.name}:${e.key}`;
                it.description = (e.record.warnings.length ? '⚠️ ' : '') + e.record.title;
                it.iconPath = statusIcon(e.status);
                it.contextValue = `priorwork.paper.${e.status}`;
                const md = new vscode.MarkdownString(undefined, true);
                md.appendMarkdown(`**${escapeMd(e.record.title)}**\n\n`);
                md.appendMarkdown(`${escapeMd(e.record.authors.slice(0, 6).join(', '))}\n\n`);
                md.appendMarkdown(`*${escapeMd(e.record.journal_name || 'N/A')}* (${e.record.year ?? 'n.d.'}) · `
                    + vscode.l10n.t('cited by {0}', e.record.citation_count) + '\n\n');
                for (const w of e.record.warnings) {
                    md.appendMarkdown(`⚠️ ${escapeMd(w)}\n\n`);
                }
                if (e.reason) {
                    md.appendMarkdown(`${vscode.l10n.t('Reason')}: ${escapeMd(e.reason)}\n\n`);
                }
                it.tooltip = md;
                it.command = { command: 'priorwork.openPaper', title: '', arguments: [node.survey.name, e.number] };
                return it;
            }
            case 'message': {
                const it = new vscode.TreeItem(node.label, C.None);
                it.iconPath = node.icon ? new vscode.ThemeIcon(node.icon) : undefined;
                it.command = node.command;
                it.tooltip = node.label;
                return it;
            }
        }
    }
}

function escapeMd(s: string): string {
    return s.replace(/[\\`*_{}[\]()#+\-.!|<>]/g, '\\$&');
}
