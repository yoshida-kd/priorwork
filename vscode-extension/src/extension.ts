// extension.ts — 入口。コマンドの登録と配線だけをここに置く。
//
//   cli.ts    priorwork コマンドの呼び出しと --json の型
//   model.ts  ワークスペースの状態（CLI から読む）。状態ファイルを見張って読み直す
//   tree.ts   サイドバーの「サーベイ」
//   paper.ts  論文のページ（選別）
//   setup.ts  ワークスペース・.venv を作る、エンジンの版を確かめる
//
// 書き換えはすべて CLI が行う。ここはコマンドを組み立てて走らせ、終わったら model.refresh() するだけ。
import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';
import {
    CheckReport, CliError, DoctorReport, Entry, ExportReport, runJson, runText, SearchReport, Status, SurveySummary,
} from './cli';
import { Model } from './model';
import { doiUrl, PaperPanel } from './paper';
import { Setup } from './setup';
import { Node, SurveyTree } from './tree';

export function activate(context: vscode.ExtensionContext): void {
    const output = vscode.window.createOutputChannel('Prior Work');
    const log = (s: string): void => output.appendLine(s);
    const model = new Model(log);
    const tree = new SurveyTree(model);
    const view = vscode.window.createTreeView('priorwork.surveys', {
        treeDataProvider: tree, canSelectMany: true, showCollapseAll: true,
    });
    const setup = new Setup(context, output);
    const problems = vscode.languages.createDiagnosticCollection('priorwork');
    const paper = new PaperPanel(context, model, {
        decide: (survey, numbers, status, reason) => decide(survey, numbers, status, reason),
        fulltext: (survey, number) => fulltext(survey, number),
        openReport: (survey) => openReport(survey),
    });
    context.subscriptions.push(output, model, tree, view, paper, problems);

    // -- 共通 -----------------------------------------------------------------
    function root(): string | undefined {
        if (!model.root) {
            void vscode.window.showWarningMessage(vscode.l10n.t('Open a Prior Work workspace folder first.'));
        }
        return model.root;
    }

    function fail(e: unknown): void {
        const msg = e instanceof Error ? e.message : String(e);
        if (e instanceof CliError) {
            log(e.output);
        }
        const show = vscode.l10n.t('Show the output');
        void vscode.window.showErrorMessage(`Prior Work: ${msg}`, show).then((p) => { if (p === show) { output.show(); } });
    }

    /** 長くかかるもの（検索など）。進み具合（CLI の stderr）を通知に出し、取り消せる。 */
    function busy<T>(title: string, task: (opts: { token: vscode.CancellationToken; onOutput: (s: string) => void }) => Promise<T>): Thenable<T> {
        return vscode.window.withProgress(
            { location: vscode.ProgressLocation.Notification, title: `Prior Work: ${title}`, cancellable: true },
            (progress, token) => task({
                token,
                onOutput: (s: string) => {
                    output.append(s);
                    const last = s.trim().split(/\r?\n/).pop()?.trim();
                    if (last) {
                        progress.report({ message: last.slice(0, 120) });
                    }
                },
            }));
    }

    /** コマンドの引数（木の節・名前・無し）からサーベイを決める。無ければ選ばせる。 */
    async function surveyOf(arg: unknown): Promise<SurveySummary | undefined> {
        if (arg && typeof arg === 'object' && 'survey' in arg) {
            return (arg as { survey: SurveySummary }).survey;
        }
        const list = await model.surveys();
        if (typeof arg === 'string') {
            return list.find((s) => s.name === arg || s.name.endsWith(`_${arg}`));
        }
        return model.pickSurvey();
    }

    /** 木で選んだ論文（複数選択にも対応）。 */
    function papersOf(node: unknown, nodes: unknown): { survey: string; entries: Entry[] } | undefined {
        const all = (Array.isArray(nodes) && nodes.length ? nodes : [node]) as Node[];
        const picked = all.filter((n): n is Extract<Node, { kind: 'paper' }> => Boolean(n) && n.kind === 'paper');
        if (!picked.length) {
            return undefined;
        }
        const survey = picked[0].survey.name;
        return { survey, entries: picked.filter((n) => n.survey.name === survey).map((n) => n.entry) };
    }

    async function decide(survey: string, numbers: number[], status: Status, reason: string): Promise<boolean> {
        const verb = { included: 'include', maybe: 'maybe', excluded: 'exclude', candidate: 'reset' }[status];
        try {
            await runJson(model.root, [verb, survey, ...numbers.map(String), ...(reason ? ['--reason', reason] : [])]);
            model.refresh();
            return true;
        } catch (e) {
            fail(e);
            return false;
        }
    }

    async function askReason(survey: string, required: boolean, current = ''): Promise<string | undefined> {
        const papers = await model.papers(survey).catch((): Entry[] => []);
        const used = [...new Set(papers.filter((e) => e.reason).map((e) => e.reason))];
        if (used.length) {
            const typeNew = vscode.l10n.t('Type a new reason…');
            const items = [...used.map((r) => ({ label: r })), { label: typeNew, alwaysShow: true }];
            const picked = await vscode.window.showQuickPick(items, {
                placeHolder: required ? vscode.l10n.t('Reason for excluding') : vscode.l10n.t('Reason (optional)'),
            });
            if (!picked) {
                return undefined;
            }
            if (picked.label !== typeNew) {
                return picked.label;
            }
        }
        return vscode.window.showInputBox({
            prompt: required ? vscode.l10n.t('Reason for excluding') : vscode.l10n.t('Reason (optional)'),
            value: current,
            validateInput: (v) => (required && !v.trim() ? vscode.l10n.t('An exclusion needs a reason.') : undefined),
        });
    }

    async function fulltext(survey: string, number: number): Promise<void> {
        try {
            const info = await busy(vscode.l10n.t('getting the full text of #{0}', number),
                (o) => runJson<{ path: string; source: string }>(model.root, ['fulltext', survey, String(number)], o));
            model.refresh();
            const openIt = vscode.l10n.t('Open the text');
            const picked = await vscode.window.showInformationMessage(
                vscode.l10n.t('Prior Work: got the full text of #{0} ({1}).', number, info.source), openIt);
            if (picked === openIt && model.root) {
                const p = path.isAbsolute(info.path) ? info.path : path.join(model.root, info.path);
                await vscode.window.showTextDocument(vscode.Uri.file(p));
            }
        } catch (e) {
            fail(e);
        }
    }

    async function openReport(survey: string): Promise<void> {
        const s = (await model.surveys()).find((x) => x.name === survey);
        if (s) {
            await vscode.window.showTextDocument(vscode.Uri.file(s.report));
        }
    }

    async function afterFinding(s: SurveySummary, r: SearchReport | { new: number; hits: number }): Promise<void> {
        model.refresh();
        const screen = vscode.l10n.t('Screen now');
        const picked = await vscode.window.showInformationMessage(
            vscode.l10n.t('Prior Work: new candidates: {0} (found: {1}).', r.new, r.hits), ...(r.new ? [screen] : []));
        if (picked === screen) {
            await paper.show(s.name);
        }
    }

    let reportPanel: vscode.WebviewPanel | undefined;

    // -- コマンド ---------------------------------------------------------------
    const commands: Record<string, (...args: any[]) => unknown> = {
        'priorwork.refresh': () => model.refresh(),
        'priorwork.showOutput': () => output.show(),
        'priorwork.initWorkspace': () => setup.initWorkspace(() => model.refresh()),

        'priorwork.setupEnvironment': async () => {
            const r = root();
            if (r && await setup.createVenv(r)) {
                model.refresh();
                void vscode.window.showInformationMessage(vscode.l10n.t('Prior Work: the Python environment is ready.'));
            }
        },

        'priorwork.migrate': async () => {
            const r = root();
            if (!r) {
                return;
            }
            const go = vscode.l10n.t('Move');
            const picked = await vscode.window.showWarningMessage(vscode.l10n.t(
                'Move this lit workspace to Prior Work? .lit/ becomes .priorwork/, ./lit becomes ./priorwork, and the '
                + 'reports are regenerated. Commit your work first so that you can review the changes with git.'),
                { modal: true }, go);
            if (picked !== go) {
                return;
            }
            try {
                log(await runText(r, ['migrate']));
                model.refresh();
                void vscode.window.showInformationMessage(vscode.l10n.t(
                    'Prior Work: moved. Review the changes with git and commit them.'));
            } catch (e) {
                fail(e);
            }
        },

        'priorwork.newSurvey': async () => {
            const r = root();
            if (!r) {
                return;
            }
            const topic = await vscode.window.showInputBox({
                title: vscode.l10n.t('New survey (1/4)'),
                prompt: vscode.l10n.t('The topic (any language)'),
                placeHolder: vscode.l10n.t('e.g. Minimum wages and employment'),
                validateInput: (v) => (v.trim() ? undefined : vscode.l10n.t('Give a topic.')),
            });
            if (!topic) {
                return;
            }
            const guess = /^[\x20-\x7e]+$/.test(topic)
                ? topic.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 60) : '';
            const slug = await vscode.window.showInputBox({
                title: vscode.l10n.t('New survey (2/4)'),
                prompt: vscode.l10n.t('An English slug for the file name'),
                placeHolder: 'minimum_wage_employment',
                value: guess,
                validateInput: (v) => (/^[A-Za-z0-9][A-Za-z0-9 _-]*$/.test(v.trim()) ? undefined
                    : vscode.l10n.t('Use English letters, digits and underscores.')),
            });
            if (!slug) {
                return;
            }
            const depth = await vscode.window.showQuickPick([
                { label: 'full', description: vscode.l10n.t('A broad topic; aim for coverage (chase citations, check full texts)') },
                { label: 'quick', description: vscode.l10n.t('A narrow topic; an overview from abstracts') },
            ], { title: vscode.l10n.t('New survey (3/4)'), placeHolder: vscode.l10n.t('How deep?') });
            if (!depth) {
                return;
            }
            const question = await vscode.window.showInputBox({
                title: vscode.l10n.t('New survey (4/4)'),
                prompt: vscode.l10n.t('The research question (optional; you can set it later)'),
            });
            if (question === undefined) {
                return;
            }
            try {
                const made = await runJson<SurveySummary>(r, ['new', topic.trim(), '--slug', slug.trim(), '--depth', depth.label,
                    ...(question.trim() ? ['--question', question.trim()] : [])]);
                model.refresh();
                const search = vscode.l10n.t('Search');
                const picked = await vscode.window.showInformationMessage(
                    vscode.l10n.t('Prior Work: created {0}.', path.basename(made.report)), search);
                if (picked === search) {
                    await vscode.commands.executeCommand('priorwork.search', made.name);
                }
            } catch (e) {
                fail(e);
            }
        },

        'priorwork.editScope': async (arg?: unknown) => {
            const s = await surveyOf(arg);
            if (!s) {
                return;
            }
            const labels: Record<string, string> = {
                question: vscode.l10n.t('Research question'), years: vscode.l10n.t('Period'),
                fields: vscode.l10n.t('Fields'), inclusion: vscode.l10n.t('Inclusion criteria'),
                exclusion: vscode.l10n.t('Exclusion criteria'), depth: vscode.l10n.t('Depth'),
            };
            for (;;) {
                let d;
                try {
                    d = await model.detail(s.name);
                } catch (e) {
                    fail(e);
                    return;
                }
                const values: Record<string, string> = { ...d.scope, depth: d.depth };
                const picked = await vscode.window.showQuickPick(Object.keys(labels).map((k) => ({
                    label: labels[k], description: values[k] || vscode.l10n.t('(not set)'), key: k,
                })), { title: vscode.l10n.t('Scope of {0}', s.topic), placeHolder: vscode.l10n.t('Choose what to change') });
                if (!picked) {
                    return;
                }
                let value: string | undefined;
                if (picked.key === 'depth') {
                    value = (await vscode.window.showQuickPick(['full', 'quick'], { placeHolder: labels.depth }));
                } else {
                    value = await vscode.window.showInputBox({ title: picked.label, value: values[picked.key] });
                }
                if (value === undefined) {
                    continue;
                }
                try {
                    await runJson(model.root, ['scope', s.name, `--${picked.key}`, value]);
                    model.refresh();
                } catch (e) {
                    fail(e);
                    return;
                }
            }
        },

        'priorwork.search': async (arg?: unknown) => {
            const s = await surveyOf(arg);
            if (!s) {
                return;
            }
            const query = await vscode.window.showInputBox({
                title: vscode.l10n.t('Search for {0}', s.topic),
                prompt: vscode.l10n.t('An English query. Bulk search accepts + (and), | (or), - (not) and "phrases".'),
                placeHolder: 'minimum wage employment',
                validateInput: (v) => (v.trim() ? undefined : vscode.l10n.t('Give a query.')),
            });
            if (!query) {
                return;
            }
            const modes = [
                { label: vscode.l10n.t('Search'), description: vscode.l10n.t('by relevance, 20 results'), args: ['--limit', '20'] },
                { label: vscode.l10n.t('Bulk search'), description: vscode.l10n.t('boolean operators, most cited first, 25 results'),
                  args: ['--bulk', '--limit', '25'] },
                { label: vscode.l10n.t('SSCI journals only'), description: vscode.l10n.t('by relevance, 20 results'),
                  args: ['--ssci-only', '--limit', '20'] },
            ];
            const mode = await vscode.window.showQuickPick(modes, { placeHolder: vscode.l10n.t('How to search') });
            if (!mode) {
                return;
            }
            try {
                const r = await busy(vscode.l10n.t('searching "{0}"', query),
                    (o) => runJson<SearchReport>(model.root, ['search', query.trim(), '--into', s.name, ...mode.args], o));
                await afterFinding(s, r);
            } catch (e) {
                fail(e);
            }
        },

        'priorwork.snowball': async (arg?: unknown) => {
            const s = await surveyOf(arg);
            if (!s) {
                return;
            }
            if (!s.counts.included) {
                void vscode.window.showInformationMessage(vscode.l10n.t('Include some papers first; citations are chased from them.'));
                return;
            }
            try {
                const r = await busy(vscode.l10n.t('chasing citations (included papers: {0})', s.counts.included),
                    (o) => runJson<SearchReport>(model.root, ['snowball', s.name, '--limit', '15'], o));
                await afterFinding(s, r);
            } catch (e) {
                fail(e);
            }
        },

        'priorwork.addPaper': async (arg?: unknown) => {
            const s = await surveyOf(arg);
            if (!s) {
                return;
            }
            const ids = await vscode.window.showInputBox({
                title: vscode.l10n.t('Add papers to {0}', s.topic),
                prompt: vscode.l10n.t('DOIs (or DOI URLs, OpenAlex IDs), separated by spaces'),
                placeHolder: '10.1257/aer.91.5.1369',
            });
            const list = (ids ?? '').split(/[\s,]+/).filter(Boolean);
            if (!list.length) {
                return;
            }
            const how = await vscode.window.showQuickPick([
                { label: vscode.l10n.t('Include'), args: [] as string[] },
                { label: vscode.l10n.t('As candidates'), args: ['--candidate'] },
            ], { placeHolder: vscode.l10n.t('Include them, or add them as candidates?') });
            if (!how) {
                return;
            }
            try {
                await busy(vscode.l10n.t('adding papers ({0})', list.length),
                    (o) => runJson(model.root, ['add', s.name, ...list, ...how.args], o));
                model.refresh();
            } catch (e) {
                fail(e);
            }
        },

        'priorwork.screen': async (arg?: unknown) => {
            const s = await surveyOf(arg);
            if (s) {
                await paper.show(s.name);
            }
        },

        'priorwork.openPaper': (survey: string, number: number) => paper.show(survey, number),

        'priorwork.include': async (node: unknown, nodes: unknown) => {
            const got = papersOf(node, nodes);
            if (got) {
                await decide(got.survey, got.entries.map((e) => e.number), 'included', '');
            }
        },
        'priorwork.maybe': async (node: unknown, nodes: unknown) => {
            const got = papersOf(node, nodes);
            if (!got) {
                return;
            }
            const reason = await askReason(got.survey, false);
            if (reason !== undefined) {
                await decide(got.survey, got.entries.map((e) => e.number), 'maybe', reason.trim());
            }
        },
        'priorwork.exclude': async (node: unknown, nodes: unknown) => {
            const got = papersOf(node, nodes);
            if (!got) {
                return;
            }
            const reason = await askReason(got.survey, true);
            if (reason?.trim()) {
                await decide(got.survey, got.entries.map((e) => e.number), 'excluded', reason.trim());
            }
        },
        'priorwork.reset': async (node: unknown, nodes: unknown) => {
            const got = papersOf(node, nodes);
            if (got) {
                await decide(got.survey, got.entries.map((e) => e.number), 'candidate', '');
            }
        },

        'priorwork.fulltext': async (node: unknown) => {
            const got = papersOf(node, undefined);
            if (got) {
                await fulltext(got.survey, got.entries[0].number);
            }
        },

        'priorwork.openDoi': (node: unknown) => {
            const got = papersOf(node, undefined);
            const url = got && doiUrl(got.entries[0]);
            if (url) {
                void vscode.env.openExternal(vscode.Uri.parse(url));
            }
        },

        'priorwork.openReport': async (arg?: unknown) => {
            const s = await surveyOf(arg);
            if (s) {
                await openReport(s.name);
            }
        },

        'priorwork.exportReport': async (arg?: unknown) => {
            const s = await surveyOf(arg);
            if (!s) {
                return;
            }
            let r: ExportReport;
            try {
                r = await runJson<ExportReport>(model.root, ['export', s.name]);
            } catch (e) {
                fail(e);
                return;
            }
            if (!reportPanel) {
                reportPanel = vscode.window.createWebviewPanel('priorwork.report', s.topic, vscode.ViewColumn.Active,
                                                               { enableScripts: false });
                reportPanel.onDidDispose(() => { reportPanel = undefined; });
            }
            reportPanel.title = s.topic;
            reportPanel.webview.html = fs.readFileSync(r.path, 'utf-8');
            reportPanel.reveal();
            const browser = vscode.l10n.t('Open in the browser');
            const actions = r.issues.length ? [vscode.l10n.t('Check'), browser] : [browser];
            const picked = r.issues.length
                ? await vscode.window.showWarningMessage(vscode.l10n.t('Prior Work: exported as a draft: {0}', r.issues.join('; ')), ...actions)
                : await vscode.window.showInformationMessage(vscode.l10n.t('Prior Work: exported {0}.', path.basename(r.path)), ...actions);
            if (picked === browser) {
                void vscode.env.openExternal(vscode.Uri.file(r.path));
            } else if (picked) {
                void vscode.commands.executeCommand('priorwork.check', s.name);
            }
        },

        'priorwork.check': async (arg?: unknown) => {
            const s = await surveyOf(arg);
            if (!s) {
                return;
            }
            let r: CheckReport;
            try {
                r = await busy(vscode.l10n.t('checking {0}', s.topic), (o) => runJson<CheckReport>(model.root, ['check', s.name], o));
            } catch (e) {
                fail(e);
                return;
            }
            // 行の位置は分からないので、レポートの先頭に並べる（問題パネルで一覧できればよい）
            const sev = { ERROR: vscode.DiagnosticSeverity.Error, WARN: vscode.DiagnosticSeverity.Warning,
                          INFO: vscode.DiagnosticSeverity.Information };
            const report = vscode.Uri.file(s.report);
            problems.set(report, r.findings.map((f) => {
                const d = new vscode.Diagnostic(new vscode.Range(0, 0, 0, 0), f.message, sev[f.level]);
                d.source = 'priorwork check';
                return d;
            }));
            const show = vscode.l10n.t('Show problems');
            const text = r.errors || r.warnings
                ? vscode.l10n.t('Prior Work: {2}: errors {0}, warnings {1}.', r.errors, r.warnings, s.topic)
                : vscode.l10n.t('Prior Work: no problems in {0}.', s.topic);
            const picked = await (r.errors ? vscode.window.showWarningMessage(text, show)
                                           : vscode.window.showInformationMessage(text, show));
            if (picked === show) {
                void vscode.commands.executeCommand('workbench.actions.view.problems');
            }
        },

        'priorwork.doctor': async () => {
            let r: DoctorReport;
            try {
                r = await busy(vscode.l10n.t('diagnosing the setup'),
                    (o) => runJson<DoctorReport>(model.root, ['doctor', '--online'], o));
            } catch (e) {
                const setUp = vscode.l10n.t('Set up .venv');
                const create = vscode.l10n.t('Create a Workspace');
                const picked = await vscode.window.showErrorMessage(
                    `Prior Work: ${e instanceof Error ? e.message : String(e)}`, model.root ? setUp : create);
                if (picked === setUp) {
                    void vscode.commands.executeCommand('priorwork.setupEnvironment');
                } else if (picked === create) {
                    void vscode.commands.executeCommand('priorwork.initWorkspace');
                }
                return;
            }
            const icon = { ok: '✅', warn: '⚠️', ng: '❌' };
            output.appendLine(`\n== priorwork doctor (${r.version}, ${r.root})`);
            for (const c of r.checks) {
                output.appendLine(`${icon[c.level]} ${c.name}: ${c.message}`);
            }
            output.show(true);
            const text = vscode.l10n.t('Prior Work: problems {0}, warnings {1} (details in the output).', r.ng, r.warn);
            void (r.ng ? vscode.window.showWarningMessage(text) : vscode.window.showInformationMessage(text));
        },

        'priorwork.sync': async () => {
            const r = root();
            if (!r) {
                return;
            }
            try {
                log(await runText(r, ['sync']));
                model.refresh();
                void vscode.window.showInformationMessage(vscode.l10n.t('Prior Work: AGENTS.md and the skills are up to date.'));
            } catch (e) {
                fail(e);
            }
        },

        'priorwork.upgrade': async (version?: string) => {
            const r = root();
            if (!r) {
                return;
            }
            try {
                const out = await busy(vscode.l10n.t('updating the engine'),
                    (o) => runText(r, ['upgrade', ...(typeof version === 'string' ? ['--to', version] : [])], o));
                log(out);
                model.refresh();
                void vscode.window.showInformationMessage(vscode.l10n.t(
                    'Prior Work: the engine is updated. Review the changes with git and commit them.'));
            } catch (e) {
                fail(e);
            }
        },

        'priorwork.openEnv': async () => {
            const r = root();
            if (!r) {
                return;
            }
            const env = path.join(r, '.env');
            const example = path.join(r, '.env.example');
            if (!fs.existsSync(env) && fs.existsSync(example)) {
                fs.copyFileSync(example, env);
            }
            if (!fs.existsSync(env)) {
                fs.writeFileSync(env, '');
            }
            await vscode.window.showTextDocument(vscode.Uri.file(env));
        },

        'priorwork.runStep': async (s: SurveySummary, step: { id: string; args: string[] }) => {
            switch (step.id) {
                case 'scope': return vscode.commands.executeCommand('priorwork.editScope', s.name);
                case 'search': return vscode.commands.executeCommand('priorwork.search', s.name);
                case 'screen': return paper.show(s.name);
                case 'snowball': return vscode.commands.executeCommand('priorwork.snowball', s.name);
                case 'check': return vscode.commands.executeCommand('priorwork.check', s.name);
                case 'export': return vscode.commands.executeCommand('priorwork.exportReport', s.name);
                case 'fill': {
                    const n = Number(step.args[2]);
                    const get = vscode.l10n.t('Get the full text of #{0}', n);
                    const picked = await vscode.window.showInformationMessage(vscode.l10n.t(
                        'Ask your agent to fill in the paper cards (skill /survey-extract). '
                        + 'You can get the full texts here first.'), get);
                    if (picked === get) {
                        await fulltext(s.name, n);
                    }
                    return;
                }
                default: {
                    const term = vscode.window.createTerminal({ name: 'Prior Work', cwd: model.root });
                    term.show();
                    term.sendText(['priorwork', ...step.args].map((a) => (/[\s"'<>|&;]/.test(a) ? `"${a}"` : a)).join(' '));
                    return;
                }
            }
        },
    };
    for (const [id, fn] of Object.entries(commands)) {
        context.subscriptions.push(vscode.commands.registerCommand(id, fn));
    }

    // 開いたときに一度、エンジンがあるか・版が合っているかを見る（旧名 lit のワークスペースは移行が先）
    void (async () => {
        const ws = await model.workspace();
        if (model.root && (ws?.workspace || !ws)) {
            await setup.checkEngine(model.root, () => model.refresh());
        }
    })();
}

export function deactivate(): void {
    // 何もしない（子プロセスは各コマンドが終わらせる）
}
