"""Small authored box trajectories with known identities, never fake video accuracy."""
from .tracking import Tracker
from .tracking_eval import evaluate_sequence


def item(identity, x, width=40, y=100, height=100):
    return {'id':identity,'box':[x,y,x+width,y+height]}


def scenario_suite():
    sequences = {}
    sequences['A_left'] = [[item(1,180-3*t)] for t in range(30)]
    sequences['A_right'] = [[item(1,20+3*t)] for t in range(30)]
    sequences['A_approach'] = [[item(1,100-t,40+2*t)] for t in range(25)]
    sequences['A_recede'] = list(reversed(sequences['A_approach']))
    sequences['A_short_exit'] = [[item(1,100)] if t not in [8,9,10] else [] for t in range(22)]
    sequences['B_simultaneous_opposite'] = [[item(1,30+2*t),item(2,350-2*t)] for t in range(30)]
    sequences['B_crossing'] = [[item(1,40+5*t),item(2,243-5*t)] for t in range(42)]
    sequences['B_close_parallel'] = [[item(1,20+2*t),item(2,65+2*t)] for t in range(30)]
    sequences['B_partial_overlap'] = [[item(1,20+2*t),item(2,45+2*t)] for t in range(30)]
    sequences['C_short_occlusion'] = [[item(1,100)] for _ in range(22)]
    sequences['C_long_occlusion'] = [[item(1,100)] for _ in range(28)]
    sequences['C_occluded_separation'] = sequences['B_crossing']
    results = []
    for name, ground in sequences.items():
        tracker = Tracker();frames=[]
        for t, gt in enumerate(ground):
            visible = gt
            if name == 'C_short_occlusion' and 8 <= t <= 10: visible=[]
            if name == 'C_long_occlusion' and 8 <= t <= 17: visible=[]
            if name == 'C_occluded_separation' and 17 <= t <= 23: visible=[]
            # Ground truth remains annotated during synthetic missed detections;
            # A_short_exit intentionally has no GT while physically out-of-view.
            dets=[{'class_id':0,'label':'person','objectness':.9,'box':g['box']} for g in visible]
            tracks=tracker.update(dets)
            frames.append({'frame':t,'ground_truth':gt,
                           'predictions':[{'id':tr['id'],'box':tr['box']} for tr in tracks if tr['state']=='tracked']})
        results.append({'scenario':name,'metrics':evaluate_sequence(frames,'synthetic_ground_truth',target_gt_id=1),
                        'frames':frames})
    return {'data_source':'authored deterministic box fixtures; no dataset download and no actual persons',
            'tracker':'unchanged greedy IoU threshold=.3 max_missed=5',
            'real_world_accuracy':'NOT TESTED; synthetic scores validate behavior/metric code only',
            'scenarios':results}
