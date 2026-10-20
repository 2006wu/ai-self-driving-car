import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from p3.tracking import Tracker
from p3.evaluation import benchmark
from p3.detection import ROOT, Detector, MODEL
from p3.pipeline import run


def person(x=0,y=100):
    return {'class_id':0,'label':'person','objectness':.9,'box':[x,y,x+40,y+100]}


class TrackingTests(unittest.TestCase):
    def test_persistent_id(self):
        t=Tracker();a=t.update([person()]);b=t.update([person(2)])
        self.assertEqual(a[0]['id'],b[0]['id'])
    def test_multiple_one_to_one(self):
        t=Tracker();t.update([person(),person(100)])
        tracks=t.update([person(2),person(102)])
        self.assertEqual(len(tracks),2);self.assertEqual({r['id'] for r in tracks},{1,2})
    def test_occlusion_recovery(self):
        t=Tracker();t.update([person()]);t.update([])
        self.assertEqual(t.target_state,'missing')
        tracks=t.update([person(2)])
        self.assertEqual(tracks[0]['id'],1);self.assertEqual(t.target_state,'tracked')
    def test_lost_no_silent_switch(self):
        t=Tracker(max_missed=1);t.update([person()]);t.update([]);t.update([])
        t.update([person(200)])
        self.assertEqual(t.target,1);self.assertEqual(t.target_state,'lost')
    def test_explicit_selection(self):
        t=Tracker();t.update([person(),person(100)])
        self.assertEqual(t.select_next(),2)
    def test_nonperson_ignored(self):
        p=person();p['class_id']=2
        self.assertEqual(Tracker().update([p]),[])
    def test_fast_motion_new_id(self):
        t=Tracker();t.update([person()]);tracks=t.update([person(300)])
        self.assertEqual(tracks[-1]['id'],2)
    def test_new_id_after_long_loss(self):
        t=Tracker(max_missed=0);t.update([person()]);t.update([])
        self.assertEqual(t.update([person()])[0]['id'],2)
    def test_bounded_long_run(self):
        t=Tracker(max_missed=2)
        for i in range(1000): t.update([person(i*100)])
        self.assertLessEqual(len(t.tracks),3)
    def test_parameter_validation(self):
        with self.assertRaises(ValueError): Tracker(max_missed=-1)


class BenchmarkIntegrationTests(unittest.TestCase):
    def test_repeatable_input_configuration(self):
        source=ROOT/'projects/project3/artifacts/bus.jpg'
        if not source.exists(): self.skipTest('bus fixture missing')
        a=benchmark(source,samples=3,warmup=1)
        b=benchmark(source,samples=3,warmup=1)
        self.assertEqual(a['input_sha256'],b['input_sha256'])
        self.assertEqual(a['model']['model_sha256'],b['model']['model_sha256'])
        self.assertEqual(a['detection_count'],b['detection_count'])
        self.assertEqual(a['metrics']['inference_ms']['count'],3)
        self.assertGreater(a['file_pipeline_fps'],0)
    def test_model_pipeline_short_video_eof_and_single_session(self):
        if not MODEL.is_file():
            self.skipTest('ONNX model missing: external/aJLL/bodyjim/yolov5n_flat.onnx (not in git; no automatic download)')
        with tempfile.TemporaryDirectory() as tmp:
            source=str(Path(tmp)/'test.avi')
            w=cv2.VideoWriter(source,cv2.VideoWriter_fourcc(*'MJPG'),10,(128,96))
            self.assertTrue(w.isOpened())
            for i in range(4): w.write(np.full((96,128,3),i*30,np.uint8))
            w.release()
            detector=Detector();session=detector.session
            rows=run(detector,source,Path(tmp)/'out',max_frames=100,tracker=Tracker())
            self.assertEqual(len(rows),4);self.assertIs(detector.session,session)
            cap=cv2.VideoCapture(str(Path(tmp)/'out/overlay.avi'))
            count=0
            while cap.read()[0]: count+=1
            cap.release();self.assertEqual(count,4)

class DashboardTests(unittest.TestCase):
    def test_gui_quit_and_cleanup(self):
        image=ROOT/'projects/project3/artifacts/bus.jpg'
        if not image.exists(): self.skipTest('bus image missing')
        with tempfile.TemporaryDirectory() as t, \
             patch('p3.pipeline.cv2.imshow') as show, \
             patch('p3.pipeline.cv2.waitKey',return_value=ord('q')), \
             patch('p3.pipeline.cv2.destroyAllWindows') as close:
            rows=run(Detector(),image,Path(t)/'out',display=True,tracker=Tracker())
            self.assertEqual(len(rows),1);show.assert_called_once();close.assert_called_once()
    def test_ui_invalid_data_stops_processes(self):
        from p3.run2 import MockBindings,run_ui
        b=MockBindings()
        with patch('p3.run2.validate',side_effect=ValueError('bad data')):
            with self.assertRaises(ValueError): run_ui(b,sleep=lambda _:None)
        self.assertEqual(len(b.stopped),4)
