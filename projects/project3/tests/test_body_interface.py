"""Offline command boundary checks; no external processes or devices."""
import ast
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest

from p3.research import body_interface as body
from p3.research.controllers import Action
from p3.research.simulation import SafetySupervisor


def action(v=.3, w=.5, **kwargs):
    return Action(v, w, kwargs.pop('status', 'TRACKING'), 'test',
                  kwargs.pop('valid', True), **kwargs)


class BodyInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.interface = body.BodyInterface()

    def moving(self):
        self.interface.tick(action(), now=0.)
        return self.interface.tick(action(), now=.1)

    def reasons(self):
        return self.interface.history[-1]['reasons']

    def test_watchdog(self):
        self.moving()
        at_boundary = self.interface.tick(now=.35)
        self.assertGreater(at_boundary.linear, 0.)
        stopped = self.interface.tick(now=.351)
        self.assertEqual((stopped.linear, stopped.angular), (0., 0.))
        self.assertEqual(self.reasons(), ['watchdog_zero'])
        self.assertEqual(self.interface.tick(now=.4).linear, 0.)
        # A long idle interval cannot accumulate an acceleration budget.
        self.assertEqual(self.interface.tick(action(), now=2.).linear, 0.)
        self.assertAlmostEqual(self.interface.tick(action(), now=2.1).linear, .1)

    def test_initial_poll_and_injected_clock(self):
        clock_values = iter([0., .1, .2, .5])
        interface = body.BodyInterface(clock=lambda: next(clock_values))
        self.assertEqual(interface.tick().linear, 0.)
        interface.tick(action())
        self.assertGreater(interface.tick(action()).linear, 0.)
        self.assertEqual(interface.tick().linear, 0.)

    def test_estop_latches_and_reset_requires_post_latch_zero(self):
        self.moving()
        stopped = self.interface.estop('operator', now=.11)
        self.assertEqual((stopped.linear, stopped.angular), (0., 0.))
        self.assertEqual(self.reasons(), ['estop_latched'])
        with self.assertRaisesRegex(ValueError, 'zero'):
            self.interface.reset_estop()
        for timestamp in (.12, .2, .5):
            self.assertEqual(self.interface.tick(action(), now=timestamp).linear, 0.)
        with self.assertRaises(ValueError):
            self.interface.reset_estop()
        self.interface.tick(action(0., 0.), now=.6)
        self.assertTrue(self.interface.estop_latched)
        self.interface.reset_estop()
        self.assertFalse(self.interface.estop_latched)
        self.assertGreater(self.interface.tick(action(), now=.7).linear, 0.)

    def test_nonzero_after_zero_blocks_reset(self):
        self.interface.estop('stop', now=0.)
        self.interface.tick(action(0., 0.), now=.1)
        self.interface.tick(action(), now=.2)
        with self.assertRaises(ValueError):
            self.interface.reset_estop()

    def test_acceleration_and_immediate_deceleration(self):
        first = self.moving()
        self.assertAlmostEqual(first.linear, .1)
        self.assertAlmostEqual(first.angular, .1)
        self.assertIn('rate_limited', self.reasons())
        lower = self.interface.tick(action(.015, .025), now=.11)
        self.assertAlmostEqual(lower.linear, .05)
        self.assertAlmostEqual(lower.angular, .05)
        stopped = self.interface.tick(action(0., 0.), now=.111)
        self.assertEqual((stopped.linear, stopped.angular), (0., 0.))
        self.assertEqual(self.reasons(), ['ok'])

    def test_angular_reversal_brakes_then_accelerates(self):
        self.moving()
        reversed_command = self.interface.tick(action(.3, -.5), now=.11)
        self.assertAlmostEqual(reversed_command.angular, -.01)

    def test_clamping_and_mapping(self):
        limits = body.BodyLimits(max_linear=2., max_angular=3.,
                                 max_linear_accel=100., max_angular_accel=100.)
        interface = body.BodyInterface(limits=limits)
        interface.tick(action(), now=0.)
        command = interface.tick(action(9., -9.), now=.1)
        self.assertEqual((command.linear, command.angular), (2., -3.))
        self.assertEqual(interface.history[-1]['reasons'], ['clamped'])
        self.assertEqual(interface.tick(action(-1., 0.), now=.11).linear, 0.)
        self.assertEqual(command.units, 'body_normalized')
        self.assertEqual(command.source, 'test')
        self.assertEqual(command.sequence, 1)

    def test_invalid_inputs_zero_and_fault(self):
        bad_actions = [action(float('nan')), action(w=float('inf')),
                       action(float('-inf')), action(True), action('bad'),
                       action(10 ** 400),
                       action(units='m/s'), action(valid=False), object(),
                       action(status='STOP')]
        for bad in bad_actions:
            with self.subTest(bad=bad):
                self.setUp()
                self.moving()
                command = self.interface.tick(bad, now=.11)
                self.assertEqual((command.linear, command.angular), (0., 0.))
                self.assertTrue(self.interface.faulted)
                self.assertEqual(self.reasons(), ['invalid_input'])

    def test_supervisor_stop_is_immediate(self):
        self.moving()
        supervisor = SafetySupervisor()  # starts latched
        command = self.interface.tick(supervisor.apply(action()), now=.11)
        self.assertEqual((command.linear, command.angular), (0., 0.))
        self.assertEqual(self.reasons(), ['supervisor_stop'])

    def test_limits_validation(self):
        for name in body.BodyLimits.__dataclass_fields__:
            for value in (0., -1., float('nan'), float('inf'), True, '1'):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    replace(body.BodyLimits(), **{name: value})

    def test_bad_time_never_sends(self):
        self.moving()
        for now in (.01, float('nan'), float('inf'), -1., True):
            with self.assertRaises(ValueError):
                self.interface.tick(action(), now=now)
        self.assertEqual(len(self.interface.transport.commands), 2)

    def test_factory_and_disabled_real(self):
        self.assertIsInstance(body.create_transport(), body.MockTransport)
        self.assertIsInstance(body.create_transport('dry_run'), body.DryRunTransport)
        with self.assertRaisesRegex(ValueError, 'simulation_only=True'):
            body.create_transport('real', allow_real=True)
        with self.assertRaisesRegex(ValueError, 'allow_real=False'):
            body.create_transport('real', simulation_only=False)
        with self.assertRaises(NotImplementedError):
            body.create_transport('real', simulation_only=False, allow_real=True)
        with self.assertRaises(NotImplementedError):
            body.RealTransport()
        with self.assertRaises(ValueError):
            body.BodyInterface(simulation_only=False)
        with self.assertRaises(ValueError):
            body.BodyInterface(transport=object())
        with self.assertRaises(ValueError):
            body.create_transport('unknown')
        with self.assertRaises(TypeError):
            body.Transport()

    def test_history_matches_recorded_commands(self):
        self.moving()
        self.interface.estop('test', now=.11)
        self.assertEqual(len(self.interface.history), len(self.interface.transport.commands))
        for row, command in zip(self.interface.history, self.interface.transport.commands):
            self.assertEqual(row['sequence'], command.sequence)
            self.assertEqual(row['linear'], command.linear)
            self.assertTrue(row['reasons'])

    def test_cli_replay_sim(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            output = Path(temp) / 'new'
            self.assertEqual(body.main(['replay-sim', '--scenario', 'too_close',
                                        '--controller', 'pid', '--steps', '5',
                                        '--output', str(output)]), 0)
            summary = json.loads((output / 'summary.json').read_text())
            rows = [json.loads(line) for line in (output / 'commands.jsonl').read_text().splitlines()]
            self.assertTrue(summary['simulation_only'])
            self.assertEqual(summary['transport'], 'mock')
            self.assertEqual(summary['command_count'], 5)
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(row['linear'] == 0 for row in rows))
            self.assertEqual(summary['counts_per_reason'], {'ok': 5})
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                body.main(['replay-sim', '--output', str(output)])

    def test_cli_replay_log_and_persistent_supervisor(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            output = Path(temp) / 'new'
            fixture = Path(__file__).parent / 'fixtures' / 'body-actions.jsonl'
            body.main(['replay-log', str(fixture), '--output', str(output)])
            rows = [json.loads(line) for line in (output / 'commands.jsonl').read_text().splitlines()]
            self.assertGreater(rows[1]['linear'], 0.)
            self.assertEqual(rows[2]['linear'], 0.)
            self.assertEqual(rows[3]['linear'], 0.)
            self.assertEqual(rows[3]['reasons'], ['supervisor_stop'])

    def test_cli_real_refused_without_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            for mode in (['replay-sim'], ['replay-log', 'unused.jsonl']):
                error = io.StringIO()
                output = Path(temp) / 'new'
                with redirect_stderr(error), self.assertRaises(SystemExit) as raised:
                    body.main(mode + ['--transport', 'real', '--output', str(output)])
                self.assertNotEqual(raised.exception.code, 0)
                self.assertIn('Real transport refused', error.getvalue())
                self.assertFalse(output.exists())

    def test_no_device_or_network_imports(self):
        tree = ast.parse(Path(body.__file__).read_text())
        forbidden = {'socket', 'serial', 'can', 'usb', 'subprocess', 'requests'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name.split('.')[0] for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or '').split('.')[0]]
            else:
                continue
            self.assertFalse(forbidden.intersection(names))


if __name__ == '__main__':
    unittest.main()
