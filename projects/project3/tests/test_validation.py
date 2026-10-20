import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from p3.follow import FollowController
from p3.tracking import Tracker
from p3.pipeline import run, Frames
from p3.tracking_eval import maximum_assignment, evaluate_sequence
from p3.scenarios import scenario_suite
from p3.evaluation import benchmark
from p3.detection import ROOT


def track(identity=1, x=140, state='tracked', width=40):
    return {'id':identity,'box':[x,100,x+width,200],'state':state,'missed':0}


def det(x=140, width=40):
    return {'class_id':0,'label':'person','objectness':.9,'box':[x,100,x+width,200]}


class FollowTests(unittest.TestCase):
    def setUp(self): self.c=FollowController(lost_after=2)
    def ready(self): self.c.select(1,[track()]);return self.c.update([track()],(300,320,3))
    def test_default_no_auto_follow(self): self.assertEqual(self.c.update([track()],(300,320,3))['action'],'STOP')
    def test_select_first_stops(self): self.assertEqual(self.c.select(1,[track()])['state'],'TARGET_SELECTED')
    def test_center_far_moves_simulation_only(self):
        r=self.ready();self.assertEqual(r['state'],'TRACKING');self.assertEqual(r['speed'],.3);self.assertTrue(r['simulation_only'])
    def test_left_turn_no_forward(self):
        self.ready();r=self.c.update([track(x=0)],(300,320,3));self.assertGreater(r['turn'],0);self.assertEqual(r['speed'],0)
    def test_right_turn_no_forward(self):
        self.ready();r=self.c.update([track(x=270)],(300,320,3));self.assertLess(r['turn'],0);self.assertEqual(r['speed'],0)
    def test_close_stop_no_reverse(self):
        self.ready();r=self.c.update([track(x=100,width=120)],(300,320,3));self.assertEqual(r['action'],'STOP')
    def test_short_loss_stops_immediately(self):
        self.ready();r=self.c.update([],(300,320,3));self.assertEqual(r['state'],'TARGET_TEMPORARILY_LOST');self.assertEqual(r['action'],'STOP')
    def test_long_loss(self):
        self.ready()
        for _ in range(3):r=self.c.update([],(300,320,3))
        self.assertEqual(r['state'],'TARGET_LOST');self.assertEqual(r['speed'],0)
    def test_same_id_reappearance_needs_confirmation(self):
        self.ready();self.c.update([],(300,320,3));self.assertEqual(self.c.update([track()],(300,320,3))['action'],'STOP')
        self.c.select(1,[track()]);self.assertEqual(self.c.update([track()],(300,320,3))['action'],'FOLLOW')
    def test_new_id_never_adopted(self):
        self.ready();self.assertEqual(self.c.update([track(2)],(300,320,3))['action'],'STOP');self.assertEqual(self.c.target,1)
    def test_crossing_ambiguity_latches(self):
        self.ready();self.assertEqual(self.c.update([track(),track(2,x=150)],(300,320,3))['action'],'STOP')
        self.assertEqual(self.c.update([track()],(300,320,3))['action'],'STOP')
    def test_cancel_is_latched(self):
        self.ready();self.c.cancel();r=self.c.update([track()],(300,320,3));self.assertEqual(r['action'],'STOP');self.assertIsNone(r['target_id'])
    def test_invalid_id(self):
        for bad in [0,-1,True,'1',float('nan')]:self.assertEqual(self.c.select(bad,[track()])['action'],'STOP')
    def test_duplicate_id_fault(self):
        self.ready();r=self.c.update([track(),track()],(300,320,3));self.assertEqual(r['action'],'STOP');self.assertTrue(self.c.faulted)
    def test_invalid_box_fault(self):
        for box in [[0,0,0,4],[0,0,float('nan'),2],[-1,0,3,4],[0,0,400,5]]:
            c=FollowController();c.select(1,[track()]);t=track();t['box']=box;self.assertEqual(c.update([t],(300,320,3))['action'],'STOP')
    def test_fault_cannot_rearm(self):
        self.ready();self.c.stop('inference_failure',fault=True);self.assertEqual(self.c.select(1,[track()])['action'],'STOP')
    def test_invalid_shape(self):self.ready();self.assertEqual(self.c.update([track()],(0,0,3))['action'],'STOP')
    def test_invalid_configuration(self):
        for kwargs in [{'lost_after':-1},{'overlap_stop':2}]:
            with self.assertRaises(ValueError):FollowController(**kwargs)
    def test_tracker_cancel_no_automatic_reselection(self):
        t=Tracker();t.update([det()]);t.cancel_target();t.update([det()]);self.assertIsNone(t.target);t.select(1);self.assertEqual(t.target,1)
    def test_tracker_invalid_detection_atomic(self):
        t=Tracker();t.update([det()]);before=dict(t.tracks)
        with self.assertRaises(ValueError):t.update([{'class_id':0,'box':[0,0,0,0]}])
        self.assertEqual(t.tracks,before)


class MetricTests(unittest.TestCase):
    def frame(self,n,gt=(1,),pred=(1,)):
        return {'frame':n,'ground_truth':[{'id':g,'box':[0,0,40,100]} for g in gt],
                'predictions':[{'id':p,'box':[0,0,40,100]} for p in pred]}
    def test_perfect(self):
        r=evaluate_sequence([self.frame(i) for i in range(5)],'synthetic_ground_truth');self.assertEqual(r['IDF1'],1);self.assertEqual(r['ID_switches'],0)
    def test_identity_split_global_not_greedy(self):
        r=evaluate_sequence([self.frame(i,pred=(1 if i<2 else 2,)) for i in range(4)],'synthetic_ground_truth')
        self.assertEqual((r['IDTP'],r['IDFP'],r['IDFN']),(2,2,2));self.assertEqual(r['IDF1'],.5);self.assertEqual(r['ID_switches'],1)
    def test_miss_and_false_positive(self):
        r=evaluate_sequence([self.frame(0),self.frame(1,pred=()),self.frame(2,gt=())],'synthetic_ground_truth')
        self.assertEqual((r['IDTP'],r['IDFN'],r['IDFP']),(1,1,1));self.assertEqual(r['IDF1'],.5)
    def test_fragmentation(self):
        r=evaluate_sequence([self.frame(0),self.frame(1,pred=()),self.frame(2)],'synthetic_ground_truth',target_gt_id=1)
        self.assertEqual(r['track_fragmentations'],1);self.assertEqual(r['target_recovery']['rate'],1)
    def test_absent_ground_truth_not_fragment(self):
        r=evaluate_sequence([self.frame(0),self.frame(1,(),()),self.frame(2)],'synthetic_ground_truth')
        self.assertEqual(r['track_fragmentations'],0)
    def test_no_gt_or_predictions_rates_na(self):
        r=evaluate_sequence([self.frame(0,(),())],'synthetic_ground_truth');self.assertIsNone(r['IDF1']);self.assertIsNone(r['target_recovery']['rate'])
    def test_unlabeled_cannot_claim_accuracy(self):
        with self.assertRaises(ValueError):evaluate_sequence([self.frame(0)],'proxy')
    def test_invalid_duplicates(self):
        with self.assertRaises(ValueError):evaluate_sequence([self.frame(0,pred=(1,1))],'synthetic_ground_truth')
    def test_invalid_frame_order(self):
        with self.assertRaises(ValueError):evaluate_sequence([self.frame(1),self.frame(0)],'synthetic_ground_truth')
    def test_assignment_rectangular(self):
        self.assertEqual(maximum_assignment([[2,0,0],[0,5,0]]),[(0,0),(1,1)])
    def test_assignment_matches_brute_force(self):
        rng=np.random.default_rng(42)
        for n,m in [(2,3),(3,2),(4,4)]:
            for _ in range(8):
                a=rng.integers(0,10,(n,m)).tolist();size=max(n,m);padded=np.zeros((size,size));padded[:n,:m]=a
                optimum=max(sum(padded[i,j] for i,j in enumerate(order)) for order in itertools.permutations(range(size)))
                self.assertEqual(sum(a[i][j] for i,j in maximum_assignment(a)),optimum)
    def test_scenarios_cover_categories_and_expose_failures(self):
        r=scenario_suite();self.assertEqual(len(r['scenarios']),12)
        self.assertTrue(any(s['metrics']['ID_switches']>0 for s in r['scenarios']))
        self.assertTrue(all(s['metrics']['annotation_kind']=='synthetic_ground_truth' for s in r['scenarios']))


class FakeDetector:
    def predict(self, image):return [det()],{'inference_ms':1.}


class PipelineSafetyTests(unittest.TestCase):
    def image(self,path):cv2.imwrite(str(path),np.zeros((300,320,3),np.uint8))
    def events(self,out):return [json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]
    def test_inference_exception_stop_and_cleanup(self):
        for error in [RuntimeError('model failure'),LookupError('unexpected'),KeyboardInterrupt()]:
            with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as t:
                src=Path(t)/'input.png';self.image(src);out=Path(t)/'out';d=FakeDetector();d.predict=lambda _:(_ for _ in ()).throw(error)
                with self.assertRaises(type(error)):run(d,src,out,controller=FollowController(),tracker=Tracker())
                controls=[e for e in self.events(out) if e['event']=='simulated_control'];self.assertEqual(controls[-1]['action'],'STOP')
                self.assertEqual(controls[-1]['speed'],0);self.assertTrue((out/'run-status.json').exists())
    def test_cancel_key_priority(self):
        with tempfile.TemporaryDirectory() as t,patch('p3.pipeline.cv2.imshow'),patch('p3.pipeline.cv2.waitKey',return_value=ord('c')),patch('p3.pipeline.cv2.destroyAllWindows') as close:
            src=Path(t)/'input.png';self.image(src);c=FollowController();rows=run(FakeDetector(),src,Path(t)/'out',display=True,tracker=Tracker(),controller=c,target_id=1)
            self.assertEqual(rows[0]['decision']['action'],'STOP');self.assertEqual(rows[0]['decision']['reason'],'user_cancelled');close.assert_called_once()
    def test_screenshot_key(self):
        with tempfile.TemporaryDirectory() as t,patch('p3.pipeline.cv2.imshow'),patch('p3.pipeline.cv2.waitKey',return_value=ord('s')),patch('p3.pipeline.cv2.destroyAllWindows'):
            src=Path(t)/'input.png';self.image(src);out=Path(t)/'out';run(FakeDetector(),src,out,display=True)
            self.assertTrue((out/'screenshot-000000.png').exists())
    def test_camera_permission_failure_stop(self):
        with tempfile.TemporaryDirectory() as t,patch('p3.pipeline.cv2.VideoCapture') as factory:
            cap=factory.return_value;cap.isOpened.return_value=False
            with self.assertRaises(RuntimeError):run(FakeDetector(),'0',Path(t)/'out',camera=True,tracker=Tracker(),controller=FollowController())
            cap.release.assert_called_once();self.assertEqual(self.events(Path(t)/'out')[-2]['action'],'STOP')
    def test_camera_disconnect_after_frames(self):
        with tempfile.TemporaryDirectory() as t,patch('p3.pipeline.cv2.VideoCapture') as factory:
            cap=factory.return_value;cap.isOpened.return_value=True;cap.get.return_value=30;cap.read.side_effect=[(True,np.zeros((300,320,3),np.uint8)),(False,None)]
            out=Path(t)/'out'
            with self.assertRaises(RuntimeError):run(FakeDetector(),'0',out,camera=True,tracker=Tracker(),controller=FollowController(),record=False)
            cap.release.assert_called_once();self.assertEqual(json.loads((out/'run-status.json').read_text())['frames'],1)
            self.assertEqual([e for e in self.events(out) if e['event']=='simulated_control'][-1]['action'],'STOP')
    def test_enter_get_failure_releases(self):
        with patch('p3.pipeline.cv2.VideoCapture') as factory:
            cap=factory.return_value;cap.isOpened.return_value=True;cap.get.side_effect=RuntimeError('property error')
            with self.assertRaises(RuntimeError):
                with Frames('0',True):pass
            cap.release.assert_called_once()
    def test_invalid_box_stops_before_render(self):
        with tempfile.TemporaryDirectory() as t:
            src=Path(t)/'input.png';self.image(src);d=FakeDetector();d.predict=lambda _:([dict(det(),box=[0,0,float('nan'),4])],{})
            with patch('p3.pipeline.render') as render:
                with self.assertRaises(ValueError):run(d,src,Path(t)/'out',tracker=Tracker(),controller=FollowController())
                render.assert_not_called()
    def test_run_timing_and_eof_final_stop(self):
        with tempfile.TemporaryDirectory() as t:
            src=Path(t)/'input.png';self.image(src);out=Path(t)/'out';rows=run(FakeDetector(),src,out,tracker=Tracker(),controller=FollowController(),target_id=1)
            self.assertGreaterEqual(rows[0]['timing']['loop_ms'],rows[0]['timing']['e2e_ms'])
            self.assertGreaterEqual(rows[0]['timing']['tracking_ms'],0)
            self.assertEqual([e for e in self.events(out) if e['event']=='simulated_control'][-1]['action'],'STOP')
    def test_nonfinite_duration_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):run(FakeDetector(),'none',t,max_seconds=float('nan'))
    def test_benchmark_tracking_timings_real_model(self):
        r=benchmark(ROOT/'projects/project3/artifacts/bus.jpg',samples=3,warmup=1,tracking=True,simulate_follow=True)
        self.assertEqual(r['metrics']['tracking_ms']['count'],3);self.assertGreater(r['cpu_percent_one_core'],0)
        self.assertGreater(r['person_count']['mean'],0);self.assertEqual(r['application_skipped_frames'],0)

class AdditionalFailureTests(unittest.TestCase):
    def test_stale_frame_stops_and_latches(self):
        c=FollowController();c.select(1,[track()]);r=c.update([track()],(300,320,3),age_seconds=.6)
        self.assertEqual(r['action'],'STOP');self.assertEqual(c.update([track()],(300,320,3))['action'],'STOP')
    def test_sparse_frames_break_continuity(self):
        f=lambda n:{'frame':n,'ground_truth':[{'id':1,'box':[0,0,5,10]}],'predictions':[{'id':1,'box':[0,0,5,10]}]}
        r=evaluate_sequence([f(0),f(2)],'synthetic_ground_truth');self.assertEqual(r['track_continuity']['1']['longest_consecutive_match_fraction'],.5)
    def test_assignment_nonfinite_rejected(self):
        with self.assertRaises(ValueError):maximum_assignment([[float('nan')]])
    def test_tracking_invalid_age(self):
        for age in [float('nan'),float('inf'),.5,True]:
            with self.assertRaises(ValueError):Tracker(max_missed=age)
    def test_empty_success_frame_is_failure(self):
        with patch('p3.pipeline.cv2.VideoCapture') as factory:
            cap=factory.return_value;cap.isOpened.return_value=True;cap.get.return_value=20;cap.read.return_value=(True,None)
            with self.assertRaises(RuntimeError):
                with Frames('0',True) as f:list(f)
            cap.release.assert_called_once()
    def test_premature_video_read_failure(self):
        with tempfile.NamedTemporaryFile(suffix='.avi') as f,patch('p3.pipeline.cv2.VideoCapture') as factory:
            cap=factory.return_value;cap.isOpened.return_value=True;cap.get.return_value=10;cap.read.return_value=(False,None)
            with self.assertRaises(RuntimeError):
                with Frames(f.name) as frames:list(frames)
            cap.release.assert_called_once()
    def test_gui_unexpected_error_still_stop_close(self):
        with tempfile.TemporaryDirectory() as t,patch('p3.pipeline.cv2.imshow',side_effect=LookupError('GUI')),patch('p3.pipeline.cv2.destroyAllWindows') as close:
            src=Path(t)/'image.png';cv2.imwrite(str(src),np.zeros((300,320,3),np.uint8));out=Path(t)/'out'
            with self.assertRaises(LookupError):run(FakeDetector(),src,out,display=True,tracker=Tracker(),controller=FollowController())
            close.assert_called_once();events=[json.loads(x) for x in (out/'events.jsonl').read_text().splitlines()]
            self.assertEqual([x for x in events if x['event']=='simulated_control'][-1]['action'],'STOP')
    def test_preview_failure_stops(self):
        with tempfile.TemporaryDirectory() as t:
            src=Path(t)/'image.png';cv2.imwrite(str(src),np.zeros((300,320,3),np.uint8));out=Path(t)/'out'
            with patch('p3.pipeline.cv2.imwrite',return_value=False):
                with self.assertRaises(RuntimeError):run(FakeDetector(),src,out,tracker=Tracker(),controller=FollowController())
            self.assertEqual(json.loads((out/'run-status.json').read_text())['status'],'FAIL')
    def test_quit_final_stop(self):
        with tempfile.TemporaryDirectory() as t,patch('p3.pipeline.cv2.imshow'),patch('p3.pipeline.cv2.waitKey',return_value=ord('q')),patch('p3.pipeline.cv2.destroyAllWindows'):
            src=Path(t)/'image.png';cv2.imwrite(str(src),np.zeros((300,320,3),np.uint8));out=Path(t)/'out'
            rows=run(FakeDetector(),src,out,display=True,tracker=Tracker(),controller=FollowController(),target_id=1)
            self.assertEqual(rows[0]['decision']['action'],'STOP');self.assertEqual(rows[0]['decision']['reason'],'user_quit')
    def test_recording_failure_releases_writer(self):
        with tempfile.TemporaryDirectory() as t,patch('p3.pipeline.cv2.VideoCapture') as factory,patch('p3.pipeline.cv2.VideoWriter') as writer:
            cap=factory.return_value;cap.isOpened.return_value=True;cap.get.return_value=20;cap.read.return_value=(True,np.zeros((300,320,3),np.uint8));writer.return_value.isOpened.return_value=False
            with self.assertRaises(RuntimeError):run(FakeDetector(),'0',Path(t)/'out',camera=True,tracker=Tracker(),controller=FollowController())
            cap.release.assert_called_once();writer.return_value.release.assert_called_once()

class SelectionSafetyTests(unittest.TestCase):
    def test_selection_during_overlap_cannot_arm_after_separation(self):
        c=FollowController();r=c.select(1,[track(),track(2,x=150)])
        self.assertEqual(r['action'],'STOP');self.assertEqual(r['reason'],'selection_ambiguous')
        self.assertEqual(c.update([track()],(300,320,3))['action'],'STOP')
    def test_tracker_invalid_selection(self):
        t=Tracker();t.update([det()])
        for k in [True,0,-1,99,'1']:
            with self.assertRaises(ValueError):t.select(k)
    def test_invisible_selected_target_is_rejected(self):
        c=FollowController();self.assertEqual(c.select(1,[track(state='missing')])['action'],'STOP')

class CrossingRegressionTests(unittest.TestCase):
    def test_crossing_between_frames_exposes_iou_id_switches(self):
        r=scenario_suite();cross=next(s for s in r['scenarios'] if s['scenario']=='B_crossing')
        self.assertGreater(cross['metrics']['ID_switches'],0)
        self.assertLess(cross['metrics']['IDF1'],1)
    def test_event_sink_failure_closes_handle_and_latches_stop(self):
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as t:
            src=Path(t)/'image.png';cv2.imwrite(str(src),np.zeros((300,320,3),np.uint8));c=FollowController()
            stream=MagicMock();stream.write.side_effect=OSError('disk unavailable')
            original=Path.open
            def opening(path,*args,**kwargs):
                return stream if path.name=='events.jsonl' else original(path,*args,**kwargs)
            with patch.object(Path,'open',opening):
                with self.assertRaises(OSError):run(FakeDetector(),src,Path(t)/'out',tracker=Tracker(),controller=c)
            stream.close.assert_called_once();self.assertEqual(c.output()['action'],'STOP')
