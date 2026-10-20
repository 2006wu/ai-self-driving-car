import copy
import json
from pathlib import Path
import tempfile
import unittest
from p3.follow import FollowController
from p3.scenarios import scenario_suite
from p3.research.controllers import Observation, Action, RuleBasedController, AIController
from p3.research.tracking import create_tracker
from p3.research.dataset import validate_records, validate_record, loads, envelope
from p3.research.export import convert_events, export_events
from p3.research.simulation import SafetySupervisor, CommandReplay, PhysicalRobotInterface


def track(x=140, identity=1):
    return {'id': identity, 'box': [x, 100, x+40, 200], 'state': 'tracked', 'missed': 0}


def event(frame=0, time=1.):
    return {'event': 'frame', 'frame': frame, 'time_seconds': time, 'target': 1,
            'decision': {'simulation_only': True, 'speed': .3, 'turn': 0., 'action': 'FOLLOW',
                         'state': 'TRACKING', 'reason': 'visible_unambiguous_target'}}


class ControllerTests(unittest.TestCase):
    def test_legacy_parity_all_fixtures(self):
        for case in scenario_suite()['scenarios']:
            baseline, adapter = FollowController(), RuleBasedController()
            for i, f in enumerate(case['frames']):
                tracks = [dict(p, state='tracked', missed=0) for p in f['predictions']]
                if i % 9 == 0 and tracks:
                    target = tracks[0]['id']
                    self.assertEqual(baseline.select(target, tracks), adapter.select(target, tracks).metadata)
                for age in (0., .6):
                    actual = adapter.predict(Observation(None, tracks, (300, 400), age))
                    self.assertEqual(actual.metadata, baseline.update(tracks, (300, 400), age))
                    self.assertEqual(actual.linear_velocity_command, actual.metadata['speed'])
                    self.assertEqual(actual.angular_velocity_command, actual.metadata['turn'])
            self.assertEqual(baseline.cancel(), adapter.cancel().metadata)
            self.assertEqual(baseline.stop('fault', True), adapter.stop('fault', True).metadata)
            self.assertEqual(baseline.select(1, [track()]), adapter.select(1, [track()]).metadata)

    def test_loss_overlap_rearm_fault(self):
        c = RuleBasedController(); c.select(1, [track()])
        obs = lambda ts: Observation(None, ts, (300, 320), 0.)
        self.assertEqual(c.predict(obs([track()])).linear_velocity_command, .3)
        c.predict(obs([]))
        self.assertEqual(c.predict(obs([track()])).linear_velocity_command, 0)
        c.select(1, [track()]); c.predict(obs([track(), track(150, 2)]))
        self.assertEqual(c.predict(obs([track()])).linear_velocity_command, 0)
        c.select(1, [track()]); c.predict(obs([track(), track()]))
        self.assertEqual(c.select(1, [track()]).metadata['reason'], 'fault_requires_new_session')

    def test_observation_does_not_arm(self):
        c = RuleBasedController()
        self.assertEqual(c.predict(Observation(None, [track()], (300, 320), 0., target_id=1)).linear_velocity_command, 0)

    def test_ai_disabled(self):
        a = AIController().predict(None)
        self.assertFalse(a.valid); self.assertEqual(a.linear_velocity_command, 0)


class TrackingResearchTests(unittest.TestCase):
    def test_baseline_default(self):
        from p3.tracking import Tracker
        self.assertIs(type(create_tracker()), Tracker)
        with self.assertRaises(ValueError): create_tracker('kalman')

    def test_all_scenarios_deterministic(self):
        for method in ('greedy_iou', 'hungarian'):
            for case in scenario_suite()['scenarios']:
                a, b = create_tracker(method), create_tracker(method)
                for row in case['frames']:
                    detections = [{'class_id': 0, 'box': p['box']} for p in row['predictions']]
                    self.assertEqual(a.update(detections), b.update(detections))

    def test_gap_target_and_invalid_atomic(self):
        for method in ('greedy_iou', 'hungarian'):
            t = create_tracker(method, max_missed=1)
            d = [{'class_id': 0, 'box': [10, 20, 50, 100]}]
            t.update(d); t.update([])
            self.assertEqual(t.update(d)[0]['id'], 1)
            t.update([]); t.update([])
            self.assertEqual(t.target_state, 'lost')
            self.assertEqual(t.update(d)[0]['id'], 2)
            self.assertEqual(t.target, 1)
            for bad in ([0, 0, 0, 1], [0, 0, float('nan'), 2], [0, 0, float('inf'), 2]):
                before = copy.deepcopy(t.__dict__)
                with self.assertRaises(ValueError): t.update([{'class_id': 0, 'box': bad}])
                self.assertEqual(t.__dict__, before)
            t.cancel_target(); t.update(d); self.assertIsNone(t.target)
            t.select(2); self.assertEqual(t.select_next(), 2)

    def test_crossing_metrics_remain_limited(self):
        from p3.tracking_eval import evaluate_sequence
        case = next(c for c in scenario_suite()['scenarios'] if c['scenario'] == 'B_crossing')
        for method in ('greedy_iou', 'hungarian'):
            tracker, frames = create_tracker(method), []
            for row in case['frames']:
                tracks = tracker.update([{'class_id':0, 'box':g['box']} for g in row['ground_truth']])
                frames.append(dict(row, predictions=[{'id':t['id'],'box':t['box']} for t in tracks if t['state']=='tracked']))
            metrics = evaluate_sequence(frames, 'synthetic_ground_truth', target_gt_id=1)
            self.assertEqual(metrics, case['metrics'])
            self.assertEqual(metrics['ID_switches'], 2)

    def test_hungarian_maximum_cardinality_advantage(self):
        # A-X strongest, A-Y and B-X eligible, B-Y ineligible.
        from unittest.mock import patch
        from p3.research.tracking import HungarianTracker
        t = HungarianTracker()
        t.update([{'class_id': 0, 'box': [0,0,10,10]}, {'class_id':0,'box':[20,0,30,10]}])
        with patch('p3.research.tracking.iou', side_effect=[[.9,.4],[.4,0.]]):
            out = t.update([{'class_id':0,'box':[1,0,11,10]}, {'class_id':0,'box':[21,0,31,10]}])
        self.assertEqual(len(out),2)
        self.assertEqual(out[0]['box'],[21,0,31,10])


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)/'events.jsonl'
        self.source.write_text(json.dumps(event())+'\n')
        self.record = convert_events(self.source)[0]

    def test_valid_and_missing_provenance(self):
        validate_record(self.record)
        self.assertIsNone(self.record['robot_measurements']['value'])
        self.assertEqual(self.record['timestamp']['value']['semantics'], 'journal_emission')
        self.assertIsNone(self.record['human_demonstrations']['value'])

    def test_missing_fields(self):
        for key in self.record:
            r = copy.deepcopy(self.record); del r[key]
            with self.assertRaises(ValueError): validate_record(r)

    def test_timestamp_rejects(self):
        for v in (-1, True, '1', float('nan'), float('inf')):
            r = copy.deepcopy(self.record); r['timestamp']['value']['seconds'] = v
            with self.assertRaises(ValueError): validate_record(r)
        r = copy.deepcopy(self.record); r['timestamp']['value']['semantics'] = 'camera_capture'
        with self.assertRaises(ValueError): validate_record(r)

    def test_duplicates_order(self):
        with self.assertRaises(ValueError): validate_records([self.record, self.record])
        r = copy.deepcopy(self.record); r['frame_id'] = 1; r['timestamp']['value']['seconds'] = .1
        with self.assertRaises(ValueError): validate_records([self.record, r])

    def test_boxes(self):
        for b in ([0,0,0,1], [-1,0,2,3], [0,0,float('inf'),3], ['0',0,2,3]):
            r = copy.deepcopy(self.record)
            r['observations']['value']['target_box'] = b
            with self.assertRaises(ValueError): validate_record(r)

    def test_control_metadata_units_nan(self):
        for key, value in [('units','m/s,rad/s'),('controller_type','human'),('source_controller','ai'),
                           ('linear',float('nan')),('angular',float('inf')),('linear', True),('status','STOP'),('status','UNKNOWN')]:
            r = copy.deepcopy(self.record); r['rule_based_pseudo_labels']['value'][key] = value
            with self.assertRaises(ValueError): validate_record(r)

    def test_provenance_separation(self):
        r = copy.deepcopy(self.record); r['human_demonstrations'] = r['rule_based_pseudo_labels']
        with self.assertRaises(ValueError): validate_record(r)
        for name in ('observations','human_demonstrations','rule_based_pseudo_labels'):
            r = copy.deepcopy(self.record); r[name]['provenance'] = {}
            with self.assertRaises(ValueError): validate_record(r)

    def test_real_category_contracts(self):
        r = copy.deepcopy(self.record)
        r['human_demonstrations'] = envelope({'linear':.1,'angular':.2,'units':'m/s,rad/s','operator_id':'test'},
                                            {'kind':'human_demonstration','reference':'test-only'})
        r['robot_measurements'] = envelope({'linear_velocity':.1,'angular_velocity':.2,'units':'m/s,rad/s','odometry':None},
                                           {'kind':'robot_measurement','reference':'test-only'})
        r['ground_truth'] = envelope({'annotations':[{'box':[0,0,2,3]}],'annotation_kind':'synthetic_ground_truth'},
                                    {'kind':'synthetic_ground_truth','reference':'test-only'})
        validate_record(r)
        r['robot_measurements']['value']['units'] = 'normalized_simulation'
        with self.assertRaises(ValueError): validate_record(r)

    def test_corrupt_records(self):
        for raw in ('{', '{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(ValueError): loads(raw)
        for raw in ('[]', '{}', 'null', 'true'):
            with self.assertRaises(ValueError): validate_record(loads(raw))

    def test_export_deterministic_no_overwrite(self):
        before = self.source.read_bytes()
        a, b = Path(self.tmp.name)/'a', Path(self.tmp.name)/'b'
        export_events(self.source,a); export_events(self.source,b)
        self.assertEqual(a.read_bytes(),b.read_bytes()); self.assertEqual(before,self.source.read_bytes())
        with self.assertRaises(FileExistsError): export_events(self.source,a)
        self.assertEqual(convert_events(self.source),[self.record])
        with self.assertRaises(FileExistsError): export_events(self.source,self.source)

    def test_bad_journal_no_destination(self):
        destination = Path(self.tmp.name)/'out'
        cases = [[event(),event()], [event(time=-1)], [event(),event(1,.5)],
                 [event(),{'event':'frame','time_seconds':2,'frame':1,'decision':{'simulation_only':False}}]]
        for events in cases:
            self.source.write_text('\n'.join(map(json.dumps, events)))
            with self.assertRaises(ValueError): export_events(self.source,destination)
            self.assertFalse(destination.exists())


class SimulationTests(unittest.TestCase):
    def test_gate_rearm_emergency_fault(self):
        gate = SafetySupervisor(); a = Action(.3,0.,'TRACKING','rule_based',True)
        self.assertEqual(gate.apply(a).linear_velocity_command,0)
        gate.rearm(); self.assertEqual(gate.apply(a),a)
        self.assertEqual(gate.apply(a,emergency_stop=True).linear_velocity_command,0)
        self.assertEqual(gate.apply(a).linear_velocity_command,0)
        gate.rearm(); gate.apply(a,fault=True); gate.rearm()
        self.assertEqual(gate.apply(a).linear_velocity_command,0)

    def test_invalid_actions_stale_stop(self):
        for action in (Action(.3,0,'x','x',True,units='m/s'), Action(float('nan'),0,'x','x',True), Action(.3,0,'STOP','x',True), AIController().predict(None)):
            gate = SafetySupervisor(); gate.rearm()
            self.assertEqual(gate.apply(action).linear_velocity_command,0)
        gate = SafetySupervisor(); gate.rearm()
        self.assertEqual(gate.apply(Action(.3,0,'x','x',True),age_seconds=.6).linear_velocity_command,0)

    def test_replay_and_physical_disabled(self):
        replay = CommandReplay(); a = AIController().predict(None)
        self.assertEqual(replay.submit(a),a)
        self.assertTrue(replay.simulation_only)
        with self.assertRaises(ValueError): replay.submit(Action(.1,0,'x','x',False))
        with self.assertRaises(RuntimeError): PhysicalRobotInterface()
