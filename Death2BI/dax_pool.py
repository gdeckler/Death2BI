"""Bounded, supervised DAX processes. IPC is private to the parent and its children."""
from dataclasses import dataclass
import json
import logging
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import uuid


class DaxPoolError(RuntimeError):
    def __init__(self,message,status=503):
        super().__init__(message);self.status=status


@dataclass(frozen=True)
class PoolSettings:
    workers:int=2
    queue_size:int=32
    queue_seconds:float=120
    threads:int=1
    recycle:int=100
    hard_grace:float=35  # Includes startup and the existing 30-second RLS setup budget.

    @classmethod
    def from_env(cls):
        def integer(name,default,low,high):
            try:value=int(os.environ.get(name,str(default)))
            except ValueError:raise ValueError(name+' must be an integer.') from None
            if not low<=value<=high:raise ValueError(f'{name} must be between {low} and {high}.')
            return value
        cpus=getattr(os,'process_cpu_count',os.cpu_count)() or 2
        return cls(workers=integer('D2BI_DAX_WORKERS',min(2,cpus),1,8),
                   queue_size=integer('D2BI_DAX_QUEUE_SIZE',32,0,256),
                   queue_seconds=integer('D2BI_DAX_QUEUE_SECONDS',120,1,300),
                   threads=integer('D2BI_DAX_THREADS',1,1,8))


def _evaluate(job):
    # Import once in each spawned interpreter, never inherit an open connection.
    from dax_engine import evaluate_visual
    from model_recovery import unavailable_table_error
    import duckdb
    from rls import connect
    seconds,steps=job['limits']
    os.environ['D2PBI_DAX_SECONDS']=str(seconds)
    os.environ['D2PBI_DAX_STEPS']=str(steps)
    con=connect(job['path'],job['model'],job['effective'],threads=job['threads'])
    timer=threading.Timer(seconds+2,con.interrupt);timer.daemon=True;timer.start()
    try:return evaluate_visual(con,job['model'],job['payload'])
    except duckdb.CatalogException as error:
        raise unavailable_table_error(error,job['model']) from None
    finally:timer.cancel();con.close()


class _Transport:
    """Private anonymous OS pipes; no listeners, named pipes or network credentials."""
    def __init__(self,reader,writer):self.reader=reader;self.writer=writer

    def send(self,value):
        from decimal import Decimal
        def scalar(v):return float(v) if isinstance(v,Decimal) and v.is_finite() else None if isinstance(v,Decimal) else str(v)
        self.writer.write(json.dumps(value,default=scalar,ensure_ascii=True)+'\n');self.writer.flush()

    def recv(self):
        line=self.reader.readline()
        if not line:raise EOFError()
        return json.loads(line)

    def close(self):self.reader.close();self.writer.close()


def worker_main(pipe=None):
    pipe=pipe or _Transport(sys.stdin,sys.stdout)
    # Ctrl+C belongs to the server; it closes this pool before exiting.
    signal.signal(signal.SIGINT,signal.SIG_IGN)
    try:
        while True:
            try:job=pipe.recv()
            except EOFError:break
            if job is None:break
            start=time.monotonic()
            try:reply={'ok':True,'result':_evaluate(job)}
            except Exception as error:reply={'ok':False,'error':str(error),'status':getattr(error,'status',400)}
            reply.update(pid=os.getpid(),elapsed=time.monotonic()-start)
            pipe.send(reply)
    finally:pipe.close()


class _Slot:
    def __init__(self,command):
        self.command=command;self.lock=threading.Lock()
        self.process=None;self.pipe=None;self.completed=0;self.closed=False
        self.stderr_lock=threading.Lock();self.stderr_tail='';self.stderr_thread=None

    def _drain_stderr(self,stream):
        # Never allow native diagnostics to fill the pipe and deadlock a job.
        # Retain only a bounded private tail; raw text never enters API replies.
        try:
            while chunk:=stream.read(1024):
                with self.stderr_lock:self.stderr_tail=(self.stderr_tail+chunk)[-8192:]
        except (OSError,ValueError):pass

    def failure(self,error):
        process=self.process
        if process:
            try:code=process.wait(.2)
            except subprocess.TimeoutExpired:code=process.poll()
        else:code=None
        if self.stderr_thread:self.stderr_thread.join(.2)
        with self.stderr_lock:tail=self.stderr_tail
        windows=(code&0xffffffff) if code is not None else None
        native={0xc0000005:'native access violation',0xc0000017:'native memory allocation failure',
                0xc00000fd:'native stack overflow',0xc0000374:'native heap corruption',0xc0000409:'native fail-fast termination'}
        reason=native.get(windows)
        if reason is None:
            reason={-11:'native segmentation fault',-6:'native abort',-9:'worker was killed'}.get(code)
        if reason is None:reason='invalid worker response' if isinstance(error,(json.JSONDecodeError,UnicodeError)) else 'worker ended without a response' if code==0 else 'worker exited unexpectedly' if code is not None else 'worker communication failed'
        result={'workerPid':process.pid if process else None,'exitCode':code,'reason':reason}
        if windows in native:result['exitCodeHex']='0x'+format(windows,'08X')
        logging.getLogger(__name__).error('DAX worker failure: pid=%s exit=%s reason=%s transport=%s; private stderr tail:\n%s',
            result['workerPid'],result.get('exitCodeHex',code),reason,type(error).__name__,tail)
        return result

    def _stop(self):
        process=self.process
        if process:
            if process.poll() is None:process.terminate()
            try:process.wait(1)
            except subprocess.TimeoutExpired:process.kill();process.wait(2)
        if self.pipe:self.pipe.close();self.pipe=None
        if self.stderr_thread:self.stderr_thread.join(1);self.stderr_thread=None
        if process and process.stderr:process.stderr.close()
        self.process=None
        self.completed=0

    def start(self,recycle):
        with self.lock:
            if self.closed:raise DaxPoolError('The DAX pool is shutting down.')
            if self.process and (self.process.poll() is not None or self.completed>=recycle):self._stop()
            if not self.process:
                with self.stderr_lock:self.stderr_tail=''
                process=subprocess.Popen(self.command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    text=True,encoding='utf-8',errors='replace',bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),close_fds=True)
                self.process=process;self.pipe=_Transport(process.stdout,process.stdin)
                self.stderr_thread=threading.Thread(target=self._drain_stderr,args=(process.stderr,),daemon=True)
                self.stderr_thread.start()
            return self.pipe

    def stop(self,close=False):
        with self.lock:
            self.closed=self.closed or close;self._stop()

    def pid(self):
        with self.lock:return self.process.pid if self.process and self.process.poll() is None else None


class DaxProcessPool:
    def __init__(self,settings=None,*,worker_command=None):
        self.settings=settings or PoolSettings.from_env()
        # Fresh interpreters on Windows AND Linux; no forked server connections.
        command=worker_command or [sys.executable,'-X','utf8','-X','faulthandler',os.path.abspath(__file__),'--worker']
        self.slots=[_Slot(command) for _ in range(self.settings.workers)]
        self.free=queue.Queue()
        for slot in self.slots:self.free.put(slot)
        self.admission=threading.BoundedSemaphore(self.settings.workers+self.settings.queue_size)
        self.lock=threading.Lock();self.closed=threading.Event();self.jobs={};self.cancelled_before_start={}
        self.counts={key:0 for key in ('submitted','completed','failed','cancelled','timedOut','rejected')}
        self.last_worker_failure=None

    def status(self):
        with self.lock:
            result={**self.counts,'running':sum(j['state']=='running' for j in self.jobs.values()),
                    'queued':sum(j['state']=='queued' for j in self.jobs.values()),
                    'lastWorkerFailure':dict(self.last_worker_failure) if self.last_worker_failure else None}
        return {**result,'workers':self.settings.workers,'queueCapacity':self.settings.queue_size,
                'queueLimitSeconds':self.settings.queue_seconds,'duckdbThreadsPerWorker':self.settings.threads,
                'workerPids':[pid for slot in self.slots if (pid:=slot.pid())], 'closed':self.closed.is_set()}

    @staticmethod
    def request_id(value):
        if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):raise DaxPoolError('Invalid DAX request ID.',400)
        return value

    def cancel(self,owner,request_id):
        key=(owner,self.request_id(request_id));now=time.monotonic()
        with self.lock:
            if key in self.jobs:self.jobs[key]['cancel'].set();return True
            # An abort may reach the server before the original HTTP request.
            self.cancelled_before_start={k:t for k,t in self.cancelled_before_start.items() if t>now}
            if len(self.cancelled_before_start)>=1024:self.cancelled_before_start.pop(next(iter(self.cancelled_before_start)))
            self.cancelled_before_start[key]=now+60
        return False

    def run(self,prepare,owner,request_id=None):
        key=(owner,self.request_id(request_id) if request_id else uuid.uuid4().hex)
        cancel=threading.Event();slot=None;admitted=False;discard=False;io_thread=None
        queued_at=time.monotonic();wait_deadline=queued_at+self.settings.queue_seconds
        with self.lock:
            if self.closed.is_set():raise DaxPoolError('The DAX pool is shutting down.')
            if key in self.jobs:raise DaxPoolError('This DAX request is already pending.',409)
            if self.cancelled_before_start.pop(key,0)>queued_at:cancel.set()
            self.jobs[key]={'cancel':cancel,'state':'queued'}
        try:
            admitted=self.admission.acquire(blocking=False)
            if not admitted:
                with self.lock:self.counts['rejected']+=1
                raise DaxPoolError('The DAX calculation queue is full. Retry shortly.')
            with self.lock:self.counts['submitted']+=1
            while slot is None:
                self._check(cancel)
                if time.monotonic()>wait_deadline:raise DaxPoolError('DAX queue wait limit exceeded. Retry shortly.')
                try:slot=self.free.get(timeout=.05)
                except queue.Empty:pass
            self._check(cancel)
            # Authorization/RLS is resolved AFTER waiting, immediately before dispatch.
            job=prepare() if callable(prepare) else prepare
            self._check(cancel)
            job={**job,'threads':self.settings.threads}
            queued_seconds=time.monotonic()-queued_at;started=time.monotonic()
            deadline=started+job['limits'][0]+self.settings.hard_grace
            pipe=slot.start(self.settings.recycle);discard=True;replies=queue.Queue(maxsize=1)
            with self.lock:self.jobs[key]['state']='running'
            # Supervise IPC too: a blocked pipe or native crash must not hang the HTTP thread.
            def exchange():
                try:pipe.send(job);replies.put((True,pipe.recv()))
                except Exception as error:replies.put((False,error))
            io_thread=threading.Thread(target=exchange,daemon=True);io_thread.start()
            while True:
                self._check(cancel)
                if time.monotonic()>deadline:
                    with self.lock:self.counts['timedOut']+=1
                    raise DaxPoolError('DAX worker exceeded its hard time limit and was replaced.',504)
                try:ok,reply=replies.get(timeout=.05)
                except queue.Empty:continue
                self._check(cancel)
                if not ok:
                    failure=slot.failure(reply)
                    with self.lock:self.last_worker_failure=failure
                    code=failure.get('exitCodeHex',failure['exitCode'])
                    detail=failure['reason']+(' ('+str(code)+')' if code is not None else '')
                    raise DaxPoolError('The DAX worker stopped unexpectedly: '+detail+'. Retry the visual; its worker will be replaced.') from None
                discard=False;slot.completed+=1
                if not reply['ok']:raise DaxPoolError(reply['error'],reply.get('status',400))
                result=reply['result']
                result.setdefault('evaluation',{}).update(executionMode='process pool',workerPid=reply['pid'],
                    queueSeconds=round(queued_seconds,3),workerElapsedSeconds=round(reply['elapsed'],3),
                    workerProcesses=self.settings.workers,duckdbThreads=self.settings.threads)
                with self.lock:self.counts['completed']+=1
                return result
        except Exception as error:
            with self.lock:self.counts['cancelled' if isinstance(error,DaxPoolError) and error.status==499 else 'failed']+=1
            raise
        finally:
            if slot:
                if discard:slot.stop()
                if io_thread:io_thread.join(1)
                if not self.closed.is_set():self.free.put(slot)
            if admitted:self.admission.release()
            with self.lock:self.jobs.pop(key,None)

    def _check(self,cancel):
        if self.closed.is_set():raise DaxPoolError('The DAX pool is shutting down.')
        if cancel.is_set():raise DaxPoolError('DAX request cancelled.',499)

    def close(self):
        with self.lock:
            self.closed.set()
            for job in self.jobs.values():job['cancel'].set()
        for slot in self.slots:slot.stop(close=True)


if __name__=='__main__':
    if sys.argv[1:]!=['--worker']:raise SystemExit('DAX workers are started by the application server.')
    worker_main()
