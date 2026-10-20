import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from p3.detection import Detector, MODEL, ROOT, decode, iou, map_boxes
from p3.pipeline import Frames, run, render
from p3.evaluation import stats, benchmark
from p3.run2 import MockBindings, build_messages, run_ui, validate, PROCESSES


class GeometryTests(unittest.TestCase):
    def test_non_square_map(self):
        a=map_boxes([[0,0,640,416,.8,0]],1280,480)
        np.testing.assert_array_equal(a[0,:4],[0,0,1280,480])
    def test_clip(self):
        a=map_boxes([[-10,-20,700,500,.5,0]],320,208)
        np.testing.assert_array_equal(a[0,:4],[0,0,320,208])
    def test_map_empty(self):
        self.assertEqual(map_boxes([],640,416).shape,(0,6))
    def test_zero_area_iou(self):
        np.testing.assert_equal(iou([0,0,0,0],[[0,0,0,0]]),[0])
    def test_iou_overlap(self):
        self.assertAlmostEqual(iou([0,0,2,2],[[1,1,3,3]])[0],1/7)
    def test_bad_threshold(self):
        with self.assertRaises(ValueError): decode(np.zeros(1392300),-1)
    def test_nonfinite_output(self):
        a=np.zeros(1392300);a[0]=np.nan
        with self.assertRaises(ValueError): decode(a)
    def test_bad_output_shape(self):
        with self.assertRaises(ValueError): decode(np.zeros(85))
    def test_empty_detections(self):
        self.assertEqual(decode(np.zeros(1392300)).shape,(0,6))
    def test_preprocess(self):
        x=Detector.preprocess(np.full((480,1000,3),255,np.uint8))
        self.assertEqual(x.shape,(1,3,416,640));self.assertEqual(x.dtype,np.float32)
        np.testing.assert_array_equal(x,1)
    def test_invalid_image(self):
        with self.assertRaises(ValueError): Detector.preprocess(np.zeros((3,3)))
    def test_baseline_nms_equivalence(self):
        path=ROOT/'external/aJLL/bodyjim/YoloPC.py'
        if not path.is_file():
            self.skipTest('YoloPC.py missing: external/aJLL/bodyjim/YoloPC.py (not in git)')
        tree=ast.parse(path.read_text())
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in
                   {'xywh2xyxy','compute_iou','non_max_suppression','nms'}]
        namespace={'np':np}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'<professor pure functions>','exec'),namespace)
        raw=np.zeros((1,16380,85),np.float32)
        raw[0,:4,:6]=[[100,100,40,40,.9,.7],[102,102,40,40,.7,.9],
                      [300,300,10,10,.8,.2],[0,0,1,1,.2,.9]]
        np.testing.assert_allclose(decode(raw),namespace['nms'](raw),rtol=1e-6)


class InputTests(unittest.TestCase):
    def test_missing(self):
        with self.assertRaises(FileNotFoundError):
            with Frames('/does-not-exist.mp4'): pass
    def test_bad_extension(self):
        with tempfile.NamedTemporaryFile(suffix='.txt') as f:
            with self.assertRaises(ValueError):
                with Frames(f.name): pass
    def test_corrupt_image(self):
        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            with self.assertRaises(ValueError):
                with Frames(f.name): pass
    def test_video_eof(self):
        with tempfile.TemporaryDirectory() as t:
            p=str(Path(t)/'test.avi')
            writer=cv2.VideoWriter(p,cv2.VideoWriter_fourcc(*'MJPG'),20,(64,48))
            self.assertTrue(writer.isOpened())
            for _ in range(3): writer.write(np.zeros((48,64,3),np.uint8))
            writer.release()
            with Frames(p) as frames:
                self.assertEqual(len(list(frames)),3)
            self.assertFalse(frames.cap.isOpened())
    def test_camera_failure_cleanup(self):
        with patch('p3.pipeline.cv2.VideoCapture') as factory:
            cap=factory.return_value;cap.isOpened.return_value=False
            with self.assertRaises(RuntimeError):
                with Frames('0',camera=True): pass
            cap.release.assert_called_once()
    def test_camera_disconnect_cleanup(self):
        with patch('p3.pipeline.cv2.VideoCapture') as factory:
            cap=factory.return_value;cap.isOpened.return_value=True;cap.get.return_value=30
            cap.read.return_value=(False,None)
            with self.assertRaises(RuntimeError):
                with Frames('0',camera=True) as frames: list(frames)
            cap.release.assert_called_once()
    def test_stats(self):
        s=stats([1,2,3]);self.assertEqual(s['count'],3);self.assertEqual(s['median'],2)
    def test_bad_stats(self):
        with self.assertRaises(ValueError): stats([])
    def test_bad_benchmark_size(self):
        with self.assertRaises(ValueError): benchmark('none',samples=1)


class ModelIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEL.is_file():
            raise unittest.SkipTest('ONNX model missing: external/aJLL/bodyjim/yolov5n_flat.onnx (not in git; no automatic download)')
        cls.detector=Detector()
        cls.image=cv2.imread(str(ROOT/'projects/project3/artifacts/bus.jpg'))
        if cls.image is None: raise unittest.SkipTest('download bus fixture per README first')
    def test_model_io(self):
        self.assertEqual(self.detector.input.shape,[1,3,416,640])
    def test_real_image_detections(self):
        ds,_=self.detector.predict(self.image)
        self.assertTrue(any(d['label']=='person' for d in ds))
        for d in ds:
            x1,y1,x2,y2=d['box'];self.assertTrue(0<=x1<=x2<=self.image.shape[1])
            self.assertTrue(0<=y1<=y2<=self.image.shape[0]);self.assertTrue(.3<d['objectness']<=1)
    def test_deterministic_reuse(self):
        session=self.detector.session
        a,_=self.detector.predict(self.image);b,_=self.detector.predict(self.image)
        self.assertIs(session,self.detector.session);self.assertEqual(a,b)
    def test_original_preprocessing_and_real_nms(self):
        path=ROOT/'external/aJLL/bodyjim/YoloPC.py'
        if not path.is_file():
            self.skipTest('YoloPC.py missing: external/aJLL/bodyjim/YoloPC.py (not in git)')
        tree=ast.parse(path.read_text())
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in
               {'xywh2xyxy','compute_iou','non_max_suppression','nms'}]
        runner=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='YoloRunner')
        method=next(n for n in runner.body if isinstance(n,ast.FunctionDef) and n.name=='preprocess_image')
        namespace={'np':np,'cv2':cv2,'INPUT_SHAPE':(640,416)}
        exec(compile(ast.Module(body=nodes+[method],type_ignores=[]),'<reference math>','exec'),namespace)
        tensor=self.detector.preprocess(self.image)
        np.testing.assert_array_equal(tensor,namespace['preprocess_image'](None,self.image))
        raw=self.detector.session.run(None,{'image':tensor})[0]
        np.testing.assert_allclose(decode(raw),namespace['nms'](raw.reshape(1,16380,85)),rtol=1e-6)
    def test_file_export(self):
        with tempfile.TemporaryDirectory() as t:
            rows=run(self.detector,ROOT/'projects/project3/artifacts/bus.jpg',Path(t)/'out')
            self.assertEqual(len(rows),1);self.assertTrue((Path(t)/'out/preview.png').is_file())
    def test_output_overwrite_refused(self):
        with tempfile.TemporaryDirectory() as t:
            Path(t,'important.txt').write_text('keep')
            with self.assertRaises(FileExistsError): run(self.detector,'none',t)
    def test_overlay_shape(self):
        self.assertEqual(render(self.image,[],{}).shape,self.image.shape)


class Run2Tests(unittest.TestCase):
    def test_normal(self):
        b=MockBindings();r=run_ui(b,ticks=2,sleep=lambda _:None)
        self.assertEqual(len(b.sent),8);self.assertEqual(r['events'],[])
        self.assertEqual(b.stopped,list(reversed(PROCESSES)))
    def test_invalid_data(self):
        b=MockBindings();m=build_messages(b.messaging,b.log);m['deviceState'].deviceState.started='yes'
        with self.assertRaises(ValueError): validate(m)
    def test_timeout_recovery(self):
        b=MockBindings(TimeoutError('timeout'));r=run_ui(b,sleep=lambda _:None)
        self.assertIn('publisher_recreated',r['events']);self.assertEqual(b.publishers,2)
    def test_disconnect_recovery(self):
        b=MockBindings(ConnectionError('disconnected'));r=run_ui(b,sleep=lambda _:None)
        self.assertIn('ConnectionError',r['events']);self.assertEqual(len(b.sent),20)
    def test_error_cleanup(self):
        b=MockBindings(ValueError('invalid publish'))
        with self.assertRaises(ValueError): run_ui(b,sleep=lambda _:None)
        self.assertEqual(len(b.stopped),4)
    def test_no_retry_cleanup(self):
        b=MockBindings(TimeoutError('timeout'))
        with self.assertRaises(TimeoutError): run_ui(b,retries=0,sleep=lambda _:None)
        self.assertEqual(len(b.stopped),4)
    def test_partial_start_cleanup(self):
        b=MockBindings(fail_start='ui')
        with self.assertRaises(RuntimeError): run_ui(b,sleep=lambda _:None)
        self.assertEqual(b.stopped,['ui','camerad'])
    def test_exact_reference_main(self):
        path=ROOT/'projects/project3/artifacts/reference/uiview.py'
        if not path.exists(): self.skipTest('exact course uiview unavailable')
        tree=ast.parse(path.read_text())
        guard=next(n for n in tree.body if isinstance(n,ast.If))
        b=MockBindings()
        calls=[]
        def stop(_):
            calls.append(1)
            if len(calls)>1: raise KeyboardInterrupt
        ns={'car':b.car,'Params':lambda:b.params,'managed_processes':b.processes,
            'messaging':b.messaging,'log':b.log,'time':type('Time',(),{'sleep':staticmethod(stop)})}
        exec(compile(ast.Module(body=guard.body,type_ignores=[]),'<exact course main, injected mocks>','exec'),ns)
        self.assertEqual(b.started,PROCESSES);self.assertEqual(len(b.stopped),4)
        self.assertEqual(len(b.sent),4)
        validate(ns['msgs'])
