"""Safe HTML folder pages. Legacy notes are embedded byte-for-byte as base64."""
import base64
import html
import json
from pathlib import Path
from fis.fingerprint import sha256_file
from fis.index import digest


def legacy_notes(folder):
    notes = []
    for p in sorted(Path(folder).glob('*.fisnote')):
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise PermissionError('Legacy note is a link: '+str(p))
        data = p.read_bytes()
        notes.append({'path': str(p), 'sha256': sha256_file(p),
                      'base64': base64.b64encode(data).decode('ascii'),
                      'text': data.decode('utf-8', errors='replace'),
                      'mtime_ns': p.stat().st_mtime_ns, 'atime_ns': p.stat().st_atime_ns})
    return notes


def render(folder, rows, notes, template='fable', run='pending'):
    e = html.escape
    payload = {'schema': 'fis.html.v1', 'folder': str(folder), 'template': template,
               'run': run, 'files': rows, 'legacy': notes}
    # Escaping < prevents script element termination even in hostile filenames or legacy notes.
    island = json.dumps(payload, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    entries = ''.join('<tr id="file-'+r['id']+'"><td>'+e(Path(r['path']).name)+
                      '</td><td>'+e(r['classification']['class'])+'</td><td>'+e(', '.join(t['tag'] for t in r['tags']))+
                      '</td><td><details><summary>Why</summary><pre>'+e(json.dumps(r, indent=2))+'</pre></details></td></tr>' for r in rows)
    old = ''.join('<details><summary>Preserved note: '+e(Path(n['path']).name)+'</summary><pre>'+e(n['text'])+'</pre></details>' for n in notes)
    accent = {'fable': '#cb895e', 'vault': '#82b6a1', 'signals': '#98a9e8', 'compact': '#d2bd81', 'recovery': '#bd99c9', 'classic': '#a7b5bc'}.get(template, '#cb895e')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>FIS · '+e(Path(folder).name)+'</title><style>body{max-width:1100px;margin:48px auto;padding:24px;background:#151a1d;color:#e8e5de;font:16px system-ui}h1,h2{color:'+accent+'}table{width:100%;border-collapse:collapse}td,th{padding:12px;text-align:left;border-bottom:1px solid #39434a}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{margin:12px 0}.capsule{border-left:4px solid '+accent+';padding:20px;background:#20282c}</style>'
            '<h1>'+e(Path(folder).name)+'</h1><p>Your files, their meaning, and how to put everything back.</p>'
            '<section class="capsule"><h2>Semantic Capsule</h2><p>'+str(len(rows))+' files · template '+e(template)+
            ' · observations and proposals; authority unresolved.</p></section>'
            '<h2>Health</h2><p>Inventory recorded. Filename clues do not establish truth or canon.</p>'
            '<h2>Files Here</h2><table><tr><th>File</th><th>Class</th><th>Tags</th><th>Evidence</th></tr>'+entries+'</table>'
            '<h2>Child Folders</h2><p>See the selected-root index for child folder pages.</p>'
            '<h2>Folder Signals / Semantic Network</h2><p>Connections are proposals supported by the evidence above.</p>'
            '<h2>Preserved legacy notes</h2>'+old+'<h2>Recovery Contract</h2><p>Run '+e(run)+
            '. Rollback checks fingerprints before restoring paths. Original notes are archived, never deleted.</p>'
            '<script type="application/json" id="fis-data">'+island+'</script></html>')
