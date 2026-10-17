// collections.ts — Zotero のコレクションを、フォルダをたどる形で選ぶ。
//
// Zotero のコレクションは入れ子のフォルダ。いちばん上のフォルダだけを並べ、フォルダを選ぶとその中を並べる、を
// 繰り返して選ぶ（全部を一度に並べると、数が多いときに探せない）。中にフォルダがあるものは開き、無いものは
// そのまま選ぶ。開いたフォルダそのものは、先頭の「このフォルダを使う」で選ぶ。名前で探したいときは
// 「すべてのフォルダから探す」で、パスつきの一覧に切り替える。
import * as vscode from 'vscode';
import { ZoteroCollection } from './cli';

export type Browse =
    | { kind: 'pick'; key: string }
    | { kind: 'unlink' }
    | { kind: 'reload' }
    | { kind: 'howto' };

interface Item extends vscode.QuickPickItem {
    act: 'open' | 'pick' | 'up' | 'use' | 'all' | 'reload' | 'howto' | 'unlink';
    key?: string;
}

/** 親のキー。古い CLI（0.1.8 まで）は parent を出さないので、パス（"親 / 子"）から求める。 */
function parentsOf(cols: ZoteroCollection[]): Map<string, string> {
    const byPath = new Map(cols.map((c) => [c.path, c.key]));
    return new Map(cols.map((c) => {
        if (c.parent !== undefined) {
            return [c.key, c.parent];
        }
        const up = c.path.slice(0, Math.max(0, c.path.length - c.name.length - 3));
        return [c.key, c.path.endsWith(` / ${c.name}`) ? byPath.get(up) ?? '' : ''];
    }));
}

export async function browseCollections(opts: {
    cols: ZoteroCollection[];
    title: string;
    /** いま結び付いているコレクションのキー */
    current?: string;
    /** 先頭に出すコレクション（Octavo のプロジェクトのもの）のキー */
    suggested?: string[];
    /** 選ぶ前の説明（placeholder） */
    hint: string;
    /** コレクションごとに説明に添える言葉（「Octavo のプロジェクトが使う」など） */
    note?: (c: ZoteroCollection) => string;
}): Promise<Browse | undefined> {
    const L = vscode.l10n;
    const { cols } = opts;
    const parent = parentsOf(cols);
    const byKey = new Map(cols.map((c) => [c.key, c]));
    const children = (key: string): ZoteroCollection[] => cols.filter((c) => parent.get(c.key) === key)
        .sort((a, b) => a.name.localeCompare(b.name));
    // いま結び付いているものと、その上のフォルダすべて（開く道筋に印を付ける）
    const onPath = new Set<string>();
    for (let k = opts.current; k; k = parent.get(k)) {
        onPath.add(k);
    }
    const describe = (c: ZoteroCollection): string => {
        const n = children(c.key).length;
        return [L.t('{0} items', c.total ?? c.items), n ? L.t('{0} folders inside', n) : '', opts.note?.(c) ?? '']
            .filter(Boolean).join(' · ');
    };
    const folderItem = (c: ZoteroCollection, label = c.name): Item => ({
        label: (c.key === opts.current ? '$(pass-filled) ' : onPath.has(c.key) ? '$(folder-opened) ' : '$(folder) ') + label
            + (children(c.key).length ? '  ›' : ''),
        description: describe(c),
        act: children(c.key).length ? 'open' : 'pick',
        key: c.key,
    });
    const tail: Item[] = [
        { label: '', kind: vscode.QuickPickItemKind.Separator, act: 'reload' },
        { label: '$(search) ' + L.t('Search all folders'), description: L.t('by name, with the path'), act: 'all' },
        { label: '$(refresh) ' + L.t('Reload the list'), description: L.t('after making a collection in Zotero'), act: 'reload' },
        { label: '$(question) ' + L.t('How to make a new collection'), act: 'howto' },
        ...(opts.current ? [{ label: '$(close) ' + L.t('Unlink'), description: byKey.get(opts.current)?.path ?? '', act: 'unlink' } as Item] : []),
    ];

    const qp = vscode.window.createQuickPick<Item>();
    qp.matchOnDescription = true;
    qp.placeholder = opts.hint;
    let at = '';            // 開いているフォルダ（'' はいちばん上）
    let flat = false;       // すべてのフォルダをパスつきで並べている
    const render = (): void => {
        const here = byKey.get(at);
        qp.title = `${opts.title} — ${flat ? L.t('all folders') : here ? here.path : L.t('My Library')}`;
        qp.buttons = at || flat ? [vscode.QuickInputButtons.Back] : [];
        qp.value = '';
        if (flat) {
            qp.items = cols.map((c) => ({ ...folderItem(c, c.path), act: 'pick' as const, label:
                (c.key === opts.current ? '$(pass-filled) ' : '$(folder) ') + c.path }));
            return;
        }
        const suggested = !at ? (opts.suggested ?? []).map((k) => byKey.get(k)).filter((c): c is ZoteroCollection => !!c) : [];
        qp.items = [
            ...(here ? [
                { label: '$(arrow-up) ' + L.t('Up'), act: 'up' } as Item,
                { label: '$(check) ' + L.t('Use this folder: {0}', here.name), description: describe(here), act: 'use', key: here.key } as Item,
                { label: L.t('Folders inside'), kind: vscode.QuickPickItemKind.Separator, act: 'open' } as Item,
            ] : []),
            ...(suggested.length ? [
                { label: L.t('The Octavo project'), kind: vscode.QuickPickItemKind.Separator, act: 'open' } as Item,
                ...suggested.map((c) => folderItem(c, c.path)),
                { label: L.t('Collections in Zotero'), kind: vscode.QuickPickItemKind.Separator, act: 'open' } as Item,
            ] : []),
            ...children(at).map((c) => folderItem(c)),
            ...tail,
        ];
    };
    render();
    return new Promise<Browse | undefined>((resolve) => {
        let done = false;
        const finish = (r: Browse | undefined): void => {
            if (!done) {
                done = true;
                resolve(r);
                qp.hide();
            }
        };
        qp.onDidTriggerButton(() => {
            if (flat) {
                flat = false;
            } else {
                at = parent.get(at) ?? '';
            }
            render();
        });
        qp.onDidAccept(() => {
            const item = qp.selectedItems[0] ?? qp.activeItems[0];
            if (!item) {
                return;
            }
            switch (item.act) {
                case 'open': at = item.key ?? ''; render(); return;
                case 'up': at = parent.get(at) ?? ''; render(); return;
                case 'all': flat = true; render(); return;
                case 'pick':
                case 'use': finish({ kind: 'pick', key: item.key ?? '' }); return;
                case 'reload': finish({ kind: 'reload' }); return;
                case 'howto': finish({ kind: 'howto' }); return;
                case 'unlink': finish({ kind: 'unlink' }); return;
            }
        });
        qp.onDidHide(() => {
            finish(undefined);
            qp.dispose();
        });
        qp.show();
    });
}
