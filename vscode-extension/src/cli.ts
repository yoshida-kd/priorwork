// cli.ts — `priorwork` コマンドの呼び出しと、`--json` の出力の型。
//
// 拡張機能は状態を自分で持たない。読むのも書くのもぜんぶ CLI を通す（Octavo の拡張機能と同じ方針）。
// ここの interface のキーは tests/test_cli_json.py が CLI の出力と突き合わせる。名前を変えるときは両方を直す。
//
// どの priorwork を使うか（上から順に最初に見つかったもの）:
//   1. 設定 priorwork.command
//   2. ワークスペースの .venv（.venv/bin/priorwork、Windows は .venv\Scripts\priorwork.exe）
//   3. PATH の priorwork
import * as cp from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';

export type Status = 'candidate' | 'included' | 'excluded' | 'maybe';

export interface Counts {
    candidate: number;
    included: number;
    excluded: number;
    maybe: number;
}

export interface SurveySummary {
    name: string;
    topic: string;
    created: string;
    depth: string;
    lang: string;
    report: string;
    /** 原稿から始めたサーベイの原稿のパス（0.1.4 から。古い CLI には無い） */
    manuscript?: string | null;
    counts: Counts;
    searches: number;
}

export interface GitInfo {
    repo: boolean;
    remote: boolean;
}

export interface WorkspaceStatus {
    version: string;
    root: string;
    workspace: boolean;
    lang: string;
    git: GitInfo;
    sync: string | null;
    surveys: SurveySummary[];
}

export interface Scope {
    question: string;
    years: string;
    fields: string;
    inclusion: string;
    exclusion: string;
}

export interface NextStep {
    id: string;
    text: string;
    args: string[];
}

export interface SurveyDetail extends SurveySummary {
    scope: Scope;
    unfilled: number[];
    zotero_missing: number[];
    zotero_collection: ZoteroCollectionLink | null;
    sync: string | null;
    next: NextStep[];
}

/** サーベイに結び付けた Zotero のコレクション。 */
export interface ZoteroCollectionLink {
    key: string;
    name: string;
}

/** `priorwork zotero --collections --json` */
export interface ZoteroCollections {
    collections: ZoteroCollection[];
}

export interface ZoteroCollection {
    key: string;
    name: string;
    path: string;
    items: number;
}

/** `priorwork zotero SURVEY [--collection X] [--import] --json` */
export interface ZoteroReport {
    survey: string;
    collection: ZoteroCollectionLink | null;
    missing_dois: string[];
    to_import: number;
    imported: AddedPaper[];
    no_doi: string[];
}

export interface Ssci {
    status: string;
    badge: string;
    tier: number;
}

export interface PaperRecord {
    title: string;
    authors: string[];
    year: number | null;
    journal_name: string;
    doi: string;
    abstract: string;
    tldr: string;
    citation_count: number;
    ssci: Ssci;
    warnings: string[];
    url: string;
    oa_pdf: string;
}

export interface HistoryItem {
    at: string;
    status: Status;
    reason: string;
}

export interface FulltextInfo {
    path: string;
    source: string;
    pages: number | null;
    chars: number;
}

export interface Entry {
    number: number;
    key: string;
    status: Status;
    reason: string;
    found_by: string[];
    history: HistoryItem[];
    record: PaperRecord;
    fulltext?: FulltextInfo;
}

export interface Finding {
    level: 'ERROR' | 'WARN' | 'INFO';
    message: string;
}

export interface CheckReport {
    findings: Finding[];
    errors: number;
    warnings: number;
}

export interface DoctorCheck {
    level: 'ok' | 'warn' | 'ng';
    name: string;
    message: string;
}

export interface DoctorReport {
    version: string;
    root: string;
    lang: string;
    checks: DoctorCheck[];
    ng: number;
    warn: number;
}

export interface ExportReport {
    path: string;
    issues: string[];
}

export interface AddedPaper {
    number: number;
    new: boolean;
    status: Status;
    title: string;
}

export type Evidence = 'unchecked' | 'abstract' | 'fulltext';

export interface EvidenceOption {
    key: Evidence;
    label: string;
}

export interface CardField {
    key: string;
    label: string;
    /** 1行目が行内の値（比較マトリクスに載る）、2行目以降が直下の箇条書き */
    value: string;
}

/** `priorwork card SURVEY N --json`（採用論文のカード） */
export interface CardReport {
    number: number;
    evidence: Evidence | null;
    evidence_options: EvidenceOption[];
    fields: CardField[];
}

export interface SettingItem {
    key: string;
    secret: boolean;
    set: boolean;
    /** 秘密の値（API キー・パスワード）は空。設定済みかは set で見る */
    value: string;
}

export interface SsciListInfo {
    file: string | null;
    journals: number;
}

/** `priorwork settings --json` */
export interface SettingsReport {
    env: string;
    exists: boolean;
    items: SettingItem[];
    ssci: SsciListInfo;
}

export interface SearchReport {
    query: string;
    hits: number;
    new: number;
    added: AddedPaper[];
}

export class CliError extends Error {
    constructor(message: string, readonly code: number | null, readonly output: string) {
        super(message);
    }
}

function cfg() {
    return vscode.workspace.getConfiguration('priorwork');
}

/** CLI の表示の言語は VS Code の表示言語に合わせる。 */
export function displayLang(): string {
    return vscode.env.language.toLowerCase().startsWith('ja') ? 'ja' : 'en';
}

function venvCommand(root: string): string | undefined {
    const candidates = process.platform === 'win32'
        ? [path.join(root, '.venv', 'Scripts', 'priorwork.exe')]
        : [path.join(root, '.venv', 'bin', 'priorwork')];
    return candidates.find((p) => fs.existsSync(p));
}

/** 使う priorwork（見つからなければ 'priorwork' のまま返し、実行時に失敗させる）。 */
export function resolveCommand(root: string | undefined): string {
    const explicit = (cfg().get<string>('command', '') || '').trim();
    if (explicit) {
        return explicit.replace(/^~(?=$|\/|\\)/, os.homedir());
    }
    return (root && venvCommand(root)) || 'priorwork';
}

/** ~/.local/bin（pipx・uv tool が入れる場所）は、VS Code の PATH に無いことがある。 */
function childEnv(root: string | undefined): NodeJS.ProcessEnv {
    const extra = [path.join(os.homedir(), '.local', 'bin')];
    if (process.platform === 'darwin') {
        extra.push('/opt/homebrew/bin', '/usr/local/bin');
    }
    const have = (process.env.PATH ?? '').split(path.delimiter);
    const PATH = [...extra.filter((d) => !have.includes(d) && fs.existsSync(d)), process.env.PATH ?? '']
        .join(path.delimiter);
    const env: NodeJS.ProcessEnv = { ...process.env, PATH, PRIORWORK_LANG: displayLang(), PYTHONIOENCODING: 'utf-8' };
    if (root) {
        env.PRIORWORK_WORKSPACE = root;
    }
    return env;
}

export interface RunOptions {
    token?: vscode.CancellationToken;
    onOutput?: (text: string) => void;
    timeoutMs?: number;
    /** 標準入力に渡す文字列（API キーなどを引数に載せないため） */
    input?: string;
}

export interface RunResult {
    code: number | null;
    stdout: string;
    stderr: string;
}

/** priorwork が見つからないときの文言。何をすればよいかまで言う。 */
function notFound(root: string | undefined, command: string): string {
    const L = vscode.l10n;
    if ((cfg().get<string>('command', '') || '').trim()) {
        return L.t('The priorwork command was not found ({0}). Correct the setting priorwork.command, or clear it.', command);
    }
    return root
        ? L.t('The priorwork command was not found ({0}). Set up the Python environment (.venv): it installs priorwork into this workspace.', command)
        : L.t('The priorwork command was not found ({0}). Create a workspace: it installs priorwork into the workspace folder.', command);
}

/** priorwork を走らせて、出力をまるごと返す。token で取り消すと子プロセスを止める。 */
export function run(root: string | undefined, args: string[], opts: RunOptions = {}): Promise<RunResult> {
    const command = resolveCommand(root);
    return new Promise((resolve) => {
        let stdout = '';
        let stderr = '';
        let child: cp.ChildProcess;
        try {
            child = cp.spawn(command, args, { cwd: root ?? os.homedir(), env: childEnv(root), shell: false });
        } catch (e) {
            resolve({ code: null, stdout: '', stderr: String(e) });
            return;
        }
        if (opts.input !== undefined) {
            child.stdin?.end(opts.input);
        }
        const timer = opts.timeoutMs ? setTimeout(() => child.kill(), opts.timeoutMs) : undefined;
        child.stdout?.on('data', (b: Buffer) => { stdout += b.toString(); });
        child.stderr?.on('data', (b: Buffer) => {
            const s = b.toString();
            stderr += s;
            opts.onOutput?.(s);
        });
        const cancel = opts.token?.onCancellationRequested(() => child.kill());
        const done = (code: number | null, extra = ''): void => {
            if (timer) {
                clearTimeout(timer);
            }
            cancel?.dispose();
            resolve({ code, stdout, stderr: stderr + extra });
        };
        child.on('error', (e: NodeJS.ErrnoException) => {
            done(null, e.code === 'ENOENT' ? notFound(root, command) : e.message);
        });
        child.on('close', (code) => done(code));
    });
}

/** CLI のエラー出力から、人に見せる1行を取る（`Error: …` の行、無ければ最後の行）。 */
export function errorLine(stderr: string): string {
    const lines = stderr.trim().split(/\r?\n/).filter((l) => l.trim());
    const err = [...lines].reverse().find((l) => /^Error: /.test(l));
    return (err ?? lines[lines.length - 1] ?? '').replace(/^Error: /, '');
}

/** `--json` を付けて走らせ、標準出力を JSON として読む。読めなければ CliError。 */
export async function runJson<T>(root: string | undefined, args: string[], opts: RunOptions = {}): Promise<T> {
    const r = await run(root, [...args, '--json'], opts);
    const text = r.stdout.trim();
    if (text) {
        try {
            return JSON.parse(text) as T;
        } catch {
            // 下で CliError にする
        }
    }
    throw new CliError(errorLine(r.stderr) || vscode.l10n.t('priorwork {0} failed.', args[0]), r.code,
                       r.stderr + r.stdout);
}

/** JSON を出さないコマンド（render・sync・upgrade）。失敗したら CliError。 */
export async function runText(root: string | undefined, args: string[], opts: RunOptions = {}): Promise<string> {
    const r = await run(root, args, opts);
    if (r.code !== 0) {
        throw new CliError(errorLine(r.stderr) || vscode.l10n.t('priorwork {0} failed.', args[0]), r.code,
                           r.stderr + r.stdout);
    }
    return r.stdout;
}

/** `priorwork --version` → '0.1.0'。無ければ undefined。 */
export async function cliVersion(root: string | undefined): Promise<string | undefined> {
    const r = await run(root, ['--version'], { timeoutMs: 30000 });
    // 標準出力だけを見る。見つからないときの文言（stderr）も「priorwork …」で始まり、版と取り違える
    const m = r.code === 0 ? /^priorwork (\d\S*)/m.exec(r.stdout) : null;
    return m ? m[1] : undefined;
}

/** '0.1.10' と '0.1.9' を数として比べる。a < b なら負。 */
export function compareVersions(a: string, b: string): number {
    const pa = a.split('.').map((x) => parseInt(x, 10) || 0);
    const pb = b.split('.').map((x) => parseInt(x, 10) || 0);
    for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
        const d = (pa[i] ?? 0) - (pb[i] ?? 0);
        if (d !== 0) {
            return d;
        }
    }
    return 0;
}
