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
    CheckReport, CliError, DoctorReport, Entry, ExportReport, OctavoRequest, runJson, runText, SearchReport, Status,
    SurveySummary, ZoteroCollections, ZoteroReport,
} from './cli';
import { browseCollections } from './collections';
import { Model } from './model';
import { doiUrl, PaperPanel } from './paper';
import { SettingsPanel } from './settings';
import { Setup } from './setup';
import { Node, SurveyTree } from './tree';

/** エージェントに頼める仕事（文面は askAgent）。 */
type AgentTask = 'survey' | 'auto' | 'search' | 'screen' | 'snowball' | 'fill' | 'write' | 'reread' | 'check' | 'audit';

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
            survey: L.t('Carry on with the survey "{0}" ({1}) with Priorwork in its mode (./priorwork status shows it): search, screen, chase citations, fill in the cards, write the text, check and export, deciding on your own with reasons. If you stopped to wait for me, I am done: go on.', s.topic, s.name),
            auto: L.t('Carry on with the survey "{0}" ({1}) with Priorwork to the end without stopping (full auto from now on): search, screen, chase citations, fill in the cards, write the text, check and export. Decide on your own with reasons, and report at the end.', s.topic, s.name),
            search: L.t('Search more for the survey "{0}" ({1}) with Priorwork, from subtopics not searched yet, then screen the new candidates.', s.topic, s.name),
            screen: L.t('Screen the candidates of the survey "{0}" ({1}) with Priorwork against its criteria, recording a reason for each decision.', s.topic, s.name),
            snowball: L.t('Chase the citations of the included papers of the survey "{0}" ({1}) with Priorwork and screen the new candidates.', s.topic, s.name),
            fill: L.t('Fill in the paper cards of the survey "{0}" ({1}) with Priorwork: {2}. Write only what the abstract or the full text says, and update the evidence level.', s.topic, s.name, which),
            write: s.purpose === 'complete'
                ? L.t('Fill in my manuscript ({0}) from the survey "{1}" ({2}): map what each section lacks (the marks I left first: [cite], [@?], TODO(priorwork)), then write what to add and where, quoting the sentence it goes before or after, in the language of the manuscript. Fill in only what the literature backs, not the methods or the results. Cite only papers included in the survey, run ./priorwork check and export it with ./priorwork export {2} --draft. Do not rewrite the manuscript.', s.manuscript ?? '', s.topic, s.name)
                : s.purpose === 'advice'
                ? L.t('Write the advice on my manuscript ({0}) from the survey "{1}" ({2}): how it cites the literature (the direction of each citation), the literature it is missing, and comments on the argument, most important first. Cite only papers included in the survey, keep the literature apart from my own claims, and run ./priorwork check at the end. Do not rewrite the manuscript.', s.manuscript ?? '', s.topic, s.name)
                : s.manuscript
                ? L.t('Write the draft of the introduction, literature review and theory and hypotheses of my manuscript ({0}) from the survey "{1}" ({2}), in the language of the manuscript. Cite only papers included in the survey, show where the literature disagrees with my results, run ./priorwork check and export the draft with ./priorwork export {2} --draft.', s.manuscript, s.topic, s.name)
                : L.t('Write the text of the report of the survey "{0}" ({1}) from the paper cards: the background, the sections on the literature (theories, methods, debates, gaps), citing included papers for each claim, and the hypotheses of this study kept apart from the literature. Run ./priorwork check at the end.', s.topic, s.name),
            reread: L.t('My manuscript ({0}) has changed since the survey "{1}" ({2}) read it. Read it again with ./priorwork read {0} --for {2}, tell me what changed, and update what it made stale (what to add, the draft or the advice; search more if new claims need literature). Do not rewrite the manuscript.', s.manuscript ?? '', s.topic, s.name),
            check: L.t('Check the survey "{0}" ({1}) with Priorwork, fix what it finds and export the report.', s.topic, s.name),
            audit: L.t('Audit the survey "{0}" ({1}) with Priorwork, written by another model: check every paper card against the full text, the direction of each citation in the text, that my hypotheses are not presented as the literature, and the excluded papers. Fix what is wrong and record the audit with ./priorwork audit.', s.topic, s.name),
        }[task];
        await copyForAgent(text);
    }

    /**
     * 原稿から始めるサーベイの依頼文を作る。原稿（ファイルか、原稿と結果の表を入れたフォルダ）は
     * ワークスペースの manuscripts/ に置く決まり。外にあれば、そこへ写すかを聞く（元のファイルは動かさない）。
     */
    async function fromManuscript(r: string): Promise<void> {
        const L = vscode.l10n;
        const dir = path.join(r, 'manuscripts');
        const picked = await vscode.window.showOpenDialog({
            title: L.t('Choose the manuscript, its folder in manuscripts/, or a paper in an Octavo project'),
            defaultUri: vscode.Uri.file(fs.existsSync(dir) ? dir : r),
            canSelectFiles: true, canSelectFolders: true, canSelectMany: false, openLabel: L.t('Use This'),
        });
        if (!picked?.length) {
            return;
        }
        let file = picked[0].fsPath;
        const octavo = octavoProject(file);
        if (octavo) {
            // Octavo のプロジェクト（別のリポジトリ）の原稿は、写さずにその場で読む（.bib と分析の結果もそこにある）
            const rel = path.relative(r, file).split(path.sep).join('/');
            await copyForAgent(L.t('My manuscript is in {0}, in an Octavo project. With Priorwork, read it (./priorwork read reads the project\'s results and the literature it cites too), then propose what to make from it and wait for my answer: what for (filling in what it lacks, with what to add and where, the marks I left first; a draft of its introduction, literature review and theory and hypotheses; advice on it such as missing literature, the direction of its citations and the argument; or several as separate reports), which parts of the manuscript to cover, and the scope of the searches. Write for Octavo (./priorwork export --draft --octavo puts it in the project\'s inbox). Do not rewrite the manuscript.', rel));
            return;
        }
        if (path.relative(r, file).startsWith('..') || path.isAbsolute(path.relative(r, file))) {
            const copy = L.t('Copy It into manuscripts/');
            const choice = await vscode.window.showWarningMessage(
                L.t('The manuscript is outside the workspace. The agent reads it from manuscripts/ in the workspace (the original stays where it is).'),
                { modal: true }, copy);
            if (choice !== copy) {
                return;
            }
            const dest = path.join(dir, path.basename(file));
            if (fs.existsSync(dest)) {
                void vscode.window.showErrorMessage(L.t('manuscripts/{0} already exists. Rename or remove it first.', path.basename(file)));
                return;
            }
            fs.mkdirSync(dir, { recursive: true });
            fs.cpSync(file, dest, { recursive: true });
            file = dest;
        }
        const rel = path.relative(r, file).split(path.sep).join('/');
        await copyForAgent(L.t('My manuscript is in {0}. With Priorwork, read it, then propose what to make from it and wait for my answer: what for (filling in what it lacks, with what to add and where, the marks I left first; a draft of its introduction, literature review and theory and hypotheses; advice on it such as missing literature, the direction of its citations and the argument; or several as separate reports), which parts of the manuscript to cover, and the scope of the searches. Do not rewrite the manuscript.', rel));
    }

    /**
     * サーベイを Octavo のプロジェクトに結び付ける（外す）。1つのテーマのサーベイを、いくつもの論文で使う。
     * Octavo のプロジェクトは別のリポジトリなので、フォルダを選んでもらう。
     */
    async function linkOctavo(s: SurveySummary): Promise<void> {
        const L = vscode.l10n;
        const r = model.root;
        if (!r) {
            return;
        }
        const linked = (await model.detail(s.name).catch(() => undefined))?.octavo_projects ?? [];
        type Item = vscode.QuickPickItem & { root?: string; manuscript?: boolean };
        const items: Item[] = [
            ...linked.map((p) => ({ label: '$(close) ' + L.t('Unlink {0}', p.name), description: p.root, root: p.root,
                                    manuscript: p.manuscript })),
            { label: '$(add) ' + L.t('Link an Octavo project…'), description: L.t('choose its folder') },
        ];
        const picked = linked.length ? await vscode.window.showQuickPick(items, { title: L.t('Octavo projects for {0}', s.topic) })
            : items[items.length - 1];
        if (!picked) {
            return;
        }
        let args: string[];
        if (picked.root) {
            if (picked.manuscript) {
                void vscode.window.showInformationMessage(L.t('{0} holds the manuscript of this survey, so it stays linked.', picked.root));
                return;
            }
            args = ['scope', s.name, '--unlink-octavo', picked.root, '--json'];
        } else {
            const dir = await vscode.window.showOpenDialog({
                title: L.t('Choose the folder of the Octavo project (with octavo.config.py)'),
                defaultUri: vscode.Uri.file(path.dirname(r)), canSelectFiles: false, canSelectFolders: true, canSelectMany: false,
                openLabel: L.t('Use This'),
            });
            if (!dir?.length) {
                return;
            }
            if (!octavoProject(dir[0].fsPath)) {
                void vscode.window.showErrorMessage(L.t('{0} is not an Octavo project (no octavo.config.py).', dir[0].fsPath));
                return;
            }
            args = ['scope', s.name, '--octavo', dir[0].fsPath, '--json'];
        }
        try {
            await runJson(r, args);
        } catch (e) {
            fail(e);
            return;
        }
        model.refresh();
        void vscode.window.showInformationMessage(picked.root ? L.t('Priorwork: unlinked the Octavo project.')
            : L.t('Priorwork: linked the Octavo project. Export for it from the survey\'s menu; ./priorwork check tells you if its Zotero collections miss the survey\'s.'));
    }

    /** Octavo のプロジェクト用に書き出す（引用をそのプロジェクトの .bib のキーで [@key] に）。 */
    async function exportOctavo(s: SurveySummary): Promise<void> {
        const L = vscode.l10n;
        const linked = ((await model.detail(s.name).catch(() => undefined))?.octavo_projects ?? []).filter((p) => !p.missing);
        if (!linked.length) {
            const link = L.t('Link an Octavo project…');
            if (await vscode.window.showInformationMessage(L.t('This survey is not linked to an Octavo project yet.'), link) === link) {
                await linkOctavo(s);
            }
            return;
        }
        const project = linked.length === 1 ? linked[0] : (await vscode.window.showQuickPick(
            linked.map((p) => ({ label: p.name, description: p.root, p })), { title: L.t('Export for which Octavo project?') }))?.p;
        if (!project) {
            return;
        }
        let got: { path: string; missing: { doi: string; title: string }[] };
        try {
            got = await busy(L.t('writing for Octavo'), (o) => runJson(model.root, ['export', s.name, '--octavo', project.root, '--json'], o));
        } catch (e) {
            fail(e);
            return;
        }
        await vscode.window.showTextDocument(vscode.Uri.file(got.path));
        if (got.missing.length) {
            const copy = L.t('Copy the DOIs');
            if (await vscode.window.showWarningMessage(
                L.t('{0} papers are not in the .bib of {1}, so they are written as [@PRIORWORK:<DOI>]. Add them to its Zotero collection, then run octavo bib pull and octavo priorwork resolve there to replace them by their keys.',
                    got.missing.length, project.name), copy) === copy) {
                await vscode.env.clipboard.writeText(got.missing.map((m) => m.doi).filter(Boolean).join('\n'));
            }
        }
        // 原稿への取り込みは Octavo の側（別のウィンドウ）でする。そのエージェントへの依頼文を渡す
        const request = L.t('Copy the Request for Octavo');
        if (await vscode.window.showInformationMessage(
            L.t('Priorwork: put the text in the inbox of the Octavo project {0} (literature/priorwork/). Priorwork does not change the manuscript; ask the agent in the Octavo project to work it in.', project.name),
            request) === request) {
            const rel = got.path.startsWith(project.root) ? got.path.slice(project.root.length).replace(/^[\\/]/, '') : got.path;
            await vscode.env.clipboard.writeText(L.t('Priorwork has put text for my manuscript in {0} (the .json next to it says what it is and which papers it cites). Read it with the manuscript, propose where and how to work it in, and wait for my answer before changing the manuscript. Keep its citations ([@key]); [@PRIORWORK:…] marks papers not in the .bib yet.', rel));
            void vscode.window.showInformationMessage(
                L.t('Copied a request for Octavo. Paste it into your agent\'s chat in the window of the Octavo project.'));
        }
    }

    /** Zotero のコレクションのパス（"親 / 子"）が同じか。大文字小文字と区切りの空白は問わない。 */
    function samePath(a: string, b: string): boolean {
        const norm = (p: string): string => p.split('/').map((x) => x.trim().toLowerCase()).join('/');
        return norm(a) === norm(b);
    }

    /** コレクション ours が theirs そのものか、その下にあるか（priorwork/check.py の within_collection と同じ）。 */
    function withinCollection(ours: string, theirs: string): boolean {
        const po = ours.split('/').map((x) => x.trim().toLowerCase());
        const pt = theirs.split('/').map((x) => x.trim().toLowerCase());
        return pt.length === 1 ? po.includes(pt[0]) : pt.every((x, i) => po[i] === x);
    }

    /** file を含む Octavo のプロジェクトの根（octavo.config.py のあるフォルダ）。無ければ undefined。 */
    function octavoProject(file: string): string | undefined {
        let dir = fs.existsSync(file) && fs.statSync(file).isDirectory() ? file : path.dirname(file);
        for (;;) {
            if (fs.existsSync(path.join(dir, 'octavo.config.py'))) {
                return dir;
            }
            const up = path.dirname(dir);
            if (up === dir) {
                return undefined;
            }
            dir = up;
        }
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

    /**
     * 標準の進め方で、カードの記入の前に止まっているとき。採用論文を Zotero に集め（PDF も）、
     * それからエージェントに続きを頼む（本文で確かめたカードが増える）。
     */
    async function beforeCards(s: SurveySummary): Promise<void> {
        const L = vscode.l10n;
        const copy = L.t('Copy the DOIs');
        const add = L.t('Add to Zotero…');
        const goOn = L.t('Ask the Agent to Go On');
        for (;;) {
            // 設定で許されていれば、Priorwork が採用論文を結び付けたコレクションに入れられる（入れる前に見せて確かめる）
            const d = await model.detail(s.name).catch(() => undefined);
            const collection = d?.zotero_write ? d.zotero_collection?.name : undefined;
            const picked = await vscode.window.showInformationMessage(
                collection
                    ? L.t('The agent stops here so that you can collect the included papers of "{0}" and their PDFs in Zotero: the cards are then read from the full texts. Priorwork can add the papers to the collection "{1}"; then get their PDFs in Zotero and ask the agent to go on.', s.topic, collection)
                    : L.t('The agent stops here so that you can collect the included papers of "{0}" and their PDFs in Zotero: the cards are then read from the full texts. Copy the DOIs, paste them into Zotero\'s "Add Item by Identifier" (the magic wand), then ask the agent to go on.', s.topic),
                ...(collection ? [add] : [copy]), goOn);
            if (picked === add) {
                await zoteroAdd(s);
                continue;
            }
            if (picked === copy) {
                try {
                    const dois = (await runText(model.root, ['zotero', s.name, '--dois'])).trim();
                    await vscode.env.clipboard.writeText(dois);
                    void vscode.window.showInformationMessage(
                        L.t('Copied {0} DOIs. In Zotero, click the magic wand, paste them and press Enter.', dois ? dois.split('\n').length : 0));
                } catch (e) {
                    fail(e);
                    return;
                }
                continue;
            }
            if (picked === goOn) {
                await askAgent(s, 'survey');
            }
            return;
        }
    }

    /**
     * Zotero に無い採用論文。設定で許されていれば Priorwork がコレクションに入れ、そうでなければ DOI をまとめて
     * コピーする（Zotero の「識別子でアイテムを追加」に貼れる）。それから読み直す。
     */
    async function zoteroMissing(s: SurveySummary): Promise<void> {
        const L = vscode.l10n;
        const reload = L.t('Reload from Zotero');
        const link = L.t('Link a collection…');
        let collection = '';
        let canWrite = false;
        let written = 0;
        const missing = async (): Promise<Entry[]> => {
            const d = await model.detail(s.name);
            collection = d.zotero_collection?.name ?? '';
            canWrite = !!d.zotero_write && !!collection;
            written = d.zotero_written ?? 0;
            const numbers = new Set(d.zotero_missing);
            return (await model.papers(s.name)).filter((e) => numbers.has(e.number));
        };
        let entries = await missing();
        for (;;) {
            const undo = L.t('Undo What Priorwork Added…');
            if (!entries.length) {
                const picked = await vscode.window.showInformationMessage(L.t('Priorwork: all included papers are in Zotero.'),
                    ...(written ? [undo] : []));
                if (picked === undo) {
                    await zoteroUndo(s);
                }
                return;
            }
            const dois = entries.filter((e) => e.record.doi).map((e) => e.record.doi as string);
            const noDoi = entries.filter((e) => !e.record.doi).map((e) => `#${e.number}`);
            const copy = L.t('Copy the DOIs');
            const add = L.t('Add to Zotero…');
            const picked = await vscode.window.showInformationMessage(
                (collection
                    ? L.t('{0} included papers are not in the Zotero collection "{1}": {2}.', entries.length, collection,
                          entries.map((e) => `#${e.number}`).join(', '))
                    : L.t('{0} included papers are not in Zotero: {1}.', entries.length, entries.map((e) => `#${e.number}`).join(', ')))
                + ' ' + (canWrite
                    ? L.t('Priorwork can add them to the collection (you see the list first, and can undo it).')
                    : L.t('Copy their DOIs, paste them into Zotero\'s "Add Item by Identifier" (the magic wand), then reload.')
                      + (collection ? ' ' + L.t('Select the collection in Zotero first, so that they go into it.') : '')
                      + (noDoi.length ? ' ' + L.t('Add these by hand (no DOI): {0}.', noDoi.join(', ')) : '')),
                ...(canWrite ? [add] : dois.length ? [copy] : []), reload, ...(collection ? [] : [link]),
                ...(written ? [undo] : []));
            if (picked === link) {
                return zoteroCollection(s);
            }
            if (picked === add || picked === undo) {
                await (picked === add ? zoteroAdd(s) : zoteroUndo(s));
                entries = await missing();
                continue;
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

    /**
     * 採用論文を、サーベイに結び付けた Zotero のコレクションに入れる（設定の ZOTERO_WRITE で許されているときだけ）。
     * 先に入れるものを見せて確かめる。入れたら、PDF は Zotero でそろえてもらう。
     */
    async function zoteroAdd(s: SurveySummary): Promise<void> {
        const L = vscode.l10n;
        let plan: ZoteroReport;
        try {
            plan = await busy(L.t('checking what goes into Zotero'),
                (o) => runJson<ZoteroReport>(model.root, ['zotero', s.name, '--add', '--dry-run', '--json'], o));
        } catch (e) {
            fail(e);
            return;
        }
        const name = plan.collection?.name ?? '';
        const items = plan.written ?? [];
        if (!items.length) {
            void vscode.window.showInformationMessage(L.t('Priorwork: all included papers are in the Zotero collection "{0}".', name));
            return;
        }
        const add = L.t('Add to Zotero');
        const picked = await vscode.window.showInformationMessage(
            L.t('Add {0} papers to the Zotero collection "{1}"?', items.length, name),
            { modal: true,
              detail: items.map((w) => `#${w.number} ${w.action === 'create' ? L.t('(new item)') : L.t('(already in the library)')} ${w.title}`).join('\n')
                  + '\n\n' + L.t('Priorwork only adds them to the collection: it does not change or delete your items, and can undo what it added.') },
            add);
        if (picked !== add) {
            return;
        }
        let r: ZoteroReport;
        try {
            r = await busy(L.t('adding the papers to Zotero'),
                (o) => runJson<ZoteroReport>(model.root, ['zotero', s.name, '--add', '--json'], o));
        } catch (e) {
            fail(e);
            return;
        }
        model.refresh();
        const done = (r.written ?? []).filter((w) => w.done);
        const failed = (r.written ?? []).filter((w) => !w.done);
        void vscode.window.showInformationMessage(
            L.t('Priorwork: added {0} papers to the Zotero collection "{1}". Get their PDFs in Zotero (select them, right-click → Find Full Text).', done.length, name)
            + (failed.length ? ' ' + L.t('Not added: {0}.', failed.map((w) => `#${w.number} (${w.error ?? ''})`).join(', ')) : ''));
    }

    /** Priorwork が Zotero に書いたものを戻す。作ったアイテムは、手が入っていなければごみ箱へ。 */
    async function zoteroUndo(s: SurveySummary): Promise<void> {
        const L = vscode.l10n;
        const undo = L.t('Undo');
        const picked = await vscode.window.showWarningMessage(
            L.t('Take back what Priorwork added to Zotero for "{0}"?', s.topic),
            { modal: true, detail: L.t('Items Priorwork made go to the Zotero trash, unless you changed them or attached files since. Items that were already in your library only leave the collection.') },
            undo);
        if (picked !== undo) {
            return;
        }
        try {
            const r = await busy(L.t('undoing the changes in Zotero'),
                (o) => runJson<ZoteroReport>(model.root, ['zotero', s.name, '--undo', '--json'], o));
            model.refresh();
            const w = r.written ?? [];
            const kept = w.filter((x) => x.undo === 'keep').map((x) => `#${x.number}`);
            const failed = w.filter((x) => !x.done).map((x) => `#${x.number} (${x.error ?? ''})`);
            void vscode.window.showInformationMessage(
                L.t('Priorwork: undid {0} changes in Zotero.', w.filter((x) => x.done && x.undo !== 'keep').length)
                + (kept.length ? ' ' + L.t('Kept, because they were changed in Zotero since: {0}.', kept.join(', ')) : '')
                + (failed.length ? ' ' + L.t('Failed: {0}.', failed.join(', ')) : ''));
        } catch (e) {
            fail(e);
        }
    }

    /**
     * サーベイに Zotero のコレクションを結び付ける。Priorwork はコレクションを作らないので、コレクションは Zotero で
     * 作ってもらい、ここで読み直す。原稿が Octavo のプロジェクトにあれば、Octavo が .bib を取るコレクションを先頭に出す
     * （同じコレクションに集めれば、Octavo の参考文献にもなる）。
     */
    async function zoteroCollection(s: SurveySummary): Promise<void> {
        const L = vscode.l10n;
        const detail = await model.detail(s.name).catch(() => undefined);
        const current = detail?.zotero_collection;
        // このサーベイを使う Octavo のプロジェクトが .bib を取るコレクション（その下のものも候補）
        const octavoNames = (detail?.octavo_projects ?? []).flatMap((p) => p.zotero_collections ?? []);
        const underOctavo = (c: { path: string }): boolean => octavoNames.some((n) => withinCollection(c.path, n));
        let refresh = false;
        let picked: { kind: 'pick'; key: string } | { kind: 'unlink' } | undefined;
        for (;;) {
            let list: ZoteroCollections;
            try {
                list = await busy(L.t('reading the Zotero collections'),
                    (o) => runJson<ZoteroCollections>(model.root, ['zotero', '--collections', '--json', ...(refresh ? ['--refresh'] : [])], o));
            } catch (e) {
                fail(e);
                return;
            }
            const suggested = list.collections.filter((c) => octavoNames.some((n) => samePath(c.path, n)
                || (!n.includes('/') && c.name.toLowerCase() === n.toLowerCase())));
            const r = await browseCollections({
                cols: list.collections,
                title: L.t('Zotero collection for {0}', s.topic),
                current: current?.key,
                suggested: suggested.map((c) => c.key),
                hint: octavoNames.length && !suggested.length
                    ? L.t('The Octavo project uses "{0}", which is not in Zotero yet. Make it in Zotero, then reload.', octavoNames.join('", "'))
                    : L.t('Choose a folder to open it; the included papers go into the collection you use'),
                note: (c) => octavoNames.length && underOctavo(c) ? L.t('under the Octavo project\'s collection') : '',
            });
            if (!r) {
                return;
            }
            if (r.kind === 'reload') {
                refresh = true;
                continue;
            }
            if (r.kind === 'howto') {
                const reload = L.t('Reload the list');
                const again = await vscode.window.showInformationMessage(
                    L.t('Priorwork does not make collections, so make it in Zotero: right-click "My Library" (or a collection) → New Collection… and name it{0}. Then come back and reload the list.',
                        octavoNames.length ? ' ' + L.t('"{0}" (the name the Octavo project uses)', octavoNames[0]) : ''),
                    { modal: false }, reload);
                if (again !== reload) {
                    return;
                }
                refresh = true;
                continue;
            }
            picked = r;
            break;
        }
        const key = picked.kind === 'pick' ? picked.key : '';
        let r: ZoteroReport;
        try {
            r = await runJson<ZoteroReport>(model.root, ['zotero', s.name, '--collection', key, '--json']);
        } catch (e) {
            fail(e);
            return;
        }
        model.refresh();
        if (!r.collection) {
            void vscode.window.showInformationMessage(L.t('Priorwork: unlinked the Zotero collection.'));
            return;
        }
        // このサーベイを使う Octavo のプロジェクトのうち、このコレクションを取らないもの（Octavo 側に足すコマンドを渡す。
        // Octavo のプロジェクトは別のウィンドウなので）
        const linkedName = r.collection.name;
        const notPulled = (detail?.octavo_projects ?? []).filter((p) => !p.missing
            && !(p.zotero_collections ?? []).some((n) => withinCollection(linkedName, n)));
        if (notPulled.length) {
            const copy = L.t('Copy the Command');
            const picked2 = await vscode.window.showInformationMessage(
                L.t('The Octavo projects {0} do not pull their .bib from this collection. In Octavo, add it with Choose the Zotero Collection.',
                    notPulled.map((p) => p.name).join(', ')), copy);
            if (picked2 === copy) {
                await vscode.env.clipboard.writeText(`octavo config set zotero_collection "${linkedName}"`);
            }
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
     * 書き出した HTML に CSP を足す。動かしてよいスクリプトは Mermaid の図を描くもの
     * （priorwork/export.py の MERMAID_JS）と、ここで足すコピーの補助だけで、レポートに紛れ込んだスクリプトは動かさない。
     * 文章は選択してコピーできる（エディターによってはコピーのキーが webview に届かないので、選択を拡張機能に送って
     * クリップボードに書く）。ページ内の検索（Ctrl+F）は webview の検索ウィジェットで行う（showHtml の enableFindWidget）。
     */
    function reportHtml(file: string): string {
        const nonce = [...Array(24)].map(() => Math.floor(Math.random() * 36).toString(36)).join('');
        const csp = '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
            + 'style-src \'unsafe-inline\'; img-src https: data:; font-src https: data:; '
            + `script-src 'nonce-${nonce}' https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js;">`;
        const select = '<style>html, body, main { -webkit-user-select: text; user-select: text; }</style>';
        const copy = `<script nonce="${nonce}">(() => {
    const vscode = acquireVsCodeApi();
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'c' || e.key === 'C' || e.key === 'Insert')) {
            const text = String(window.getSelection() || '');
            if (text) { vscode.postMessage({ type: 'copy', text }); }
        }
    });
})();</script>`;
        return fs.readFileSync(file, 'utf-8').replace(/<head>/i, `<head>\n${csp}\n${select}`)
            .replace(/<\/body>/i, `${copy}\n</body>`);
    }

    /**
     * 読むための版（HTML）をエディターの中で見せる。SSH でつないだサーバーでも見られる
     * （Live Preview などはサーバーの上のファイルをブラウザに出せないことがある）。
     */
    function showHtml(file: string, title: string): void {
        if (!reportPanel) {
            reportPanel = vscode.window.createWebviewPanel('priorwork.report', title, vscode.ViewColumn.Active,
                                                           { enableScripts: true, enableFindWidget: true,
                                                             retainContextWhenHidden: true });
            reportPanel.onDidDispose(() => { reportPanel = undefined; reportFile = undefined; });
            reportPanel.webview.onDidReceiveMessage((m: { type?: string; text?: string }) => {
                if (m.type === 'copy' && typeof m.text === 'string') {
                    void vscode.env.clipboard.writeText(m.text);
                }
            });
        }
        reportPanel.title = title;
        reportPanel.webview.html = reportHtml(file);
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
                reportPanel.webview.html = reportHtml(uri.fsPath);
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
                    { label: L.t('Carry on'), description: L.t('in the survey\'s mode (standard: stops before the cards for Zotero)'), task: 'survey' },
                    { label: L.t('Carry on to the end'), description: L.t('the whole survey, without stopping'), task: 'auto' },
                    { label: L.t('Search more'), description: L.t('more queries, then screening'), task: 'search' },
                    { label: L.t('Screen the candidates'), description: L.t('decisions with reasons'), task: 'screen' },
                    { label: L.t('Chase citations'), description: L.t('snowball, then screening'), task: 'snowball' },
                    { label: L.t('Fill in the paper cards'), description: L.t('from the abstracts or full texts'), task: 'fill' },
                    s.purpose === 'complete'
                        ? { label: L.t('Fill in the manuscript'), description: L.t('what it lacks, and where to add it'), task: 'write' }
                        : s.purpose === 'advice'
                        ? { label: L.t('Write the advice on the manuscript'), description: L.t('citations, missing literature, the argument'), task: 'write' }
                        : s.manuscript
                        ? { label: L.t('Write the draft of the manuscript'), description: L.t('introduction, literature review, hypotheses'), task: 'write' }
                        : { label: L.t('Write the text of the report'), description: L.t('background, literature, hypotheses'), task: 'write' },
                    { label: L.t('Check and fix'), description: L.t('then export the report'), task: 'check' },
                    { label: L.t('Audit as another model'), description: L.t('optional; paste into a model other than the one that wrote it'), task: 'audit' },
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
                { label: L.t('Start from my manuscript'), detail: L.t('Any format (Markdown, Quarto HTML, Word, PDF), finished or not. The agent proposes what to make with you: what to add where it lacks something (leave [cite] or TODO(priorwork): … where you want help), a draft of its introduction, literature review and hypotheses, or advice on it.'), agent: true, manuscript: true },
                { label: L.t('Set it up myself'), detail: L.t('Give the topic, slug, depth and question, then search and screen in the sidebar.'), agent: false },
            ], { title: L.t('New survey'), placeHolder: L.t('How do you want to make it?') });
            if (!how) {
                return;
            }
            if ('manuscript' in how) {
                await fromManuscript(r);
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
                const mode = await vscode.window.showQuickPick([
                    { label: L.t('Standard'), description: L.t('Recommended'), detail: L.t('Stops twice: once the scope is set, and before the paper cards, showing the DOIs to collect in Zotero (cards read from the PDFs are better).'), mode: 'standard' },
                    { label: L.t('Full auto'), description: '', detail: L.t('To the end without stopping.'), mode: 'auto' },
                    { label: L.t('Step by step'), description: '', detail: L.t('Stops after every step for you to check.'), mode: 'manual' },
                ], { title: L.t('New survey'), placeHolder: L.t('Where should the agent stop for you?') });
                if (!mode) {
                    return;
                }
                const notes = await vscode.window.showInputBox({
                    title: L.t('New survey'),
                    prompt: L.t('Anything else for the agent? (optional) E.g. the research question, inclusion criteria, years, fields or papers to start from. Press Enter to skip.'),
                    placeHolder: L.t('e.g. Since 2000, field experiments only; start from Card and Krueger (1994)'),
                });
                if (notes === undefined) {
                    return;
                }
                const what = deep.label === 'full' || deep.label === 'quick'
                    ? L.t('Make a literature survey with Priorwork (depth: {0}) on: {1}.', deep.label, about.trim())
                    : L.t('Make a literature survey with Priorwork on: {0}. Choose the depth yourself.', about.trim());
                const how = {
                    standard: L.t('Go in the standard mode: set the scope and stop to show it to me; then search, screen and chase citations, and stop again before the paper cards, showing me the DOIs to collect in Zotero. Decide on your own with reasons in between.'),
                    auto: L.t('Go in full auto: set the scope yourself, then search, screen, chase citations, fill in the cards, write the text, check and export without stopping, and report at the end.'),
                    manual: L.t('Go step by step: stop after each step (scope, searches, screening, citations, cards, text, check) and wait for me.'),
                }[mode.mode];
                await copyForAgent(`${what} ${how}${notes.trim() ? ' ' + L.t('Notes from me: {0}', notes.trim()) : ''}`);
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
                model.refresh();        // 途中で止まっても、それまでに登録した論文は保存されている
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

        'priorwork.openRequest': async (arg?: unknown) => {
            // Octavo からの依頼: エージェントに頼む（短い依頼文。中身は ./priorwork requests で読む）か、断る
            const r = arg as OctavoRequest | undefined;
            if (!r?.id) {
                return;
            }
            const L = vscode.l10n;
            const ask = L.t('Ask the Agent to Carry It Out');
            const decline = L.t('Decline…');
            const picked = await vscode.window.showInformationMessage(
                L.t('A request from Octavo ({0}):', r.project ?? ''), { modal: true, detail: r.text ?? '' }, ask, decline);
            if (picked === ask) {
                await copyForAgent(L.t('Carry out the request {0} from Octavo with Priorwork: read it with ./priorwork requests {0}, follow it, and when it is done record it with ./priorwork requests {0} --done --survey <survey>.', r.id));
            } else if (picked === decline) {
                const note = await vscode.window.showInputBox({ prompt: L.t('Why (shown to Octavo)'), ignoreFocusOut: true });
                if (note === undefined) {
                    return;
                }
                try {
                    await runJson(model.root, ['requests', r.id, '--decline', '--note', note, '--json']);
                } catch (e) {
                    fail(e);
                }
                model.refresh();
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

        'priorwork.archive': async (arg?: unknown) => {
            const s = await surveyOf(arg);
            if (!s) {
                return;
            }
            const L = vscode.l10n;
            const ok = L.t('Archive');
            const picked = await vscode.window.showWarningMessage(
                L.t('Archive "{0}" ({1})? It is hidden from the list; its report and papers stay, and you can bring it back.',
                    s.topic, s.name), { modal: true }, ok);
            if (picked !== ok) {
                return;
            }
            try {
                await runJson(model.root, ['archive', s.name]);
            } catch (e) {
                fail(e);
                return;
            }
            model.refresh();
        },

        'priorwork.unarchive': async (arg?: unknown) => {
            const s = arg && typeof arg === 'object' && 'survey' in arg ? (arg as { survey: SurveySummary }).survey : undefined;
            if (!s) {
                return;
            }
            try {
                await runJson(model.root, ['archive', s.name, '--undo']);
            } catch (e) {
                fail(e);
                return;
            }
            model.refresh();
        },

        'priorwork.linkOctavo': async (arg?: unknown) => {
            const s = await surveyOf(arg);
            if (s) {
                await linkOctavo(s);
            }
        },

        'priorwork.exportOctavo': async (arg?: unknown) => {
            const s = await surveyOf(arg);
            if (s) {
                await exportOctavo(s);
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
                case 'draft':
                    return vscode.commands.executeCommand('priorwork.askAgent', { name: s.name, task: 'write' });
                case 'zotero': return zoteroMissing(s);
                case 'wait_zotero': return beforeCards(s);
                case 'manuscript_changed':
                    return vscode.commands.executeCommand('priorwork.askAgent', { name: s.name, task: 'reread' });
                case 'advice':
                case 'complete':
                    return vscode.commands.executeCommand('priorwork.askAgent', { name: s.name, task: 'write' });
                case 'audit':
                    return vscode.commands.executeCommand('priorwork.askAgent', { name: s.name, task: 'audit' });
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
