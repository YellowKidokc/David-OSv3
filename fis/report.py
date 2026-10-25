"""Portable HTML/CSV reports, without changing source folders."""
import csv
import html
import io
import json


def export(plan, format='html'):
    if format == 'csv':
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(['id', 'kind', 'source', 'proposed', 'why', 'flag'])
        for row in plan['rows']:
            cells = [row['id'], row['kind'], row['path'], row.get('target', 'HTML sidecar'), json.dumps(row['why']), row['flag']]
            writer.writerow(["'"+v if v.startswith(('=', '+', '-', '@')) else v for v in cells])
        return stream.getvalue()
    return '<!doctype html><meta charset="utf-8"><title>FIS Plan</title><h1>What will change</h1><p>Plan '+html.escape(plan['hash'])+'</p><pre>'+html.escape(json.dumps(plan, indent=2))+'</pre>'
