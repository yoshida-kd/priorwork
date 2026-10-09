// setup.ts — ワークスペースを作る・Python の環境（.venv）を用意する・エンジンの版を確かめる。
//
// 拡張機能を入れただけで始められるように、priorwork コマンドが無ければワークスペースの .venv を作り、
// PyPI から拡張機能と同じ版の priorwork を入れる（ワークスペースの requirements.txt もその版を指す）。
// 入れたあとは cli.ts がその .venv の priorwork を見つける。
//
// .venv を作る Python: 3.10 以上が見つかればそれ。無ければ uv（Astral）に Python ごと取ってこさせる
// （uv も無ければ、確かめてから公式のインストーラーでホームの下に入れる。管理者権限は要らない）。
import * as cp from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';
import { cliVersion, compareVersions, displayLang, runText } from './cli';

interface Cmd {
    command: string;
    args: string[];
}

/** 走らせて、出力（stdout）を返す。動かなければ undefined。 */
function probe(c: Cmd, args: string[]): Promise<string | undefined> {
    return new Promise((resolve) => {
        cp.execFile(c.command, [...c.args, ...args], { timeout: 15000 }, (err, stdout) =>
            resolve(err ? undefined : String(stdout).trim()));
    });
}

/** 3.10 以上の Python。設定 priorwork.python があればそれだけを見る。 */
async function findPython(): Promise<Cmd | undefined> {
    const explicit = (vscode.workspace.getConfiguration('priorwork').get<string>('python', '') || '').trim();
    const candidates: Cmd[] = explicit ? [{ command: explicit, args: [] }]
        : process.platform === 'win32' ? [{ command: 'py', args: ['-3'] }, { command: 'python', args: [] }]
            : ['python3', 'python3.14', 'python3.13', 'python3.12', 'python3.11', 'python3.10']
                .map((command) => ({ command, args: [] }));
    for (const c of candidates) {
        if (await probe(c, ['-c', 'import sys; print(sys.version_info >= (3, 10))']) === 'True') {
            return c;
        }
    }
    return undefined;
}

/** uv の場所（PATH か、公式のインストーラーが入れる ~/.local/bin）。 */
async function findUv(): Promise<string | undefined> {
    const exe = process.platform === 'win32' ? 'uv.exe' : 'uv';
    const places = ['uv', path.join(os.homedir(), '.local', 'bin', exe), path.join(os.homedir(), '.cargo', 'bin', exe)];
    for (const p of places) {
        if (await probe({ command: p, args: [] }, ['--version'])) {
            return p;
        }
    }
    return undefined;
}

function venvPython(root: string): string {
    return process.platform === 'win32'
        ? path.join(root, '.venv', 'Scripts', 'python.exe')
        : path.join(root, '.venv', 'bin', 'python');
}

/** 1つのコマンドを走らせ、出力を出力パネルに流す。終了コードを返す。 */
function stream(command: string, args: string[], cwd: string, output: vscode.OutputChannel,
                token?: vscode.CancellationToken, progress?: vscode.Progress<{ message?: string }>): Promise<number | null> {
    output.appendLine(`$ ${command} ${args.join(' ')}`);
    return new Promise((resolve) => {
        const child = cp.spawn(command, args, { cwd, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
        const onText = (b: Buffer): void => {
            const s = b.toString();
            output.append(s);
            const last = s.trim().split(/\r?\n/).pop()?.trim();
            if (last) {
                progress?.report({ message: last.slice(0, 100) });
            }
        };
        child.stdout.on('data', onText);
        child.stderr.on('data', onText);
        const cancel = token?.onCancellationRequested(() => child.kill());
        child.on('error', (e) => { output.appendLine(e.message); cancel?.dispose(); resolve(null); });
        child.on('close', (code) => { cancel?.dispose(); resolve(code); });
    });
}

export class Setup {
    constructor(private readonly context: vscode.ExtensionContext, private readonly output: vscode.OutputChannel) {}

    get version(): string {
        return String(this.context.extension.packageJSON.version ?? '0');
    }

    /**
     * root に .venv を作り、priorwork を入れる。requirements.txt があればそれ（ワークスペースが指す版）、
     * 無ければ拡張機能と同じ版。成功したら true。
     */
    async createVenv(root: string): Promise<boolean> {
        const py = fs.existsSync(venvPython(root)) ? undefined : await findPython();
        let uv: string | undefined;
        if (!py && !fs.existsSync(venvPython(root))) {
            uv = await findUv() ?? await this.installUv();
            if (!uv) {
                return false;
            }
        }
        const req = path.join(root, 'requirements.txt');
        // requirements.txt が priorwork の版を指していなければ、拡張機能と同じ版を入れる
        const pinned = fs.existsSync(req) && /^\s*priorwork\b/m.test(fs.readFileSync(req, 'utf-8'));
        const spec = pinned ? ['-r', req] : [`priorwork==${this.version}`];
        const title = vscode.l10n.t('Prior Work: setting up the Python environment (.venv)');
        this.output.appendLine(`\n== ${title}`);
        const code = await vscode.window.withProgress(
            { location: vscode.ProgressLocation.Notification, title, cancellable: true },
            async (progress, token) => {
                if (!fs.existsSync(venvPython(root))) {
                    // uv は Python が無ければ取ってくる。--seed で pip も入れる（priorwork upgrade が使う）
                    const made = py
                        ? await stream(py.command, [...py.args, '-m', 'venv', '.venv'], root, this.output, token, progress)
                        : await stream(uv as string, ['venv', '--seed', '--python', '>=3.10', '.venv'], root, this.output,
                                       token, progress);
                    if (made !== 0) {
                        return made;
                    }
                }
                return stream(venvPython(root), ['-m', 'pip', 'install', '--upgrade', ...spec], root, this.output,
                              token, progress);
            });
        if (code === 0) {
            return true;
        }
        const show = vscode.l10n.t('Show the output');
        void vscode.window.showErrorMessage(vscode.l10n.t(
            'Prior Work: could not set up the Python environment. It needs Python 3.10 or later '
            + '(the setting priorwork.python chooses which one).'), show)
            .then((p) => { if (p === show) { this.output.show(); } });
        return false;
    }

    /** Python が無いとき: 確かめてから uv を公式のインストーラーで入れる。入れた uv の場所を返す。 */
    private async installUv(): Promise<string | undefined> {
        const L = vscode.l10n;
        const go = L.t('Install uv');
        const picked = await vscode.window.showInformationMessage(L.t(
            'Prior Work needs Python 3.10 or later, which was not found. It can install uv (a small tool from Astral, into your home folder, without administrator rights), which then downloads Python for the workspace.'),
            { modal: true }, go);
        if (picked !== go) {
            return undefined;
        }
        const [command, args] = process.platform === 'win32'
            ? ['powershell', ['-NoProfile', '-ExecutionPolicy', 'ByPass', '-Command', 'irm https://astral.sh/uv/install.ps1 | iex']]
            : ['sh', ['-c', 'if command -v curl >/dev/null; then curl -LsSf https://astral.sh/uv/install.sh | sh; '
                             + 'else wget -qO- https://astral.sh/uv/install.sh | sh; fi']];
        const title = L.t('Prior Work: installing uv');
        this.output.appendLine(`\n== ${title}`);
        const code = await vscode.window.withProgress(
            { location: vscode.ProgressLocation.Notification, title, cancellable: true },
            (progress, token) => stream(command, args, os.homedir(), this.output, token, progress));
        const uv = code === 0 ? await findUv() : undefined;
        if (!uv) {
            const show = L.t('Show the output');
            void vscode.window.showErrorMessage(L.t(
                'Prior Work: could not install uv. Install Python 3.10 or later (python.org), then try again.'), show)
                .then((p) => { if (p === show) { this.output.show(); } });
        }
        return uv;
    }

    /** 「ワークスペースを作る」: フォルダ・言語を選び、必要なら .venv を用意して `priorwork init`。 */
    async initWorkspace(onDone: () => void): Promise<void> {
        const open = vscode.workspace.workspaceFolders?.[0]?.uri;
        let folder: vscode.Uri | undefined;
        const here = open && !fs.existsSync(path.join(open.fsPath, '.priorwork')) ? open : undefined;
        if (here) {
            const thisOne = vscode.l10n.t('This folder ({0})', path.basename(here.fsPath));
            const other = vscode.l10n.t('Choose another folder…');
            const picked = await vscode.window.showQuickPick([thisOne, other],
                { placeHolder: vscode.l10n.t('Where should the workspace be?') });
            if (!picked) {
                return;
            }
            folder = picked === thisOne ? here : undefined;
        }
        if (!folder) {
            const got = await vscode.window.showOpenDialog({
                canSelectFolders: true, canSelectFiles: false, canSelectMany: false,
                openLabel: vscode.l10n.t('Create the workspace here'),
                title: vscode.l10n.t('Choose an empty folder for the workspace'),
            });
            folder = got?.[0];
        }
        if (!folder) {
            return;
        }
        const root = folder.fsPath;
        const langs = [
            { label: 'English', lang: 'en', description: vscode.l10n.t('reports, AGENTS.md and the skills in English') },
            { label: '日本語', lang: 'ja', description: vscode.l10n.t('reports, AGENTS.md and the skills in Japanese') },
        ];
        if (displayLang() === 'ja') {
            langs.reverse();
        }
        const lang = await vscode.window.showQuickPick(langs,
            { placeHolder: vscode.l10n.t('The language of the reports (it cannot be changed later)') });
        if (!lang) {
            return;
        }

        // priorwork が使えなければ、そのフォルダに .venv を作って入れる
        if (!(await cliVersion(root)) && !(await this.createVenv(root))) {
            return;
        }
        try {
            const out = await vscode.window.withProgress(
                { location: vscode.ProgressLocation.Notification, title: vscode.l10n.t('Prior Work: creating the workspace') },
                () => runText(root, ['init', root, '--lang', lang.lang]));
            this.output.appendLine(out);
        } catch (e) {
            void vscode.window.showErrorMessage(e instanceof Error ? e.message : String(e));
            return;
        }
        if (open && open.fsPath === root) {
            onDone();
            const env = vscode.l10n.t('Open the Settings');
            const picked = await vscode.window.showInformationMessage(vscode.l10n.t(
                'Prior Work: the workspace is ready. Set your API keys in the settings, then start a survey.'), env);
            if (picked === env) {
                void vscode.commands.executeCommand('priorwork.openSettings');
            }
            return;
        }
        const openIt = vscode.l10n.t('Open the folder');
        const picked = await vscode.window.showInformationMessage(
            vscode.l10n.t('Prior Work: the workspace is ready in {0}.', root), openIt);
        if (picked === openIt) {
            void vscode.commands.executeCommand('vscode.openFolder', folder);
        }
    }

    /** 開いたときに一度: priorwork が無い・古いなら知らせる。 */
    async checkEngine(root: string, onReady: () => void): Promise<void> {
        const have = await cliVersion(root);
        if (!have) {
            const setUp = vscode.l10n.t('Set up .venv');
            const picked = await vscode.window.showWarningMessage(vscode.l10n.t(
                'Prior Work: the priorwork command was not found for this workspace.'), setUp);
            if (picked === setUp && await this.createVenv(root)) {
                onReady();
            }
            return;
        }
        if (compareVersions(have, this.version) < 0) {
            const update = vscode.l10n.t('Update the engine');
            const picked = await vscode.window.showInformationMessage(vscode.l10n.t(
                'Prior Work: this workspace uses priorwork {0}; the extension is {1}.', have, this.version), update);
            if (picked === update) {
                await vscode.commands.executeCommand('priorwork.upgrade', this.version);
            }
        }
    }
}
