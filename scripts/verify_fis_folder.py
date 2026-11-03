"""Live local UI smoke check. --ask-live opts into one real DeepSeek call."""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.registry import sha256_file


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:28280/fis/')
    parser.add_argument('--ask-live',action='store_true')
    args=parser.parse_args()
    from playwright.sync_api import sync_playwright
    state=Path(os.environ['LOCALAPPDATA'])/'David-OS/FIS_FOLDER'
    config=json.loads((state/'config.json').read_text(encoding='utf-8'))
    pilot=next(h for h in config['hubs'] if h['id']=='canonical-rebuild')
    root=Path(pilot['root'])
    def sources():
        return {str(p.relative_to(root)):[sha256_file(str(p)),p.stat().st_mtime_ns] for p in root.rglob('*') if p.is_file()}
    before=sources()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        assert page.goto(args.url,wait_until='networkidle').status==200
        page.get_by_text('Connected to local service',exact=True).wait_for()
        page.screenshot(path=str(state/'dashboard-desktop.png'),full_page=True)
        page.get_by_role('link',name=re.compile('Canonical Rebuild')).first.click()
        page.get_by_role('heading',name=re.compile('Canonical Rebuild')).wait_for()
        rows=page.locator('.hub-row').count()
        page.get_by_role('button',name='Check for changes',exact=True).click()
        page.get_by_text('Done.',exact=True).wait_for(timeout=30000)
        page.locator('.hub-row button:not([disabled])').first.click()
        page.locator('#source-dialog').wait_for(state='visible')
        assert len(page.locator('#source-body').inner_text())>0
        page.get_by_role('button',name='Close',exact=True).click()
        page.get_by_role('searchbox',name='Find a file').fill('The First Reading')
        assert page.locator('.hub-row').count()==1
        page.get_by_role('searchbox',name='Find a file').fill('')
        page.screenshot(path=str(state/'folder-desktop.png'),full_page=True)
        ai_answer,ai_error=None,None
        if args.ask_live:
            page.get_by_role('textbox',name='Question for this folder').fill('In at most two sentences, state the supplied inventory file count and whether any source texts were provided. Do not infer document contents.')
            page.get_by_role('button',name='Ask DeepSeek',exact=True).click()
            page.locator('#answer:not(:empty), #message.error').first.wait_for(state='visible',timeout=120000)
            ai_answer=page.locator('#answer').inner_text()
            ai_error=page.locator('#message').inner_text() if page.locator('#message').get_attribute('class')=='error' else None
            page.screenshot(path=str(state/'folder-chat.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(state/'folder-mobile.png'),full_page=True)
        browser.close()
    after=sources()
    assert before==after
    receipt={'http_and_browser':'passed','page_errors':errors,'pilot_rows':rows,'source_bytes_and_mtimes_preserved':before==after,
             'ai_answer':ai_answer,'ai_error':ai_error,'url':args.url,'browser':'standalone headless Chromium; plugin browser unavailable'}
    (state/('acceptance-live-ai.json' if args.ask_live else 'acceptance.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    assert not errors
    if args.ask_live:
        assert ai_answer and not ai_error


if __name__=='__main__':
    main()
