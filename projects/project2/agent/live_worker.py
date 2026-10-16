"""Internal one-attempt worker. Caller owns retries, budget and cancellation."""
import contextlib
import json
import os
import sys
import time
from pathlib import Path

from live_runtime import redact,write_json,provider_code,TRANSIENT


class RedactingLog:
    def __init__(self,path): self.path=path;self.pending=''
    def write(self,text):
        self.pending+=text
        while '\n' in self.pending:
            line,self.pending=self.pending.split('\n',1)
            with self.path.open('a') as f: f.write(redact(line)+'\n')
        return len(text)
    def flush(self):
        if self.pending:
            with self.path.open('a') as f: f.write(redact(self.pending))
            self.pending=''
    def isatty(self): return False


def main():
    request=json.loads(Path(sys.argv[1]).read_text());directory=Path(sys.argv[2])
    started=time.monotonic()
    log=RedactingLog(directory/'worker.log')
    def progress(stage,details):
        if stage=='draft_ready': write_json(directory/'draft.json',details)
        if stage=='evidence_ready': write_json(directory/'context.json',details)
        if stage=='tool_checks_ready': write_json(directory/'tool-checks.json',details)
        write_json(directory/'progress.json',{'stage':stage,'elapsed_seconds':time.monotonic()-started})
        with (directory/'stages.jsonl').open('a') as f:
            f.write(json.dumps({'stage':stage,'elapsed_seconds':time.monotonic()-started})+'\n')
    try:
        with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            if request['mode']=='diagnosis':
                from diagnosis_agent import run_live
                value=run_live(request['payload']['question'],progress=progress,tool_mode=request['options']['tool_mode'])
            else:
                from vision_agent import run
                value=run(request['payload']['image'],request['mode']=='unified',False,
                          request['payload'].get('question'),progress=progress,tool_mode=request['options']['tool_mode'])
        response={'ok':True,'result':value,'retryable':False}
    except (Exception,SystemExit) as error:
        code=provider_code(error)
        response={'ok':False,'error':redact(error),'error_type':type(error).__name__,
                  'status_code':code,'retryable':code in TRANSIENT}
    finally: log.flush()
    write_json(directory/'response.json',response)


if __name__=='__main__': main()
