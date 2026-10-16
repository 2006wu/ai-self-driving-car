"""Human-readable reports; raw context/trace stays in the saved JSON record."""
import json


def number(value):
    if value is None: return '未驗證'
    return str(value) if isinstance(value,int) else f'{value:.6g}'


def format_report(result):
    mode=result.get('mode','unknown');lines=[f'# {mode.title()} — {result.get("model","offline")}',
        '', '內容狀態：需要人工覆核；程式驗證資料來源與有限格式條件，不代表所有模型敘述正確。']
    reference=result.get('verified_reference') or result.get('numerical_reference') or {}
    if mode=='diagnosis':
        lines+=['','## 已核對事實（本機證據）','',
                '| Domain | Checkpoint | 非正近端車道寬度幀數 | 近端路徑最大座標幅值 m |',
                '|---|---|---:|---:|']
        for domain,roles in reference.get('domain_reference',{}).items():
            for role,metrics in roles.items():
                lines.append(f"| {domain} | {role} | {number(metrics.get('lane_width_near_nonpositive_frames'))} | {number(metrics.get('path_near_abs_max_m'))} |")
        train=reference.get('training',{})
        if train: lines+=['',f"訓練 {train['epochs']} epochs；最佳 validation loss {number(train['best_val_loss'])}，epoch {train['best_epoch']}。"]
        lines+=['','來源：`/output/step6/{usa,taiwan}/comparison.json`；原始精度與 SHA-256 見 result.json。',
                '', '## 模型解讀（待覆核）','',str(result.get('report','')),
                '', '## 尚未證實／限制','',reference.get('allowed_next_action',''),
                '駕駛準確度、閉迴路安全、單一因果機制與部署適用性均未由此報告確立。']
    elif mode in ('unified','vision'):
        metadata=result.get('metadata',{});report=result.get('report',{})
        lines+=['','## 已核對資料','',
                f"圖片：{metadata.get('image','unknown')}；domain={metadata.get('domain')}，checkpoint={metadata.get('role')}。"]
        metrics=reference.get('metrics',{})
        if metrics:
            for key in ('frames','path_near_abs_max_m','path_near_mean_m','lane_width_near_nonpositive_frames'):
                if key in metrics: lines.append(f'- `{key}` = {number(metrics[key])}')
            lines+=['',f"來源：`{reference['source']['path']}`；統計範圍為完整 clip 的近端樣點，並非這張圖的誤差。"]
        lines+=['','## 模型視覺觀察與解讀（待覆核）','']
        labels={'observed_scene':'場景','path_assessment':'路徑','left_lane_assessment':'左車道',
                'right_lane_assessment':'右車道','lead_assessment':'前車對應',
                'potential_failure_pattern':'可能異常','confidence':'模型信心（非校準機率）',
                'numerical_agreements':'數值對照','numerical_disagreements':'無法比較／不同之處',
                'bounded_interpretation':'有限解讀'}
        for key,label in labels.items():
            if key in report: lines+= [f'**{label}：** {report[key]}','']
        lines+=['## 尚未證實／限制','',report.get('limitations',result.get('limitations','')),
                '空間鋸齒、近端座標統計與跨幀變化是不同量；不能據此推論鋸齒被時間平均消除。']
    else:
        lines+=['',json.dumps(result,indent=2,ensure_ascii=False)]
    tools=result.get('tools',[])
    lines+=['','## 查證紀錄','',
            f"模型工具呼叫：{len(tools)}；未回報錯誤：{sum(not t['error'] for t in tools)}。",
            '本機預載證據不計為模型主動呼叫工具。']
    if tools: lines.append('工具：'+', '.join(t['name']+(' [ERROR]' if t['error'] else '') for t in tools))
    if result.get('tool_verification',{}).get('selection')=='APPLICATION_REQUIRED_MODEL_CALLS':
        lines.append('verify：程式指定必要查證工具，模型發出 function calls；不代表模型自主選擇工具。')
    return '\n'.join(lines)+'\n'
