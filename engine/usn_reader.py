"""Read-only NTFS USN V2 journal prototype. Never creates/deletes a journal."""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import json
import os
import struct
import subprocess
import re
from collections import Counter
from pathlib import Path

from engine import registry

QUERY=0x000900F4
READ=0x000900BB
REASONS={0x100:'create',0x200:'delete',0x1000:'rename_old',0x2000:'rename_new',
         1:'data_overwrite',2:'data_extend',4:'data_truncate'}


def parse_buffer(data):
    if len(data)<8:raise ValueError('Truncated journal buffer')
    next_usn=struct.unpack_from('<q',data)[0];offset=8;records=[]
    while offset<len(data):
        if len(data)-offset<60:raise ValueError('Truncated USN record')
        values=struct.unpack_from('<IHHQQqqIIIIHH',data,offset)
        length,major,minor,frn,parent,usn,timestamp,reason,source,security,attributes,name_length,name_offset=values
        if length<60 or offset+length>len(data) or major!=2:raise ValueError('Unsupported or malformed USN record; checkpoint held')
        if name_length%2 or name_offset<60 or name_offset+name_length>length:raise ValueError('Invalid USN filename bounds')
        name=data[offset+name_offset:offset+name_offset+name_length].decode('utf-16-le')
        time=dt.datetime(1601,1,1,tzinfo=dt.timezone.utc)+dt.timedelta(microseconds=timestamp//10)
        records.append({'usn':usn,'frn':str(frn),'parent_frn':str(parent),'name':name,'at':time.isoformat(),
                        'reason':reason,'actions':[label for bit,label in REASONS.items() if reason&bit],
                        'is_directory':bool(attributes&0x10),'record_version':major})
        offset+=length
    return next_usn,records


def events(records,pending=None):
    pending=dict(pending or {});result=[]
    for row in records:
        frn=row['frn']
        for action in row['actions']:
            if action=='rename_old':
                if frn in pending:result.append({**pending[frn],'event':'unpaired_rename_old'})
                pending[frn]=row
            elif action=='rename_new':
                old=pending.pop(frn,None)
                if old:
                    result.append({**row,'event':'move' if old['parent_frn']!=row['parent_frn'] else 'rename',
                                   'old_name':old['name'],'old_parent_frn':old['parent_frn'],'old_usn':old['usn']})
                else:result.append({**row,'event':'unpaired_rename_new'})
            else:result.append({**row,'event':action})
    return result,pending


def validate_checkpoint(checkpoint,journal,volume):
    if checkpoint.get('volume')!=volume:raise ValueError('Checkpoint volume mismatch')
    if checkpoint['journal_id']!=journal['journal_id']:raise ValueError('Journal ID changed; continuity lost, checkpoint held')
    if not journal['first_usn']<=checkpoint['next_usn']<=journal['next_usn']:
        raise ValueError('Checkpoint outside retained journal range; gap or rollback detected')


class Volume:
    def __init__(self,volume='C:'):
        if os.name!='nt':raise OSError('Windows NTFS volume required')
        if volume.upper()!='C:':raise ValueError('Prototype is limited to C:')
        self.volume=volume.upper()
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        from ctypes import wintypes
        self.kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        self.kernel.CreateFileW.restype=wintypes.HANDLE
        self.kernel.DeviceIoControl.argtypes=[wintypes.HANDLE,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
        self.kernel.DeviceIoControl.restype=wintypes.BOOL
        self.kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        self.handle=self.kernel.CreateFileW('\\\\.\\'+self.volume,0x80000000,7,None,3,0,None)
        if self.handle==ctypes.c_void_p(-1).value and ctypes.get_last_error()==5:
            # Retry with no data-read rights. Windows still decides whether the
            # read-only journal control code is permitted; no elevation attempted.
            self.handle=self.kernel.CreateFileW('\\\\.\\'+self.volume,0,7,None,3,0,None)
        if self.handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        self.kernel.CloseHandle(self.handle)

    def ioctl(self,code,data=b''):
        # Only read/query control codes are accepted. No journal mutation API.
        if code not in {QUERY,READ}:raise ValueError('Write control codes are prohibited')
        out=ctypes.create_string_buffer(1024*1024)
        written=ctypes.c_ulong()
        incoming=ctypes.create_string_buffer(data) if data else None
        if not self.kernel.DeviceIoControl(self.handle,code,incoming,len(data),out,len(out),ctypes.byref(written),None):
            raise ctypes.WinError(ctypes.get_last_error())
        return out.raw[:written.value]

    def query(self):
        try:
            raw=self.ioctl(QUERY)
        except OSError:
            # Querying the journal is permitted on some hosts where raw volume
            # handles are restricted. This fallback never reads or alters it.
            response=subprocess.run(['fsutil','usn','queryjournal',self.volume],capture_output=True,text=True,timeout=15)
            if response.returncode:raise OSError(response.stdout+response.stderr)
            fields={}
            for label,hexvalue in re.findall(r'^([^:\r\n]+):\s*(0x[0-9a-fA-F]+)',response.stdout,re.M):
                fields[label.strip().casefold()]=int(hexvalue,16)
            required={'journal_id':'usn journal id','first_usn':'first usn','next_usn':'next usn','lowest_valid_usn':'lowest valid usn','maximum_size':'maximum size'}
            if not all(label in fields for label in required.values()):raise ValueError('Unrecognized fsutil query format; no guessed checkpoint')
            return {key:fields[label] for key,label in required.items()}
        if len(raw)<56:raise ValueError('Truncated journal query')
        journal,first,next_usn,lowest,maximum,size,delta=struct.unpack_from('<QqqqqQQ',raw)
        return {'journal_id':journal,'first_usn':first,'next_usn':next_usn,'lowest_valid_usn':lowest,'maximum_size':size}

    def read(self,checkpoint,max_records=50000):
        if max_records<1:raise ValueError('Positive record limit required')
        journal=self.query();validate_checkpoint(checkpoint,journal,self.volume)
        cursor=checkpoint['next_usn'];end=journal['next_usn'];records=[];complete=True
        while cursor<end:
            # READ_USN_JOURNAL_DATA_V1, aligned to eight bytes, constrained to V2.
            request=struct.pack('<qIIQQQHH4x',cursor,0xffffffff,0,0,0,journal['journal_id'],2,2)
            following,batch=parse_buffer(self.ioctl(READ,request))
            batch=[r for r in batch if r['usn']<end]
            room=max_records-len(records)
            if len(batch)>room:
                records+=batch[:room];cursor=batch[room]['usn'];complete=False;break
            records+=batch
            if following<=cursor:raise ValueError('Journal stopped before captured end; checkpoint held')
            cursor=min(following,end)
            if len(records)>=max_records and cursor<end:complete=False;break
        result,pending=events(records,checkpoint.get('pending_renames'))
        return {'status':'pass' if complete else 'partial','volume':self.volume,'journal':journal,
                'checkpoint_used':checkpoint,'next_checkpoint':{'volume':self.volume,'journal_id':journal['journal_id'],'next_usn':cursor,'pending_renames':pending},
                'records_read':len(records),'events':result,'summary':dict(Counter(r['event'] for r in result)),
                'source_actions_taken':False,'path_resolution':'filename + parent FRN only; full historical paths are not reconstructed',
                'pending_rename_count':len(pending)}


def report(checkpoint_path,output,*,initialize=False,max_records=50000,advance=False):
    checkpoint_path=Path(checkpoint_path);output=Path(output)
    if checkpoint_path.resolve()==output.resolve() or checkpoint_path.resolve().is_relative_to(output.resolve()):raise ValueError('Checkpoint and output must be separate files')
    output.mkdir(parents=True,exist_ok=True)
    volume=None
    try:
        volume=Volume()
        if initialize:
            if checkpoint_path.exists():raise ValueError('Existing checkpoint will not be overwritten by initialization')
            journal=volume.query()
            checkpoint={'volume':'C:','journal_id':journal['journal_id'],'next_usn':journal['next_usn'],'pending_renames':{}}
            checkpoint_path.parent.mkdir(parents=True,exist_ok=True)
            with checkpoint_path.open('x',encoding='utf-8') as out:json.dump(checkpoint,out,indent=2)
            result={'status':'baseline','checkpoint':checkpoint,'historical_coverage':'No prior checkpoint supplied; baseline starts now. No earlier changes claimed.','source_actions_taken':False}
        else:
            checkpoint=json.loads(checkpoint_path.read_text(encoding='utf-8'))
            result=volume.read(checkpoint,max_records)
        registry.write_if_changed(output/'report.json',registry.dump(result))
        rows=['# C: USN journal — read-only report','',f"Status: {result['status']}",'','No source actions taken.']
        if initialize:rows+=['',result['historical_coverage']]
        else:
            rows+=['',result['path_resolution'],'',f"Records: {result['records_read']}; events: {registry.dump(result['summary'])}",'','| Event | Name | Previous name | Parent FRN | USN |','|---|---|---|---|---|']
            for event in result['events']:
                clean=lambda v:str(v).replace('|','\\|').replace('\n',' ')
                rows.append('| '+' | '.join(clean(event.get(k,'')) for k in ('event','name','old_name','parent_frn','usn'))+' |')
        registry.write_if_changed(output/'REPORT.md','\n'.join(rows)+'\n')
        if advance and not initialize:
            # Advance only after reports exist, and only for complete coverage.
            if result['status']!='pass':raise ValueError('Partial read; checkpoint not advanced')
            registry.write_if_changed(checkpoint_path.with_suffix('.previous.json'),registry.dump(checkpoint))
            checkpoint_path.write_text(registry.dump(result['next_checkpoint']),encoding='utf-8')
        return result
    except (OSError,ValueError) as error:
        result={'status':'hold','error':str(error),'source_actions_taken':False,'checkpoint_advanced':False}
        registry.write_if_changed(output/'report.json',registry.dump(result))
        registry.write_if_changed(output/'REPORT.md','# C: USN journal — HOLD\n\n'+str(error)+'\n\nNo source actions taken; checkpoint not advanced.\n')
        return result
    finally:
        if volume:volume.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--initialize',action='store_true');parser.add_argument('--advance',action='store_true');parser.add_argument('--max-records',type=int,default=50000)
    args=parser.parse_args();result=report(args.checkpoint,args.output,initialize=args.initialize,max_records=args.max_records,advance=args.advance)
    print(registry.dump({k:v for k,v in result.items() if k!='events'}))
    raise SystemExit(0 if result['status']!='hold' else 2)
