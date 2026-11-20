"""Build a static comparison from real recorded predictions; never fabricate results."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

from evaluate import parse_svg


def render_source(source: str) -> str | None:
    """Normalize valid SVG for HTML; invalid outputs stay visible as code only."""
    try:
        return ET.tostring(parse_svg(source), encoding="unicode")
    except ValueError:
        return None


def motion_summary(row: dict) -> str:
    """Describe the visible motion while leaving the exact model prompt inspectable."""
    actions = []
    for motion in row["specification"]:
        peak = motion["peak"]
        actions.append(
            {
                "translate": f"rise {abs(peak):g} units",
                "rotate": f"rotate {peak:g}° clockwise",
                "scale": f"grow to {peak:g}× its size",
                "opacity": f"fade to {peak * 100:g}% opacity",
            }[motion["kind"]]
        )
    return (
        f"Make the {row['family']} "
        + " and ".join(actions)
        + f". Pause at the peak, then return. Repeat every {row['specification'][0]['duration']} seconds."
    )


def build(data: Path, run: Path, split: str, output: Path) -> None:
    """Join both prediction arms by ID and expose every evaluated example."""
    rows = {
        row["id"]: row
        for row in (
            json.loads(line)
            for line in (data / f"{split}.jsonl").read_text().splitlines()
        )
    }
    arms = {
        arm: {
            row["id"]: row
            for row in (
                json.loads(line)
                for line in (run / f"{arm}-{split}.jsonl").read_text().splitlines()
            )
        }
        for arm in ("base", "finetuned")
    }
    if set(arms["base"]) != set(arms["finetuned"]):
        raise ValueError("Both comparison arms must cover exactly the same examples")
    examples = []
    for identity in arms["base"]:
        row = rows[identity]
        views = {}
        for arm in arms:
            result = arms[arm][identity]
            source = render_source(result["prediction"])
            views[arm] = {
                **result,
                "renderable": source is not None,
                "render_source": source or "",
            }
        examples.append(
            {
                "id": identity,
                "family": row["family"],
                "instruction": row["instruction"],
                "summary": motion_summary(row),
                "input_svg": row["input_svg"],
                "duration": row["specification"][0]["duration"],
                **views,
            }
        )
    metadata = json.loads((run / "run.json").read_text())
    dataset = (
        json.dumps(examples)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    scores = {
        arm: sum(row[arm]["score"]["motion_pass"] for row in examples) for arm in arms
    }
    subtitle = f"{metadata['model']} · LoRA · {len(examples)} {split} examples"
    disclaimer = (
        "Preliminary GPU smoke run. This small validation sample is not a held-out test result."
        if metadata["eval_limit"]
        else "Every held-out test example is available below. Same input, decoding settings, and budget; no repair loop."
    )
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SVG Motion Lab</title><style>
    :root{color-scheme:dark;font-family:Inter,system-ui,sans-serif;background:#0b1020;color:#e8eefc}*{box-sizing:border-box}body{max-width:1200px;margin:auto;padding:44px 24px}h1{font-size:clamp(32px,5vw,58px);letter-spacing:-2px;margin:10px 0}h2{font-size:20px;margin:0}.eyebrow{color:#68e2c2;letter-spacing:3px;font-size:12px;font-weight:700}.muted{color:#a4b0c9;line-height:1.6}header{margin-bottom:32px}.metrics,.comparison{display:grid;grid-template-columns:1fr 1fr;gap:20px}.metric,.panel,.controls{border:1px solid #28324b;background:#121a2c;border-radius:18px;padding:22px}.metric strong{font-size:36px;display:block;margin-top:8px}.comparison{margin-top:20px}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:10px}.badge{font-size:12px;padding:6px 10px;border-radius:20px;background:#293650}.pass{background:#153e36;color:#86f6cf}.fail{background:#462d34;color:#ffbdc4}iframe{width:100%;height:340px;border:0;background:radial-gradient(ellipse,#20314c,#121a2c);border-radius:12px;margin-top:16px}.controls{margin-top:24px}.row{display:flex;align-items:center;flex-wrap:wrap;gap:14px}select,button{border:1px solid #3e4c6b;background:#1d2940;color:#f3f6ff;padding:11px 16px;border-radius:9px;font:inherit}button{cursor:pointer}button:hover{background:#2b3b59}input[type=range]{flex:1;min-width:160px;accent-color:#68e2c2}#instruction{line-height:1.65}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#0c1322;padding:14px;border-radius:10px;max-height:250px;overflow:auto}.reason{min-height:42px;font-size:13px;color:#a4b0c9}footer{margin-top:28px;font-size:13px}.error{height:340px;display:grid;place-items:center;color:#ffbdc4}@media(max-width:650px){.comparison,.metrics{grid-template-columns:1fr}body{padding:26px 16px}}
    </style></head><body><header><div class="eyebrow">AN EXPERIMENT IN LEARNING MOTION</div><h1>SVG Motion Lab</h1><p class="muted">A still drawing. One instruction. Two versions of the same model.</p><p class="muted">SUBTITLE</p></header><section class="metrics"><div class="metric">Base model · complete tasks passed<strong>BASESCORE / TOTAL</strong></div><div class="metric">Fine-tuned · complete tasks passed<strong>TUNEDSCORE / TOTAL</strong></div></section><p class="muted">DISCLAIMER</p><section class="controls"><div class="row"><label for="example">Example</label><select id="example"></select><button id="restart">Replay both</button><button id="pause">Pause</button></div><p id="summary"></p><details><summary>Exact model instruction</summary><p id="instruction"></p></details><div class="row"><label for="timeline">Scrub</label><input id="timeline" type="range" min="0" max="1000" value="0"><span id="time">0.00 s</span></div></section><main class="comparison"><section class="panel"><div class="panel-head"><h2>Base model</h2><span id="base-badge" class="badge"></span></div><div id="base-view"></div><p id="base-reason" class="reason"></p><details><summary>Generated SVG</summary><pre id="base-code"></pre></details></section><section class="panel"><div class="panel-head"><h2>Fine-tuned model</h2><span id="finetuned-badge" class="badge"></span></div><div id="finetuned-view"></div><p id="finetuned-reason" class="reason"></p><details><summary>Generated SVG</summary><pre id="finetuned-code"></pre></details></section></main><footer class="muted">Checks: valid SVG, original drawing preserved, and browser-measured position, rotation, scale and opacity at fixed times. Synthetic task distribution; this does not establish general animation quality. No model inference runs in your browser.</footer><script id="examples" type="application/json">EXAMPLES</script><script>
    const examples=JSON.parse(document.getElementById('examples').textContent);
    const select=document.getElementById('example'),timeline=document.getElementById('timeline');
    let current=examples[0],paused=false;
    for(const [i,row] of examples.entries()){const option=document.createElement('option');option.value=i;option.textContent=`${row.id} · ${row.family}`;select.append(option);}
    function svgs(){return [...document.querySelectorAll('iframe')].map(frame=>frame.contentDocument?.querySelector('svg')).filter(Boolean);}
    function sync(t,stop){for(const svg of svgs()){svg.pauseAnimations();svg.setCurrentTime(t);if(!stop)svg.unpauseAnimations();}paused=stop;document.getElementById('pause').textContent=stop?'Play':'Pause';}
    function show(index){current=examples[index];document.getElementById('instruction').textContent=current.instruction;document.getElementById('summary').textContent=current.summary;timeline.value=0;document.getElementById('time').textContent='0.00 s';let loaded=0;const count=['base','finetuned'].filter(arm=>current[arm].renderable).length;
      for(const arm of ['base','finetuned']){const result=current[arm],view=document.getElementById(arm+'-view');view.replaceChildren();const badge=document.getElementById(arm+'-badge');badge.textContent=result.score.motion_pass?'Passed':'Failed';badge.className='badge '+(result.score.motion_pass?'pass':'fail');document.getElementById(arm+'-reason').textContent=result.score.reason;document.getElementById(arm+'-code').textContent=result.prediction;
        if(result.renderable){const frame=document.createElement('iframe');frame.title=arm+' animation';frame.setAttribute('sandbox','allow-same-origin');frame.srcdoc=`<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'"><style>body{margin:0;display:grid;place-items:center;height:100vh;background:#101b2f}svg{width:100%;height:100%}</style>${result.render_source}`;frame.onload=()=>{loaded++;if(loaded===count)sync(0,false)};view.append(frame);}else{const message=document.createElement('div');message.className='error';message.textContent='Output could not be safely rendered';view.append(message);}}
    }
    select.onchange=()=>show(Number(select.value));document.getElementById('restart').onclick=()=>{timeline.value=0;sync(0,false)};document.getElementById('pause').onclick=()=>{const t=svgs()[0]?.getCurrentTime()||0;sync(t,!paused)};timeline.oninput=()=>{const t=Number(timeline.value)/1000*current.duration;sync(t,true);document.getElementById('time').textContent=t.toFixed(2)+' s'};show(0);
    </script></body></html>"""
    replacements = {
        "SUBTITLE": escape(subtitle),
        "BASESCORE": str(scores["base"]),
        "TUNEDSCORE": str(scores["finetuned"]),
        "TOTAL": str(len(examples)),
        "DISCLAIMER": escape(disclaimer),
        "EXAMPLES": dataset,
    }
    for key, value in replacements.items():
        html = html.replace(key, value)
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(html)
    (output / "comparison.json").write_text(json.dumps(examples, indent=2))
    print(
        json.dumps(
            {
                "examples": len(examples),
                "scores": scores,
                "path": str(output / "index.html"),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    parser.add_argument("--output", type=Path, default=Path("demo"))
    args = parser.parse_args()
    build(args.data, args.run, args.split, args.output)
