#!/usr/bin/env python3
"""Replay an evaluation corpus through `review-pr` and score where the
brief put each hand-labelled must-read item. Run it after every change to a
review skill, step file or detector: a change that makes the review miss
things shows up as a lower recall, or as a must-read item classified skim.

Usage: python3 -I tools/eval_review.py run <corpus> [--out <dir>] [--agent <command> | --agent none]
                                           [--case <name>]... [--timeout <seconds>] [--compare <report.json>]
       python3 -I tools/eval_review.py score <corpus> <out> [--compare <report.json>]

The corpus is a directory outside this repository (real PRs come from
private repositories: never commit one). Each `<name>.json` at its top is
one case:

  {"repo": "../clones/shop",            a clone, relative to the corpus or absolute
   "target": "<base sha>..<head sha>",   or "pr": 52 (read with gh)
   "spec": "#35",                        optional: "#N" or a path; or "no_spec": true
   "must_read": ["db/migrations/002_drop_email.sql",
                 {"path": "src/Billing/Invoice.php", "why": "renamed public method"}],
   "unnecessary": ["src/Kernel.php"]}    must-read files the labeller judged unnecessary

`run` replays each case as `review-pr` does: run.py, then each judgment
step its `STEP:` lines name, given to `--agent` as "Follow <step file> on
the run directory <run>." (a command template with `{prompt}`, `{step}`,
`{axis}`, `{run}` and `{skill}`, run in the run directory; `none` runs no
step, detectors only), then brief.py, validate.py and check-pointers.py.
The runs go under `<out>/state` (its own XDG_STATE_HOME, so every case is
round 1), each step's output in `<out>/step-<case>-<axis>.log`, what
happened in `<out>/runs.json`, the score in
`<out>/report.json`. `<out>` defaults to
$XDG_STATE_HOME/birdiz-review/eval/<UTC time>/.

`score` scores the runs of an earlier `run` again, after the labels
changed (an unlabelled must-read file marked necessary or unnecessary),
without replaying anything.

Metrics, per case and in total:
  recall   must-read items the brief puts in Must read (primary)
  skim     must-read items the brief classifies skim: each one is a failure
  noise    must-read files of the brief the labeller marks unnecessary;
           the ones neither labelled must-read nor unnecessary are listed
           as unlabelled, to label
A case also fails when its run is refused, a step fails or times out, or
validate.py or check-pointers.py reports a defect. `--compare` lists the
items an earlier report recalled and this one misses, and the reverse.

Exit status: 0 no failure, 1 a failure, 2 usage, corpus or output error.
Python 3.8 or later, standard library only.
"""
import datetime
import glob
import json
import os
import re
import shlex
import subprocess
import sys

sys.dont_write_bytecode = True  # leave no __pycache__ in the plugin

VERSION = "eval-review@0.1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PLUGIN = os.path.join(REPO, "plugins", "birdiz-review")
SKILL = os.path.join(PLUGIN, "skills", "review-pr")
SCRIPTS = os.path.join(SKILL, "scripts")
for _p in (os.path.join(PLUGIN, "core"), SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_format as fmt  # noqa: E402

DEFAULT_AGENT = ('claude -p {prompt} --permission-mode acceptEdits --add-dir {skill}'
                 ' --allowedTools "Bash(python3 -I *)"')
NO_AGENT = "not run (--agent none)"
PROMPT = "Follow `{step}` on the run directory `{run}`."
CASE_KEYS = {"repo", "target", "pr", "spec", "no_spec", "must_read", "unnecessary"}
DEFECT = re.compile(r"^(ERROR|MISMATCH|MISSING)\b")
LOOSE = re.compile(r"^[-*]\s+(F-[A-Z0-9]+-\d+)\b")


class CorpusError(Exception):
    pass


# --- The corpus ---------------------------------------------------------------

def inside(path, top):
    path, top = os.path.realpath(path), os.path.realpath(top)
    return path == top or path.startswith(top + os.sep)


def load_case(path):
    """One case file, checked: a typo in a key or a path labelled twice is
    a corpus error, not a silent zero."""
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        raise CorpusError("%s: %s" % (path, e))
    if not isinstance(data, dict):
        raise CorpusError("%s: not a JSON object" % path)
    unknown = sorted(set(data) - CASE_KEYS)
    if unknown:
        raise CorpusError("%s: unknown keys %s" % (path, ", ".join(unknown)))
    if not isinstance(data.get("repo"), str):
        raise CorpusError("%s: `repo` is required, a path" % path)
    if ("target" in data) == ("pr" in data):
        raise CorpusError("%s: give one of `target` (base..head) or `pr`" % path)
    if "pr" in data and not (isinstance(data["pr"], int) and data["pr"] > 0):
        raise CorpusError("%s: `pr` is a pull request number" % path)
    if "target" in data and not isinstance(data["target"], str):
        raise CorpusError("%s: `target` is a branch or base..head" % path)
    if "spec" in data and (not isinstance(data["spec"], str) or data.get("no_spec")):
        raise CorpusError("%s: `spec` is \"#N\" or a path, and excludes `no_spec`" % path)
    items = []
    for item in data.get("must_read", []):
        if isinstance(item, str):
            item = {"path": item}
        if not (isinstance(item, dict) and isinstance(item.get("path"), str) and set(item) <= {"path", "why"}):
            raise CorpusError("%s: a must_read item is a path or {\"path\", \"why\"}" % path)
        items.append({"path": item["path"], "why": item.get("why", "")})
    unnecessary = data.get("unnecessary", [])
    if not (isinstance(unnecessary, list) and all(isinstance(p, str) for p in unnecessary)):
        raise CorpusError("%s: `unnecessary` is a list of paths" % path)
    paths = [i["path"] for i in items]
    twice = sorted({p for p in paths if paths.count(p) > 1} | (set(paths) & set(unnecessary)))
    if twice:
        raise CorpusError("%s: labelled twice: %s" % (path, ", ".join(twice)))
    repo = os.path.expanduser(data["repo"])
    if not os.path.isabs(repo):
        repo = os.path.join(os.path.dirname(os.path.abspath(path)), repo)
    return {"name": name, "file": os.path.abspath(path), "repo": os.path.normpath(repo),
            "target": data.get("target"), "pr": data.get("pr"), "spec": data.get("spec"),
            "no_spec": bool(data.get("no_spec")), "must_read": items, "unnecessary": list(unnecessary)}


def load_corpus(corpus, names=()):
    if not os.path.isdir(corpus):
        raise CorpusError("not a directory: %s" % corpus)
    if inside(corpus, REPO):
        raise CorpusError("the corpus is inside %s: it holds real PRs, keep it outside this public repository" % REPO)
    cases = [load_case(p) for p in sorted(glob.glob(os.path.join(corpus, "*.json")))]
    if not cases:
        raise CorpusError("no case (<name>.json) in %s" % corpus)
    if names:
        missing = sorted(set(names) - {c["name"] for c in cases})
        if missing:
            raise CorpusError("no case named %s in %s" % (", ".join(missing), corpus))
        cases = [c for c in cases if c["name"] in names]
    return cases


# --- Replay -------------------------------------------------------------------

def script(name, *args, env=None, cwd=None):
    done = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, name)] + list(args),
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, env=env, cwd=cwd)
    return done.returncode, done.stdout, done.stderr


def agent_command(template, axis, step, run):
    prompt = PROMPT.format(step=step, run=run)
    values = {"prompt": prompt, "step": step, "axis": axis, "run": run, "skill": SKILL}
    return [part.format(**values) for part in shlex.split(template)]


def replay(case, state, agent, timeout):
    """Run one case as `review-pr` does. Returns what happened: the run
    directory, each step, each check and the error that stopped it."""
    env = dict(os.environ, XDG_STATE_HOME=state)
    out = {"name": case["name"], "run": None, "steps": [], "checks": [], "error": None, "ask": None}
    args = ["--pr", str(case["pr"])] if case["pr"] else [case["target"]]
    args += ["--repo", case["repo"]]
    if case["spec"]:
        args += ["--spec", case["spec"]]
    elif case["no_spec"]:
        args.append("--no-spec")
    code, stdout, stderr = script("run.py", *args, env=env, cwd=state)
    lines = stdout.strip().split("\n")
    if code != 0 or not lines[-1].startswith("RUN: "):
        out["error"] = "run.py exit %d: %s" % (code, (stderr or stdout).strip().split("\n")[-1])
        return out
    run = lines[-1][len("RUN: "):]
    out["run"] = run
    out["ask"] = next((ln[len("ASK: "):] for ln in lines if ln.startswith("ASK: ")), None)
    steps = [ln[len("STEP: "):].split(" ", 1) for ln in lines if ln.startswith("STEP: ")]
    ran = []
    for axis, step in steps:
        if agent == "none":
            out["steps"].append({"axis": axis, "status": NO_AGENT})
            continue
        cmd = agent_command(agent, axis, step, run)
        try:
            done = subprocess.run(cmd, cwd=run, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, universal_newlines=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            out["steps"].append({"axis": axis, "status": "timed out after %ds" % timeout})
            continue
        except OSError as e:
            out["steps"].append({"axis": axis, "status": "could not start: %s" % e})
            continue
        with open(os.path.join(os.path.dirname(state), "step-%s-%s.log" % (case["name"], axis)), "w",
                  encoding="utf-8") as fh:
            fh.write(done.stdout)
        if done.returncode != 0:
            out["steps"].append({"axis": axis, "status": "exit %d" % done.returncode})
            continue
        out["steps"].append({"axis": axis, "status": "ran"})
        ran.append(axis)
    code, stdout, stderr = script("brief.py", run, env=env)
    if code != 0:
        out["error"] = "brief.py exit %d: %s" % (code, stderr.strip())
        return out
    require = ["--require", "brief"]
    for axis in ran:
        require += ["--require", axis]
    for name, args in (("validate.py", [run] + require), ("check-pointers.py", [run])):
        code, stdout, stderr = script(name, *args, env=env)
        defects = [ln for ln in (stdout + stderr).split("\n") if DEFECT.match(ln)]
        out["checks"].append({"script": name, "exit": code, "defects": defects})
    return out


# --- Score --------------------------------------------------------------------

def read_brief(run):
    """(bucket of each changed file, must-read findings of no changed file,
    verdict line) as the brief lists them."""
    path = os.path.join(run, fmt.BRIEF)
    _, _, listed = fmt.parse_brief(path)
    placed = {p: bucket for p, bucket, _, _ in listed if p}
    loose, section = [], None
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for line in text.split("\n"):
        if line.startswith("## "):
            section = line[3:].strip()
        elif section == fmt.BUCKET_SECTION["must-read"] and LOOSE.match(line):
            loose.append(LOOSE.match(line).group(1))
    verdict = next((ln for ln in text.split("\n") if ln.startswith("Proposed verdict:")), None)
    return placed, loose, verdict


def score_case(case, ran):
    """The score of one replayed case against its labels."""
    out = {"name": case["name"], "run": ran.get("run"), "verdict": None, "items": [], "must_read_files": [],
           "noise": [], "unlabelled": [], "loose": [], "ask": ran.get("ask"), "failures": []}
    for step in ran.get("steps", []):
        if step["status"] not in ("ran", NO_AGENT):
            out["failures"].append("step %s %s" % (step["axis"], step["status"]))
    if ran.get("error"):
        out["failures"].append(ran["error"])
    for check in ran.get("checks", []):
        if check["exit"] != 0 or check["defects"]:
            out["failures"].append("%s exit %d: %s" % (check["script"], check["exit"],
                                                       "; ".join(check["defects"]) or "no defect line"))
    run = ran.get("run")
    if not run or not os.path.isfile(os.path.join(run, fmt.BRIEF)):
        out["failures"].append("no brief to score")
        out["items"] = [dict(i, bucket="no brief") for i in case["must_read"]]
        return out
    placed, loose, verdict = read_brief(run)
    out["verdict"], out["loose"] = verdict, loose
    for item in case["must_read"]:
        bucket = placed.get(item["path"], "not in the diff")
        out["items"].append(dict(item, bucket=bucket))
        if bucket == "skim":
            out["failures"].append("must-read item `%s` classified skim" % item["path"])
    labelled = {i["path"] for i in case["must_read"]}
    unnecessary = set(case["unnecessary"])
    must = [p for p, b in placed.items() if b == "must-read"]
    out["must_read_files"] = must
    out["noise"] = [p for p in must if p in unnecessary]
    out["unlabelled"] = [p for p in must if p not in labelled and p not in unnecessary]
    return out


def totals(scored):
    items = [i for c in scored for i in c["items"]]
    recalled = sum(1 for i in items if i["bucket"] == "must-read")
    must = sum(len(c["must_read_files"]) for c in scored)
    noise = sum(len(c["noise"]) for c in scored)
    return {"cases": len(scored), "failed_cases": sum(1 for c in scored if c["failures"]),
            "items": len(items), "recalled": recalled, "recall": ratio(recalled, len(items)),
            "skim": sum(1 for i in items if i["bucket"] == "skim"),
            "must_read_files": must, "noise": noise, "noise_rate": ratio(noise, must),
            "unlabelled": sum(len(c["unlabelled"]) for c in scored)}


def ratio(n, d):
    return round(n / d, 4) if d else None


def compare(scored, previous):
    """Items recalled in the previous report and not now (`lost`), and the
    reverse (`gained`), by case and path."""
    before = {(c["name"], i["path"]): i["bucket"] for c in previous.get("cases", []) for i in c.get("items", [])}
    lost, gained = [], []
    for c in scored:
        for i in c["items"]:
            old = before.get((c["name"], i["path"]))
            if old == "must-read" and i["bucket"] != "must-read":
                lost.append({"case": c["name"], "path": i["path"], "now": i["bucket"]})
            elif old is not None and old != "must-read" and i["bucket"] == "must-read":
                gained.append({"case": c["name"], "path": i["path"], "was": old})
    return {"lost": lost, "gained": gained}


def percent(r):
    return "n/a" if r is None else "%.1f%%" % (100 * r)


def render(report):
    out = ["%s: corpus %s, %s, agent %s" % (VERSION, report["corpus"], report["review"], report["agent"]),
           "out: %s" % report["out"]]
    for c in report["cases"]:
        recalled = sum(1 for i in c["items"] if i["bucket"] == "must-read")
        out.append("")
        out.append("case %s: %s" % (c["name"], c["verdict"] or "no verdict"))
        out.append("  recall: %d/%d must-read items" % (recalled, len(c["items"])))
        for i in c["items"]:
            word = "ok    " if i["bucket"] == "must-read" else "FAIL  " if i["bucket"] == "skim" else "missed"
            out.append("    %s `%s`: %s%s" % (word, i["path"], i["bucket"], " (%s)" % i["why"] if i["why"] else ""))
        out.append("  noise: %d of %d must-read files marked unnecessary%s"
                   % (len(c["noise"]), len(c["must_read_files"]),
                      ": %s" % ", ".join("`%s`" % p for p in c["noise"]) if c["noise"] else ""))
        if c["unlabelled"]:
            out.append("  unlabelled must-read files (label them): %s" % ", ".join("`%s`" % p for p in c["unlabelled"]))
        if c.get("ask"):
            out.append("  intent not checked, run.py asked: %s (give the case `spec` or `no_spec`)" % c["ask"])
        if c["loose"]:
            out.append("  must-read findings on no changed file (not scored): %s" % ", ".join(c["loose"]))
        for f in c["failures"]:
            out.append("  FAILURE: %s" % f)
        if c["run"]:
            out.append("  run: %s" % c["run"])
    t = report["totals"]
    out += ["", "recall: %d/%d must-read items (%s)" % (t["recalled"], t["items"], percent(t["recall"])),
            "skim: %d must-read item(s) classified skim" % t["skim"],
            "noise: %d of %d must-read files marked unnecessary (%s), %d unlabelled"
            % (t["noise"], t["must_read_files"], percent(t["noise_rate"]), t["unlabelled"])]
    if "compare" in report:
        cmp_ = report["compare"]
        out.append("compared with %s: %d lost, %d gained" % (report["compared_with"], len(cmp_["lost"]),
                                                            len(cmp_["gained"])))
        for i in cmp_["lost"]:
            out.append("  lost   %s `%s`: now %s" % (i["case"], i["path"], i["now"]))
        for i in cmp_["gained"]:
            out.append("  gained %s `%s`: was %s" % (i["case"], i["path"], i["was"]))
    out.append("%s: %d of %d case(s) failed" % ("FAIL" if t["failed_cases"] else "PASS", t["failed_cases"],
                                               t["cases"]))
    return "\n".join(out) + "\n"


def score(corpus, out, names=(), previous=None):
    """Score the runs recorded in <out>/runs.json against the corpus labels
    as they are now; write <out>/report.json; return the report."""
    try:
        with open(os.path.join(out, "runs.json"), encoding="utf-8") as fh:
            runs = json.load(fh)
    except (OSError, ValueError) as e:
        raise CorpusError("no runs to score in %s: %s" % (out, e))
    by_name = {r["name"]: r for r in runs.get("cases", [])}
    cases = [c for c in load_corpus(corpus, names) if c["name"] in by_name]
    if not cases:
        raise CorpusError("no case of %s was replayed in %s" % (corpus, out))
    scored = [score_case(c, by_name[c["name"]]) for c in cases]
    report = {"harness": VERSION, "review": runs.get("review"), "corpus": os.path.abspath(corpus), "out": out,
              "agent": runs.get("agent"), "started": runs.get("started"), "cases": scored, "totals": totals(scored)}
    if previous is not None:
        path, data = previous
        report["compared_with"] = path
        report["compare"] = compare(scored, data)
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    return report


# --- Command line -------------------------------------------------------------

def default_out(now):
    state = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(state, "birdiz-review", "eval", now.strftime("%Y%m%dT%H%M%SZ"))


def main(argv):
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if args else 2
    command, args = args[0], args[1:]
    positional, out, agent, names, timeout, against = [], None, DEFAULT_AGENT, [], 1800, None
    while args:
        a = args.pop(0)
        if a == "--out" and args and command == "run":
            out = args.pop(0)
        elif a == "--agent" and args and command == "run":
            agent = args.pop(0)
        elif a == "--case" and args:
            names.append(args.pop(0))
        elif a == "--timeout" and args and command == "run" and args[0].isdigit():
            timeout = int(args.pop(0))
        elif a == "--compare" and args:
            against = args.pop(0)
        elif not a.startswith("-"):
            positional.append(a)
        else:
            print("unknown argument: %s" % a, file=sys.stderr)
            return 2
    if command not in ("run", "score") or len(positional) != (1 if command == "run" else 2):
        print(__doc__, file=sys.stderr)
        return 2
    corpus = os.path.abspath(positional[0])
    try:
        previous = None
        if against:
            try:
                with open(against, encoding="utf-8") as fh:
                    previous = (os.path.abspath(against), json.load(fh))
            except (OSError, ValueError) as e:
                raise CorpusError("cannot read %s: %s" % (against, e))
        if command == "run":
            now = datetime.datetime.now(datetime.timezone.utc)
            out = os.path.abspath(out or default_out(now))
            if inside(out, REPO):
                raise CorpusError("the output is inside %s: runs copy the corpus's code, keep them outside" % REPO)
            cases = load_corpus(corpus, names)
            state = os.path.join(out, "state")
            os.makedirs(state, exist_ok=True)
            runs = {"harness": VERSION, "review": fmt.VERSION, "agent": agent, "corpus": corpus,
                    "started": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "cases": []}
            for case in cases:
                print("replaying %s ..." % case["name"], file=sys.stderr)
                runs["cases"].append(replay(case, state, agent, timeout))
            with open(os.path.join(out, "runs.json"), "w", encoding="utf-8") as fh:
                json.dump(runs, fh, indent=2)
                fh.write("\n")
        else:
            out = os.path.abspath(positional[1])
        report = score(corpus, out, names, previous)
    except CorpusError as e:
        print("ERROR %s" % e, file=sys.stderr)
        return 2
    sys.stdout.write(render(report))
    return 1 if report["totals"]["failed_cases"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
