// extension.ts — 入口。コマンドの登録と配線だけをここに置く。
//
//   cli.ts    priorwork コマンドの呼び出しと --json の型
//   model.ts  ワークスペースの状態（CLI から読む）。状態ファイルを見張って読み直す
//   tree.ts   サイドバーの「サーベイ」
//   paper.ts  論文のページ（選別・カードの記入）
//   settings.ts  設定のページ（API キー・Zotero・SSCI リスト）
//   setup.ts  ワークスペース・.venv を作る、エンジンの版を確かめる
//
// 書き換えはすべて CLI が行う。ここはコマンドを組み立てて走らせ、終わったら model.refresh() するだけ。
import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';
import {
    CheckReport, CliError, DoctorReport, Entry, ExportReport, runJson, runText, SearchReport, Status, SurveySummary,
    ZoteroCollections, ZoteroReport,
} from './cli';
import { Model } from './model';
import { doiUrl, PaperPanel } from './paper';
import { SettingsPanel } from './settings';
import { Setup } from './setup';
import { Node, SurveyTree } from './tree';

/** エージェントに頼める仕事（文面は askAgent）。 */
type AgentTask = 'survey' | 'search' | 'screen' | 'snowball' | 'fill' | 'write' | 'check';

/** エージェントのチャットを開くコマンド（入っているものだけ出す）。 */
const AGENT_CHATS: { command: string; label: string }[] = [
    { command: 'claude-vscode.sidebar.open', label: 'Claude Code' },
    { command: 'antigravity.panel.focus', label: 'Antigravity' },
    { command: 'workbench.action.chat.open', label: 'Copilot Chat' },
];

export function activate(context: vscode.ExtensionContext): void {
    const output = vscode.window.createOutputChannel('Priorwork');
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
        saveCard: (survey, number, values) => saveCard(survey, number, values),
        askAgent: (survey, number) => vscode.commands.executeCommand('priorwork.askAgent',
                                                                     { name: survey, task: 'fill', numbers: [number] }),
        openReport: (survey) => openReport(survey),
    });
    const settings = new SettingsPanel(context, model, { busy: (t, task) => busy(t, task), fail: (e) => fail(e) });
    context.subscriptions.push(output, model, tree, view, paper, settings, problems);

    // -- 共通 -----------------------------------------------------------------
    function root(): string | undefined {
        if (!model.root) {
            void vscode.window.showWarningMessage(vscode.l10n.t('Open a Priorwork workspace folder first.'));
        }
        return model.root;
    }

    function fail(e: unknown): void {
        const msg = e instanceof Error ? e.message : String(e);
        if (e instanceof CliError) {
            log(e.output);
        }
        const show = vscode.l10n.t('Show the output');
        void vscode.window.showErrorMessage(`Priorwork: ${msg}`, show).then((p) => { if (p === show) { output.show(); } });
    }

    /** 長くかかるもの（検索など）。進み具合（CLI の stderr）を通知に出し、取り消せる。 */
    function busy<T>(title: string, task: (opts: { token: vscode.CancellationToken; onOutput: (s: string) => void }) => Promise<T>): Thenable<T> {
        return vscode.window.withProgress(
            { location: vscode.ProgressLocation.Notification, title: `Priorwork: ${title}`, cancellable: true },
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

    async function saveCard(survey: string, number: number, values: Record<string, string>): Promise<boolean> {
        const pairs = Object.entries(values).map(([k, v]) => `${k}=${v}`);
        try {
            await runJson(model.root, ['card', survey, String(number), '--set', ...pairs]);
            model.refresh();
            vscode.window.setStatusBarMessage(vscode.l10n.t('Priorwork: saved the card of #{0}.', number), 4000);
            return true;
        } catch (e) {
            fail(e);
            return false;
        }
    }

    /**
     * エージェントに頼む文面をクリップボードに写す。API は呼ばない（利用者が自分のエージェントのチャットに貼る）。
     * 文面は普通の言葉で書く（スキル名を打たなくても、エージェントが AGENTS.md とスキルの説明から工程を選ぶ）。
     */
    async function askAgent(s: SurveySummary, task: AgentTask, numbers: number[] = []): Promise<void> {
        const L = vscode.l10n;
        const which = numbers.length ? numbers.map((n) => `#${n}`).join(', ') : L.t('the unfilled ones');
        const text = {
            survey: L.t('Carry on with the survey "{0}" ({1}) with Priorwork, to the end: search, screen, chase citations, fill in the cards, write the text, check and export. Decide on your own with reasons, and report at the end.', s.topic, s.name),
            search: L.t('Search more for the survey "{0}" ({1}) with Priorwork, from subtopics not searched yet, then screen the new candidates.', s.topic, s.name),
            screen: L.t('Screen the candidates of the survey "{0}" ({1}) with Priorwork against its criteria, recording a reason for each decision.', s.topic, s.name),
            snowball: L.t('Chase the citations of the included papers of the survey "{0}" ({1}) with Priorwork and screen the new candidates.', s.topic, s.name),
            fill: L.t('Fill in the paper cards of the survey "{0}" ({1}) with Priorwork: {2}. Write only what the abstract or the full text says, and update the evidence level.', s.topic, s.name, which),
            write: L.t('Write the text of the report of the survey "{0}" ({1}): the background (section 1) and sections 4 to 7, based on the paper cards. Cite only papers registered in the survey, and run ./priorwork check at the end.', s.topic, s.name),
            check: L.t('Check the survey "{0}" ({1}) with Priorwork, fix what it finds and export the report.', s.topic, s.name),
        }[task];
        await copyForAgent(text);
    }

    /** 依頼文をコピーし、入っているエージェントのチャットを開けるようにする。 */
    async function copyForAgent(text: string): Promise<void> {
        const L = vscode.l10n;
        await vscode.env.clipboard.writeText(text);
        const have = new Set(await vscode.commands.getCommands(true));
        const chats = AGENT_CHATS.filter((c) => have.has(c.command));
        const picked = await vscode.window.showInformationMessage(
            L.t('Copied a request for your agent. Paste it into the chat of your agent (Claude Code, Antigravity, …).'),
            ...chats.map((c) => L.t('Open {0}', c.label)));
        const chat = chats.find((c) => picked === L.t('Open {0}', c.label));
        if (chat) {
            await vscode.commands.executeCommand(chat.command);
        }
    }

    /** Zotero に無い採用論文。DOI をまとめてコピーし（Zotero の「識別子でアイテムを追加」に貼れる）、読み直す。 */
    async function zoteroMissing(s: SurveySummary): Promise<void> {
        const L = vscode.l10n;
        const reload = L.t('Reload from Zotero');
        const link = L.t('Link a collection…');
        let collection = '';
        const missing = async (): Promise<Entry[]> => {
            const d = await model.detail(s.name);
            collection = d.zotero_collection?.name ?? '';
            const numbers = new Set(d.zotero_missing);
            return (await model.papers(s.name)).filter((e) => numbers.has(e.number));
        };
        let entries = await missing();
        for (;;) {
            if (!entries.length) {
                void vscode.window.showInformationMessage(L.t('Priorwork: all included papers are in Zotero.'));
                return;
            }
            const dois = entries.filter((e) => e.record.doi).map((e) => e.record.doi as string);
            const noDoi = entries.filter((e) => !e.record.doi).map((e) => `#${e.number}`);
            const copy = L.t('Copy the DOIs');
            const picked = await vscode.window.showInformationMessage(
                (collection
                    ? L.t('{0} included papers are not in the Zotero collection "{1}": {2}.', entries.length, collection,
                          entries.map((e) => `#${e.number}`).join(', '))
                    : L.t('{0} included papers are not in Zotero: {1}.', entries.length, entries.map((e) => `#${e.number}`).join(', ')))
                + ' ' + L.t('Copy their DOIs, paste them into Zotero\'s "Add Item by Identifier" (the magic wand), then reload.')
                + (collection ? ' ' + L.t('Select the collection in Zotero first, so that they go into it.') : '')
                + (noDoi.length ? ' ' + L.t('Add these by hand (no DOI): {0}.', noDoi.join(', ')) : ''),
                ...(dois.length ? [copy] : []), reload, ...(collection ? [] : [link]));
            if (picked === link) {
                return zoteroCollection(s);
            }
            if (picked === copy) {
                await vscode.env.clipboard.writeText(dois.join('\n'));
                const again = await vscode.window.showInformationMessage(
                    L.t('Copied {0} DOIs. In Zotero, click the magic wand, paste them and press Enter.', dois.length), reload);
                if (again !== reload) {
                    return;
                }
            } else if (picked !== reload) {
                return;
            }
            try {
                await busy(L.t('reloading the Zotero library'), (o) => runText(model.root, ['zotero', s.name, '--refresh'], o));
            } catch (e) {
                fail(e);
                return;
            }
            model.refresh();
            entries = await missing();
        }
    }

    /** Zotero のコレクションをサーベイに結び付ける。Zotero には書き込まない（コレクションを作るのはユーザー）。 */
    async function zoteroCollection(s: SurveySummary): Promise<void> {
        const L = vscode.l10n;
        let list: ZoteroCollections;
        try {
            list = await busy(L.t('reading the Zotero collections'),
                (o) => runJson<ZoteroCollections>(model.root, ['zotero', '--collections', '--json'], o));
        } catch (e) {
            fail(e);
            return;
        }
        const current = (await model.detail(s.name).catch(() => undefined))?.zotero_collection;
        const none = { label: L.t('(none)'), description: L.t('do not link a collection'), key: '' };
        const picked = await vscode.window.showQuickPick([
            ...list.collections.map((c) => ({
                label: c.path, description: L.t('{0} items', c.items) + (current?.key === c.key ? ' ✓' : ''), key: c.key,
            })),
            ...(current ? [none] : []),
        ], {
            title: L.t('Zotero collection for {0}', s.topic),
            placeHolder: list.collections.length ? L.t('Make the collection in Zotero first if it is not here')
                : L.t('The Zotero library has no collections. Make one in Zotero first.'),
        });
        if (!picked) {
            return;
        }
        let r: ZoteroReport;
        try {
            r = await runJson<ZoteroReport>(model.root, ['zotero', s.name, '--collection', picked.key, '--json']);
        } catch (e) {
            fail(e);
            return;
        }
        model.refresh();
        if (!r.collection) {
            void vscode.window.showInformationMessage(L.t('Priorwork: unlinked the Zotero collection.'));
            return;
        }
        const add = L.t('Register them');
        const choice = await vscode.window.showInformationMessage(
            L.t('Priorwork: linked the Zotero collection "{0}". Included papers missing from it: {1}.', r.collection.name,
                r.missing_dois.length)
            + (r.to_import ? ' ' + L.t('{0} papers in the collection are not in the survey yet.', r.to_import) : ''),
            ...(r.to_import ? [add] : []));
        if (choice === add) {
            await zoteroImport(s);
        }
    }

    async function zoteroImport(s: SurveySummary): Promise<void> {
        const L = vscode.l10n;
        try {
            const r = await busy(L.t('registering the papers of the Zotero collection'),
                (o) => runJson<ZoteroReport>(model.root, ['zotero', s.name, '--import', '--json'], o));
            model.refresh();
            void vscode.window.showInformationMessage(
                L.t('Priorwork: registered {0} papers from the Zotero collection as candidates.', r.imported.filter((a) => a.new).length)
                + (r.no_doi.length ? ' ' + L.t('Not registered (no DOI or not found): {0}.', r.no_doi.join('; ')) : ''));
        } catch (e) {
            fail(e);
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
                vscode.l10n.t('Priorwork: got the full text of #{0} ({1}).', number, info.source), openIt);
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
            vscode.l10n.t('Priorwork: new candidates: {0} (found: {1}).', r.new, r.hits), ...(r.new ? [screen] : []));
        if (picked === screen) {
            await paper.show(s.name);
        }
    }

    let reportPanel: vscode.WebviewPanel | undefined;
    let reportFile: string | undefined;
    let exporting = false;   // 自分で書き出している間は、HTML の変更を通知しない

    /**
     * 読むための版（HTML）をエディターの中で見せる。SSH でつないだサーバーでも見られる
     * （Live Preview などはサーバーの上のファイルをブラウザに出せないことがある）。
     */
    function showHtml(file: string, title: string): void {
        if (!reportPanel) {
            reportPanel = vscode.window.createWebviewPanel('priorwork.report', title, vscode.ViewColumn.Active,
                                                           { enableScripts: false });
            reportPanel.onDidDispose(() => { reportPanel = undefined; reportFile = undefined; });
        }
        reportPanel.title = title;
        reportPanel.webview.html = fs.readFileSync(file, 'utf-8');
        reportFile = file;
        reportPanel.reveal();
    }

    async function titleOf(file: string): Promise<string> {
        const stem = path.basename(file, '.html');
        const s = (await model.surveys().catch((): SurveySummary[] => [])).find((x) => x.name === stem);
        return s?.topic ?? stem;
    }

    // エージェントが `priorwork export` で HTML を書き出したら、見られるように知らせる（開いていれば読み直す）
    const htmlWatcher = vscode.workspace.createFileSystemWatcher('**/reports/*.html');
    const htmlTimers = new Map<string, ReturnType<typeof setTimeout>>();
    const onHtml = (uri: vscode.Uri): void => {
        if (exporting) {
            return;
        }
        clearTimeout(htmlTimers.get(uri.fsPath));
        htmlTimers.set(uri.fsPath, setTimeout(async () => {
            htmlTimers.delete(uri.fsPath);
            if (!fs.existsSync(uri.fsPath)) {
                return;
            }
            if (reportPanel && reportFile === uri.fsPath) {
                reportPanel.webview.html = fs.readFileSync(uri.fsPath, 'utf-8');
                return;
            }
            const view = vscode.l10n.t('View');
            const picked = await vscode.window.showInformationMessage(
                vscode.l10n.t('Priorwork: the report {0} was written.', path.basename(uri.fsPath)), view);
            if (picked === view) {
                showHtml(uri.fsPath, await titleOf(uri.fsPath));
            }
        }, 1500));
    };
    htmlWatcher.onDidCreate(onHtml);
    htmlWatcher.onDidChange(onHtml);
    context.subscriptions.push(htmlWatcher);

    // -- コマンド ---------------------------------------------------------------
    const commands: Record<string, (...args: any[]) => unknown> = {
        'priorwork.refresh': () => model.refresh(),
        'priorwork.showOutput': () => output.show(),
        'priorwork.initWorkspace': () => setup.initWorkspace(() => model.refresh()),

        'priorwork.setupEnvironment': async () => {
            const r = root();
            if (r && await setup.createVenv(r)) {
                model.refresh();
                void vscode.window.showInformationMessage(vscode.l10n.t('Priorwork: the Python environment is ready.'));
            }
        },

        'priorwork.askAgent': async (arg?: unknown) => {
            // 木のサーベイ・サーベイ名、または { name, task, numbers }（論文のページ・次にやることから）
            const preset = arg && typeof arg === 'object' && 'task' in arg
                ? arg as { name: string; task: AgentTask; numbers?: number[] } : undefined;
            const s = await surveyOf(preset ? preset.name : arg);
            if (!s) {
                return;
            }
            let task = preset?.task;
            if (!task) {
                const L = vscode.l10n;
                const items: { label: string; description: string; task: AgentTask }[] = [
                    { label: L.t('Carry on to the end'), description: L.t('the whole survey, without stopping'), task: 'survey' },
                    { label: L.t('Search more'), description: L.t('more queries, then screening'), task: 'search' },
                    { label: L.t('Screen the candidates'), description: L.t('decisions with reasons'), task: 'screen' },
                    { label: L.t('Chase citations'), description: L.t('snowball, then screening'), task: 'snowball' },
                    { label: L.t('Fill in the paper cards'), description: L.t('from the abstracts or full texts'), task: 'fill' },
                    { label: L.t('Write the text of the report'), description: L.t('sections 1 and 4–7'), task: 'write' },
                    { label: L.t('Check and fix'), description: L.t('then export the report'), task: 'check' },
                ];
                task = (await vscode.window.showQuickPick(items, { placeHolder: L.t('What should your agent do?') }))?.task;
                if (!task) {
                    return;
                }
            }
            let numbers = preset?.numbers ?? [];
            if (task === 'fill' && !numbers.length) {
                numbers = (await model.detail(s.name).catch(() => undefined))?.unfilled ?? [];
            }
            await askAgent(s, task, numbers);
        },

        'priorwork.newSurvey': async () => {
            const r = root();
            if (!r) {
                return;
            }
            const L = vscode.l10n;
            const how = await vscode.window.showQuickPick([
                { label: L.t('Ask your agent to do it'), detail: L.t('Recommended. Give the topic; the agent sets the scope, searches, screens, fills in the cards and writes the report.'), agent: true },
                { label: L.t('Set it up myself'), detail: L.t('Give the topic, slug, depth and question, then search and screen in the sidebar.'), agent: false },
            ], { title: L.t('New survey'), placeHolder: L.t('How do you want to make it?') });
            if (!how) {
                return;
            }
            if (how.agent) {
                const about = await vscode.window.showInputBox({
                    title: L.t('New survey'),
                    prompt: L.t('The topic, in your own words (any language). Add a research question or criteria if you have them.'),
                    placeHolder: L.t('e.g. Minimum wages and employment'),
                    validateInput: (v) => (v.trim() ? undefined : L.t('Give a topic.')),
                });
                if (!about) {
                    return;
                }
                const deep = await vscode.window.showQuickPick([
                    { label: 'full', description: L.t('A broad topic; aim for coverage (chase citations, check full texts)') },
                    { label: 'quick', description: L.t('A narrow topic; an overview from abstracts') },
                    { label: L.t('Let the agent decide'), description: '' },
                ], { title: L.t('New survey'), placeHolder: L.t('How deep?') });
                if (!deep) {
                    return;
                }
                const text = deep.label === 'full' || deep.label === 'quick'
                    ? L.t('Make a literature survey with Priorwork (depth: {0}) on: {1}. Set the scope yourself, then search, screen, chase citations, fill in the cards, write the text, check and export without stopping, and report at the end.', deep.label, about.trim())
                    : L.t('Make a literature survey with Priorwork on: {0}. Choose the depth and set the scope yourself, then search, screen, chase citations, fill in the cards, write the text, check and export without stopping, and report at the end.', about.trim());
                await copyForAgent(text);
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
                    vscode.l10n.t('Priorwork: created {0}.', path.basename(made.report)), search);
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
            exporting = true;
            try {
                r = await runJson<ExportReport>(model.root, ['export', s.name]);
            } catch (e) {
                fail(e);
                return;
            } finally {
                setTimeout(() => { exporting = false; }, 2000);
            }
            showHtml(r.path, s.topic);
            const browser = vscode.l10n.t('Open in the browser');
            const actions = r.issues.length ? [vscode.l10n.t('Check'), browser] : [browser];
            const picked = r.issues.length
                ? await vscode.window.showWarningMessage(vscode.l10n.t('Priorwork: exported as a draft: {0}', r.issues.join('; ')), ...actions)
                : await vscode.window.showInformationMessage(vscode.l10n.t('Priorwork: exported {0}.', path.basename(r.path)), ...actions);
            if (picked === browser) {
                void vscode.env.openExternal(vscode.Uri.file(r.path));
            } else if (picked) {
                void vscode.commands.executeCommand('priorwork.check', s.name);
            }
        },

        'priorwork.zoteroCollection': async (arg?: unknown) => {
            const s = await surveyOf(arg);
            if (s) {
                await zoteroCollection(s);
            }
        },

        'priorwork.viewHtml': async (arg?: unknown) => {
            // エクスプローラーの右クリック（Uri）か、無ければ reports/ の HTML から選ぶ
            let file = arg instanceof vscode.Uri ? arg.fsPath : undefined;
            if (!file) {
                const found = await vscode.workspace.findFiles('reports/*.html');
                const picked = await vscode.window.showQuickPick(found.map((u) => ({ label: path.basename(u.fsPath), file: u.fsPath })),
                    { placeHolder: vscode.l10n.t('Which report?') });
                file = picked?.file;
            }
            if (file) {
                showHtml(file, await titleOf(file));
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
                ? vscode.l10n.t('Priorwork: {2}: errors {0}, warnings {1}.', r.errors, r.warnings, s.topic)
                : vscode.l10n.t('Priorwork: no problems in {0}.', s.topic);
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
                    `Priorwork: ${e instanceof Error ? e.message : String(e)}`, model.root ? setUp : create);
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
            const text = vscode.l10n.t('Priorwork: problems {0}, warnings {1} (details in the output).', r.ng, r.warn);
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
                void vscode.window.showInformationMessage(vscode.l10n.t('Priorwork: AGENTS.md and the skills are up to date.'));
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
                    'Priorwork: the engine is updated. Review the changes with git and commit them.'));
            } catch (e) {
                fail(e);
            }
        },

        'priorwork.openSettings': () => settings.show(),

        'priorwork.publish': async () => {
            // VS Code の「GitHub に公開」（組み込みの GitHub 拡張機能）。非公開を選ぶよう念を押してから呼ぶ
            const L = vscode.l10n;
            const go = L.t('Publish to GitHub');
            const has = (await vscode.commands.getCommands(true)).includes('github.publish');
            const picked = await vscode.window.showInformationMessage(
                L.t('Keep the workspace in a private GitHub repository: the reports contain abstracts. When VS Code asks, choose "Publish to GitHub private repository" and include all the files it suggests (.env is left out by .gitignore).'),
                { modal: true }, ...(has ? [go] : []), L.t('Open Source Control'));
            if (picked === go) {
                await vscode.commands.executeCommand('github.publish');
                model.refresh();
            } else if (picked) {
                await vscode.commands.executeCommand('workbench.view.scm');
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

        'priorwork.runStep': async (s: SurveySummary, step: { id: string; text: string; args: string[] }) => {
            switch (step.id) {
                case 'scope': return vscode.commands.executeCommand('priorwork.editScope', s.name);
                case 'search': return vscode.commands.executeCommand('priorwork.search', s.name);
                case 'search_more': return vscode.commands.executeCommand('priorwork.askAgent', { name: s.name, task: 'search' });
                case 'zotero_import': return zoteroImport(s);
                case 'screen': return paper.show(s.name);
                case 'snowball': return vscode.commands.executeCommand('priorwork.snowball', s.name);
                case 'check': return vscode.commands.executeCommand('priorwork.check', s.name);
                case 'export': return vscode.commands.executeCommand('priorwork.exportReport', s.name);
                case 'fill':
                    return vscode.commands.executeCommand('priorwork.askAgent', { name: s.name, task: 'fill' });
                case 'zotero': return zoteroMissing(s);
                default:   // 拡張機能がまだ知らない工程（CLI のほうが新しいとき）。ターミナルは開かず、出力パネルに出す
                    try {
                        log(await busy(step.text, (o) => runText(model.root, step.args, o)));
                        output.show(true);
                        model.refresh();
                    } catch (e) {
                        fail(e);
                    }
                    return;
            }
        },
    };
    for (const [id, fn] of Object.entries(commands)) {
        context.subscriptions.push(vscode.commands.registerCommand(id, fn));
    }

    // 開いたときに一度、エンジンがあるか・版が合っているかを見る
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
