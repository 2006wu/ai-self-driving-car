"""Bounded CLI execution, redacted records and SDK configuration; no live calls here."""
import ast
import hashlib
import json
import os
import random
import re
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from zoneinfo import ZoneInfo

HERE=Path(__file__).resolve().parent
TRANSIENT={408,429,500,502,503,504}


def redact(value):
    text=str(value)
    for name in ('GOOGLE_API_KEY','GEMINI_API_KEY'):
        secret=os.environ.get(name)
        if secret: text=text.replace(secret,'[REDACTED]')
    return re.sub(r'AIza[0-9A-Za-z_-]{20,}', '[REDACTED]', text)


def safe_value(value):
    if isinstance(value,str): return redact(value)
    if isinstance(value,dict): return {redact(k):safe_value(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [safe_value(v) for v in value]
    return value


def write_json(path,value):
    path=Path(path)
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(safe_value(value),indent=2,allow_nan=False))
    temporary.chmod(0o600)
    temporary.replace(path)


def provider_code(value):
    """Only structured status codes qualify for retry; do not guess from prose."""
    code=getattr(value,'status_code',None) or getattr(value,'code',None)
    if type(code) is int: return code
    if isinstance(value,dict):
        code=value.get('code') or value.get('status_code')
        if type(code) is int: return code
        return provider_code(value.get('error')) if value.get('error') is not None else None
    if isinstance(value,str):
        for parser in (json.loads,ast.literal_eval):
            try:
                parsed=parser(value)
            except (ValueError,SyntaxError,TypeError): continue
            if isinstance(parsed,dict): return provider_code(parsed)
    return None


class ProviderRunError(RuntimeError):
    def __init__(self,message,content=None):
        super().__init__(message)
        self.status_code=provider_code(content)


def configured_model():
    from agno.models.google import Gemini
    from model_config import runtime_model_id
    # Disable SDK/Agno hidden retries. CLI supervisor alone owns whole-run retries.
    timeout=float(os.environ.get('P2_AGENT_HTTP_TIMEOUT','45'))
    if not 0 < timeout <= 300: raise ValueError('HTTP timeout must be in (0,300] seconds')
    return Gemini(id=runtime_model_id(),retries=0,retry_with_guidance=False,
        client_params={'http_options':{'timeout':int(timeout*1000),'retry_options':{'attempts':1}}})


def notify(callback,stage,**details):
    if callback: callback(stage,details)


def tool_audit(result):
    audit=[]
    for tool in (getattr(result,'tools',None) or []):
        payload=getattr(tool,'result',None)
        raw=json.dumps(payload,sort_keys=True,default=str).encode() if payload is not None else None
        audit.append({'name':tool.tool_name,'error':bool(tool.tool_call_error),
            'execution_evidence':'RESULT_RECORDED' if raw is not None else 'NO_RESULT_RECORDED',
            'result_sha256':hashlib.sha256(raw).hexdigest() if raw is not None else None,
            'result_bytes':len(raw) if raw is not None else None})
    return audit


def verify_tool_mode(result,mode,required):
    if mode not in ('preload','verify'): raise ValueError('Unknown tool mode')
    actual={t.tool_name for t in (getattr(result,'tools',None) or [])
            if not t.tool_call_error and getattr(t,'result',None) is not None}
    if mode=='verify' and not set(required).issubset(actual):
        raise RuntimeError('Agent verification incomplete; missing successful tools: '+', '.join(sorted(set(required)-actual)))
    if mode=='verify' and 'check_diagnostic_claim' in required:
        claim_checked=any(t.tool_name=='check_diagnostic_claim' and not t.tool_call_error
            and getattr(t,'result',None) is not None
            and isinstance(getattr(t,'tool_args',None),dict)
            and t.tool_args.get('claim_id')=='overfitting' for t in (getattr(result,'tools',None) or []))
        if not claim_checked: raise RuntimeError('Agent verification incomplete; overfitting claim check not demonstrated')
    return {'mode':mode,'successful_model_tools':sorted(actual),
            'status':'RECORDED' if actual else 'NOT_DEMONSTRATED',
            'note':'Local preflight readers are separate from model-issued function calls; '
                   'selection policy is recorded separately.'}


def collect_verification_tools(functions, progress=None):
    """Protocol-directed model function calls, separate from final structured output.

    The application selects required tools; this is not autonomous tool selection.
    No local direct-call fallback can satisfy the execution audit.
    """
    from agno.agent import Agent
    from agno.tools import tool
    from agno.run.agent import RunStatus
    from types import SimpleNamespace
    executions=[]
    for function in functions:
        name=function.__name__
        notify(progress,'checking_tool_'+name)
        agent=Agent(model=configured_model(),tools=[tool(stop_after_tool_call=True)(function)],
                    tool_choice='any',tool_call_limit=1,retries=0,
                    instructions=['Call the single registered read-only evidence tool once. '
                                  'For check_diagnostic_claim use claim_id="overfitting".'])
        result=agent.run('Retrieve the evidence with '+name+'. Do not write a final report.')
        executions.extend(getattr(result,'tools',None) or [])
        notify(progress,'tool_checks_ready',tools=tool_audit(SimpleNamespace(tools=executions)))
        if result.status != RunStatus.completed:
            raise ProviderRunError('Verification tool request did not complete: '+name,result.content)
        verify_tool_mode(result,'verify',[name])
    return executions


def verification_context(executions):
    return {'protocol':'Application-selected required checks; model-issued function calls, '
                        'not autonomous tool selection.',
            'results':[{'name':t.tool_name,'result':t.result} for t in executions]}


def add_options(parser):
    parser.add_argument('--model',help='Override GEMINI_MODEL_ID for this run only')
    parser.add_argument('--timeout',type=float,default=300,help='Total local wall-clock budget, seconds (default 300)')
    parser.add_argument('--attempt-timeout',type=float,default=120,help='Max seconds per worker attempt (default 120)')
    parser.add_argument('--request-timeout',type=float,default=45,help='SDK HTTP timeout seconds (default 45)')
    parser.add_argument('--retries',type=int,default=1,help='Additional transient retries, 0–3 (default 1)')
    parser.add_argument('--progress-every',type=float,default=10,help='Heartbeat interval seconds')
    parser.add_argument('--output-dir',type=Path,default=HERE/'artifacts/live-runs',help='Parent directory for a unique run record')
    parser.add_argument('--json',action='store_true',help='Print full result JSON instead of concise Markdown')
    parser.add_argument('--tool-mode',choices=['preload','verify'],default='preload',help='preload: evidence-grounded summary; verify: require model-selected checks')


def validate_options(args):
    if not all(0 < v <= 3600 for v in (args.timeout,args.attempt_timeout,args.progress_every)):
        raise ValueError('Timeouts/progress interval must be in (0,3600] seconds')
    if not 0 < args.request_timeout <= 300 or not 0 <= args.retries <= 3:
        raise ValueError('request timeout must be (0,300]; retries must be 0–3')
    if args.model is not None and not args.model.strip(): raise ValueError('--model cannot be empty')


def stop_process(process):
    if process.poll() is not None: return
    try: os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError: return
    try: process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait(timeout=1)


def provenance():
    return {'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*.py'))},
        'python':sys.version.split()[0], 'packages':{name:version(name) for name in ('agno','google-genai','pydantic')},
        'git_head':subprocess.run(['git','rev-parse','HEAD'],cwd=HERE,capture_output=True,text=True).stdout.strip()}


def execute_job(mode,payload,args,*,worker=None,require_key=True):
    """Subprocess isolation permits enforced local cancellation and no overlap."""
    validate_options(args)
    if require_key and not os.environ.get('GOOGLE_API_KEY'):
        raise RuntimeError('GOOGLE_API_KEY is not inherited; no API request made.')
    from model_config import runtime_model_id
    model=args.model.strip() if args.model else runtime_model_id()
    stamp=datetime.now(ZoneInfo('Asia/Taipei')).strftime('%Y%m%d-%H%M%S')
    directory=args.output_dir.resolve()/f'{stamp}-{mode}-{uuid.uuid4().hex[:8]}'
    directory.mkdir(parents=True,exist_ok=False,mode=0o700)
    options={name:getattr(args,name) for name in ('timeout','attempt_timeout','request_timeout','retries','progress_every','tool_mode')}
    request={'mode':mode,'model':model,'payload':payload,'options':options}
    write_json(directory/'request.json',request)
    record={'mode':mode,'model':model,'status':'RUNNING','created_at':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
            'configuration':options,'provenance':provenance(),'attempts':[], 'run_directory':str(directory),
            'content_acceptance':'HUMAN_CONTENT_REVIEW_REQUIRED'}
    started=time.monotonic();process=None;result=None
    def event(stage,**details):
        item={'elapsed_seconds':round(time.monotonic()-started,3),'stage':stage,**details}
        with (directory/'events.jsonl').open('a') as f: f.write(json.dumps(safe_value(item))+'\n')
        print(f"[{item['elapsed_seconds']:.0f}s] {stage}"+(f" | {details['message']}" if 'message' in details else ''),file=sys.stderr,flush=True)
    print(f'Model: {model}\nRecords: {directory}',file=sys.stderr,flush=True)
    deadline=started+args.timeout
    write_json(directory/'run.json',record)
    try:
        for attempt in range(1,args.retries+2):
            if time.monotonic()>=deadline: raise TimeoutError('Total time budget exhausted')
            attempt_dir=directory/f'attempt-{attempt}';attempt_dir.mkdir(mode=0o700)
            command=[sys.executable,str(worker or HERE/'live_worker.py'),str(directory/'request.json'),str(attempt_dir)]
            env=os.environ.copy();env['GEMINI_MODEL_ID']=model;env['P2_AGENT_HTTP_TIMEOUT']=str(args.request_timeout)
            process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env,start_new_session=True)
            attempt_start=time.monotonic();attempt_deadline=min(deadline,attempt_start+args.attempt_timeout)
            last_stage=None;next_heartbeat=attempt_start+args.progress_every
            event('attempt_started',attempt=attempt,message=f'{attempt}/{args.retries+1}')
            timed_out=False
            while process.poll() is None:
                now=time.monotonic()
                if now>=attempt_deadline:
                    stop_process(process);timed_out=True;break
                progress=attempt_dir/'progress.json'
                if progress.exists():
                    state=json.loads(progress.read_text())
                    if state['stage']!=last_stage:
                        last_stage=state['stage'];event(last_stage,attempt=attempt)
                if now>=next_heartbeat:
                    event('waiting',attempt=attempt,message=f"{last_stage or 'starting'}; attempt elapsed {now-attempt_start:.0f}s")
                    next_heartbeat=now+args.progress_every
                try: process.wait(timeout=min(.2,max(.001,attempt_deadline-now)))
                except subprocess.TimeoutExpired: pass
            if not timed_out and time.monotonic()>=attempt_deadline:
                stop_process(process);timed_out=True
            response_path=attempt_dir/'response.json'
            if timed_out:
                response={'ok':False,'error':'Attempt timed out; local worker terminated','retryable':True,'status_code':None}
            elif response_path.exists(): response=json.loads(response_path.read_text())
            else: response={'ok':False,'error':f'Worker exited without result (exit {process.returncode})','retryable':False}
            summary={k:v for k,v in response.items() if k!='result'}
            summary.update(attempt=attempt,elapsed_seconds=round(time.monotonic()-attempt_start,3))
            record['attempts'].append(summary)
            write_json(directory/'run.json',record)
            if response.get('ok'):
                result=response['result'];write_json(directory/'result.json',result)
                record['status']='COMPLETED';event('completed');break
            failure=response.get('error','unknown error')
            if response.get('status_code') is not None: failure=f"HTTP {response['status_code']}: {failure}"
            event('attempt_failed',attempt=attempt,message=redact(failure))
            if not response.get('retryable') or attempt>args.retries:
                if timed_out: raise TimeoutError(response['error'])
                raise RuntimeError(failure)
            delay=min(2**attempt+random.uniform(0,.5),10)
            if time.monotonic()+delay>=deadline: raise TimeoutError('Total budget insufficient for another retry')
            event('retry_backoff',message=f'{delay:.1f}s; transient error; restarting whole read-only agent attempt')
            time.sleep(delay)
        if result is None: raise RuntimeError('No completed result')
        from report_output import format_report
        (directory/'report.md').write_text(redact(format_report(result)))
        return result,directory
    except KeyboardInterrupt:
        record['status']='CANCELLED';event('cancelled');raise
    except Exception as error:
        record['status']='TIMED_OUT' if isinstance(error,TimeoutError) else 'FAILED'
        record['error']=redact(error);event(record['status'].lower(),message=redact(error));raise
    finally:
        if process is not None: stop_process(process)
        record['elapsed_seconds']=round(time.monotonic()-started,3)
        write_json(directory/'run.json',record)
        files={str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest()
               for p in directory.rglob('*') if p.is_file() and p.name!='manifest.json'}
        write_json(directory/'manifest.json',{'algorithm':'SHA-256','files':files})


def print_result(result,directory,args):
    if args.json: print(json.dumps(safe_value(result),indent=2,allow_nan=False))
    else:
        from report_output import format_report
        print(format_report(result))
        print(f'\n完整結果與來源紀錄：{directory}')
