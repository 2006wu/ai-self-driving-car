"""Minimal lifecycle adapter for exact uiview.py's process/cereal API.

Dependency injection only. No device discovery, SSH, new wire protocol, or real
OpenPilot imports. Hardware integration must supply version-matched bindings.
"""
import time
from types import SimpleNamespace as NS

SERVICES = ['controlsState', 'deviceState', 'pandaStates', 'carParams']
PROCESSES = ['camerad', 'ui', 'modeld', 'calibrationd']


def build_messages(messaging, log):
    messages = {s: messaging.new_message(s) for s in SERVICES if s != 'pandaStates'}
    messages['deviceState'].deviceState.started = True
    messages['carParams'].carParams.openpilotLongitudinalControl = True
    messages['pandaStates'] = messaging.new_message('pandaStates', 1)
    messages['pandaStates'].pandaStates[0].ignitionLine = True
    messages['pandaStates'].pandaStates[0].pandaType = log.PandaState.PandaType.uno
    return messages


def validate(messages):
    if set(messages) != set(SERVICES):
        raise ValueError('Run2 service set mismatch')
    if messages['deviceState'].deviceState.started is not True:
        raise ValueError('deviceState.started must be true')
    if messages['carParams'].carParams.openpilotLongitudinalControl is not True:
        raise ValueError('carParams longitudinal flag mismatch')
    pandas = messages['pandaStates'].pandaStates
    if len(pandas) != 1 or pandas[0].ignitionLine is not True:
        raise ValueError('expected one ignition panda')


def run_ui(bindings, ticks=5, retries=1, sleep=time.sleep):
    """Caller owns isolated/device-specific bindings. Bounded by default.

    Reconnect here means recreate publisher after send timeout/disconnect, not
    Wi-Fi recovery. Partial startup and any publishing failure stop owned procs.
    """
    if ticks < 1 or retries < 0:
        raise ValueError('ticks >= 1, retries >= 0 required')
    started, events = [], []
    try:
        bindings.params.put('CarParams', bindings.car.CarParams(notCar=True).to_bytes())
        for name in PROCESSES:
            process = bindings.processes[name]
            # Register before start so a partially successful start is cleaned up.
            started.append(process)
            process.start()
        messages = build_messages(bindings.messaging, bindings.log)
        validate(messages)
        publisher = bindings.messaging.PubMaster(SERVICES)
        for _ in range(ticks):
            sleep(.01)
            for service, message in messages.items():
                for attempt in range(retries + 1):
                    try:
                        publisher.send(service, message)
                        break
                    except (TimeoutError, ConnectionError) as error:
                        events.append(type(error).__name__)
                        if attempt == retries:
                            raise
                        publisher = bindings.messaging.PubMaster(SERVICES)
                        events.append('publisher_recreated')
        return {'scope': 'injected process/cereal API only; no network/hardware',
                'ticks': ticks, 'events': events}
    finally:
        cleanup_errors = []
        for process in reversed(started):
            try:
                process.stop()
            except Exception as error:
                cleanup_errors.append(str(error))
        if cleanup_errors:
            raise RuntimeError(f'process cleanup errors: {cleanup_errors}')


class MockBindings:
    """Cereal/managed-process test double, not a C2C protocol emulator."""
    def __init__(self, fault=None, fail_start=None):
        self.sent, self.started, self.stopped, self.parameters = [], [], [], {}
        self.fault, self.publishers = fault, 0
        outer = self

        class Process:
            def __init__(self, name):
                self.name = name
            def start(self):
                outer.started.append(self.name)
                if self.name == fail_start:
                    raise RuntimeError('injected process startup failure')
            def stop(self):
                outer.stopped.append(self.name)

        class Publisher:
            def __init__(self, services):
                if list(services) != SERVICES:
                    raise ValueError('unexpected services')
                outer.publishers += 1
            def send(self, service, message):
                if outer.fault:
                    error, outer.fault = outer.fault, None
                    raise error
                outer.sent.append((service, message))

        def new_message(service, size=None):
            payload = [NS()] if service == 'pandaStates' and size == 1 else NS()
            return NS(**{service: payload})

        self.processes = {name: Process(name) for name in PROCESSES}
        self.messaging = NS(new_message=new_message, PubMaster=Publisher)
        self.log = NS(PandaState=NS(PandaType=NS(uno=1)))
        self.params = NS(put=lambda key, value: self.parameters.update({key:value}))
        self.car = NS(CarParams=lambda **kwargs: NS(to_bytes=lambda:b'MOCK_NOT_DEVICE_CARPARAMS'))
