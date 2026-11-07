# KPI & quality-gate framework (proposed targets)

Targets are hypotheses until measured on representative Windows devices and independently annotated Thai music.

| Group | Metrics and provisional acceptance targets | Why |
|---|---|---|
| K01 Output integrity (3) | completeness 100% of valid approved jobs; media decode pass 100%; original hashes unchanged 100% | deliver usable files |
| K02 MP3 quality (3) | artwork readable 100%; unchanged audio frames 100%; protected metadata retained 100% | no song degradation |
| K03 Lyrics/timing (4) | approved lyrics text match 100%; phrase MAE <= 200 ms; word timing P95 <= 300 ms; approved segment coverage 100% | truthful synchronization |
| K04 Video quality (4) | video duration mismatch <= 100 ms (config dependent); image coverage 100%; subtitle-safe-area checks pass 100%; AV sync <= 100 ms on test reference | usable lyric video |
| K05 Automation (3) | unattended completion >= 95% on prequalified cases; avoidable reprocessing 0; batch isolation 100% | reduce repetitive work |
| K06 Reliability (4) | designed crash-recovery cases 100%; duplicate artifacts 0; silent failures 0; partial-success state accuracy 100% | predictable failure handling |
| K07 Performance (3) | media baseline memory <= 6 GB; median render real-time factor <= 1.0; measure throughput at 1/10/50/100 jobs | CPU-only feasibility |
| K08 Portability (3) | clean PC launch 100% test matrix; relocation success 100%; Unicode-path compatibility 100% | portable Windows folder |
| K09 UI & usability (3) | ASCII digit compliance 100%; UI interaction P95 <= 200 ms; after-reconnect UI/SSOT consistency 100% | clarity and responsive UI |
| K10 Engineering (2) | critical test pass 100%; core domain/orchestration line coverage >= 90% alongside behavioral tests | safe maintenance |

Total: **10 groups / 32 KPIs**. Definitions: MAE=mean absolute error; P95=95th percentile; RTF=render seconds/audio duration seconds. Define exact scope, fixture, measuring procedure and evidence file before scoring. Do not claim pass without measured results.

## Release quality gates
G1 validate assets/role mapping; G2 MP3 artwork/audio hash; G3 lyrics verified and timing approved; G4 renderer compatibility; G5 MP4 decode/duration/visual samples; G6 output publish + manifest reconciliation. Human approval required for low-confidence Thai vocal alignment.

## Fault injection scenarios
Missing image, corrupt MP3, multi-MP3 mapping, lyrics mismatch, AI timeout, worker kill, disk full, DB busy, moved folders, duplicate event, UI reconnect, cancel during render, non-ASCII paths and Windows locale changes.

## Reporting
Record metric name, numerator/denominator or distribution, dataset, environment, implementation version, evidence URI and outcome. Distinguish blocked for review from failed, and completed MP3 from completed full job.
