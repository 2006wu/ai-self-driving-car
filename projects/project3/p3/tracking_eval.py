"""Annotated box-sequence evaluation; never invent accuracy from unlabeled video.

ID metrics: global maximum-cardinality identity assignment using all IoU-qualified
potential matches, following TrackEval's Identity formulation. CLEAR-like local
counts use deterministic maximum-cardinality/IoU frame assignment; not a claim of
complete MOTChallenge preprocessing/ignore-region compatibility.
"""
from collections import Counter, defaultdict
import math
from .detection import iou
from .follow import valid_box


def maximum_assignment(weights):
    """Exact rectangular maximum-weight assignment (Hungarian, zero dummy nodes)."""
    if not weights or not weights[0]: return []
    rows, cols = len(weights), len(weights[0])
    if any(len(r) != cols or any(not math.isfinite(x) or x < 0 for x in r) for r in weights):
        raise ValueError('assignment weights must be rectangular, finite and nonnegative')
    n = max(rows, cols)
    # Standard 1-indexed shortest augmenting path Hungarian minimizer.
    cost = [[0.]*(n+1) for _ in range(n+1)]
    for r in range(rows):
        for c in range(cols): cost[r+1][c+1] = -weights[r][c]
    u, v, p, way = [0.]*(n+1), [0.]*(n+1), [0]*(n+1), [0]*(n+1)
    for i in range(1, n+1):
        p[0], j0 = i, 0
        minimum, used = [float('inf')]*(n+1), [False]*(n+1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], float('inf'), 0
            for j in range(1, n+1):
                if not used[j]:
                    current = cost[i0][j]-u[i0]-v[j]
                    if current < minimum[j]: minimum[j], way[j] = current, j0
                    if minimum[j] < delta: delta, j1 = minimum[j], j
            for j in range(n+1):
                if used[j]: u[p[j]] += delta; v[j] -= delta
                else: minimum[j] -= delta
            j0 = j1
            if p[j0] == 0: break
        while True:
            j1 = way[j0];p[j0] = p[j1];j0 = j1
            if j0 == 0: break
    return [(p[j]-1, j-1) for j in range(1,n+1)
            if 0 < p[j] <= rows and j <= cols and weights[p[j]-1][j-1] > 0]


def evaluate_sequence(frames, annotation_kind, iou_threshold=.5, target_gt_id=None):
    if annotation_kind not in {'synthetic_ground_truth', 'human_ground_truth'}:
        raise ValueError('explicit trustworthy annotation_kind required; unlabeled data uses proxies only')
    if not 0 < iou_threshold <= 1 or not frames: raise ValueError('invalid evaluation configuration')
    counts, gt_totals, pred_totals = Counter(), Counter(), Counter()
    last_id, interrupted, was_matched = {}, defaultdict(bool), set()
    matched_counts, longest, streak = Counter(), Counter(), Counter()
    id_switches = fragments = matches_total = gt_total = pred_total = 0
    target_initial = None;target_gaps = target_recovered = 0;target_absent = False
    per_frame = []
    previous_frame = -1
    for frame in frames:
        fid = frame['frame']
        if isinstance(fid, bool) or not isinstance(fid, int) or fid <= previous_frame:
            raise ValueError('frames must be strictly increasing nonnegative integers')
        if fid != previous_frame+1:
            streak.clear()
        previous_frame = fid
        gt, pred = frame['ground_truth'], frame['predictions']
        for objects in (gt, pred):
            ids = [obj['id'] for obj in objects]
            if len(set(ids)) != len(ids) or any(isinstance(k,bool) or not isinstance(k,int) or k <= 0 for k in ids):
                raise ValueError('IDs must be unique positive integers per frame')
            if any(not valid_box(obj.get('box')) for obj in objects): raise ValueError('invalid evaluation box')
        for g in gt: gt_totals[g['id']] += 1
        for p in pred: pred_totals[p['id']] += 1
        gt_total += len(gt); pred_total += len(pred)
        similarity = [[float(iou(g['box'], [p['box']])[0]) for p in pred] for g in gt]
        for i,g in enumerate(gt):
            for j,p in enumerate(pred):
                if similarity[i][j] >= iou_threshold: counts[g['id'],p['id']] += 1
        # One extra valid match outweighs any possible sum of IoU improvements.
        bonus = min(len(gt),len(pred))+1
        pairs = maximum_assignment([[bonus+s if s >= iou_threshold else 0 for s in row] for row in similarity])
        matched = {gt[i]['id']:pred[j]['id'] for i,j in pairs}
        matches_total += len(pairs)
        present = {g['id'] for g in gt}
        for g in list(streak):
            if g not in matched: streak[g] = 0
        for g in present:
            if g in matched:
                pid = matched[g]
                if g in last_id and last_id[g] != pid: id_switches += 1
                if g in was_matched and interrupted[g]: fragments += 1
                last_id[g], interrupted[g] = pid, False
                was_matched.add(g);matched_counts[g] += 1;streak[g] += 1
                longest[g] = max(longest[g],streak[g])
            elif g in was_matched: interrupted[g] = True
        if target_gt_id is not None:
            if target_gt_id not in present or target_gt_id not in matched:
                if target_initial is not None: target_absent = True
            else:
                pid = matched[target_gt_id]
                if target_initial is None: target_initial = pid
                if target_absent:
                    target_gaps += 1
                    target_recovered += int(pid == target_initial)
                    target_absent = False
        per_frame.append({'frame':fid,'matches':matched})
    gids, pids = sorted(gt_totals), sorted(pred_totals)
    matrix = [[counts[g,p] for p in pids] for g in gids]
    global_pairs = maximum_assignment(matrix)
    idtp = sum(matrix[i][j] for i,j in global_pairs)
    idfn, idfp = gt_total-idtp, pred_total-idtp
    return {'annotation_kind':annotation_kind,'scope':'synthetic evaluator logic only' if annotation_kind.startswith('synthetic') else 'annotated supplied sequence only',
            'iou_threshold':iou_threshold,'IDTP':idtp,'IDFN':idfn,'IDFP':idfp,
            'IDF1':2*idtp/(gt_total+pred_total) if gt_total+pred_total else None,
            'ID_precision':idtp/pred_total if pred_total else None,'ID_recall':idtp/gt_total if gt_total else None,
            'ID_switches':id_switches,'track_fragmentations':fragments,
            'detection_matches':matches_total,'ground_truth_detections':gt_total,'predicted_detections':pred_total,
            'track_continuity':{str(g):{'matched_visible_fraction':matched_counts[g]/gt_totals[g],
                    'longest_consecutive_match_fraction':longest[g]/gt_totals[g]} for g in gids},
            'target_recovery':{'eligible_completed_gaps':target_gaps,'same_initial_id_recoveries':target_recovered,
                    'rate':target_recovered/target_gaps if target_gaps else None},
            'matching': 'global identity assignment counts all IoU-qualified pairs; local frame assignment maximizes match count then IoU',
            'fragmentation_definition':'matched -> unmatched while GT present -> matched; absent GT alone is not an FN/fragment',
            'switch_definition':'new prediction ID versus last matched ID for the same annotated GT, including across gaps',
            'limitations':'No MOT ignore regions/classes/visibility preprocessing; target ID recovery is not person recognition or permission to resume follow.',
            'per_frame':per_frame}
